"""Reference 24's graph-rewriting decision procedure (Baudier, Fages, Soliman 2018, Alg. 2 and 3).

Decides whether the reaction-labelled influence multigraph has a positive circuit that uses no
reaction twice, not a reaction and its reverse, and not all species of a conservation law, by
eliminating vertices of least in- or out-degree and composing their in and out arcs into labelled
path arcs. A path arc carries (sign, reactions used, internal species). Positive self-loops found
during elimination prove existence; an empty graph proves absence. Dominated parallel arcs (same
sign, subset reactions and subset species) are dropped. Returns True, False, or None if the arc
count exceeds a cap.

Usage: python analysis/elim.py --one MODEL.xml [--signs trajectory|random]
       python analysis/elim.py --list FILE --out FILE.jsonl
"""
import argparse
import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import loops as L  # noqa: E402

EDGE_CAP = 300000


def positive_circuit_exists(n, arcs, reverse, supports, sign_wanted=1):
    rev = {k: frozenset(v) for k, v in reverse.items()}
    out = {v: [] for v in range(n)}
    inn = {v: [] for v in range(n)}
    for a, b, lab, s in arcs:
        if a == b:
            if s == sign_wanted and not any(sp <= {a} for sp in supports):
                return True
            continue
        e = (a, b, s, frozenset([lab]), frozenset())
        out[a].append(e); inn[b].append(e)
    alive = set(v for v in range(n) if out[v] or inn[v])
    total = sum(len(out[v]) for v in alive)

    def ok_reactions(R1, R2):
        if R1 & R2:
            return False
        for r in R1:
            if rev.get(r, frozenset()) & R2:
                return False
        return True

    def add(e):
        nonlocal total
        a, b, s, R, I = e
        for f in out[a]:  # dominance check against existing parallel arcs
            if f[1] == b and f[2] == s and f[3] <= R and f[4] <= I:
                return
        keep = []
        for f in out[a]:
            if f[1] == b and f[2] == s and R <= f[3] and I <= f[4]:
                inn[b].remove(f); total -= 1
            else:
                keep.append(f)
        out[a] = keep
        out[a].append(e); inn[b].append(e); total += 1

    while alive:
        v = min(alive, key=lambda u: min(len(inn[u]), len(out[u])))
        ins, outs = list(inn[v]), list(out[v])
        for e in ins:
            out[e[0]].remove(e); total -= 1
        for e in outs:
            if e[1] != v:
                inn[e[1]].remove(e); total -= 1
        inn[v], out[v] = [], []
        alive.discard(v)
        for (w, _, s1, R1, I1) in ins:
            for (_, x, s2, R2, I2) in outs:
                if not ok_reactions(R1, R2):
                    continue
                if I1 & I2 or w in I2 or x in I1 or v in I1 or v in I2:
                    continue
                R, I, s = R1 | R2, I1 | I2 | {v}, s1 * s2
                if w == x:
                    species = I | {w}
                    if any(sp <= species for sp in supports):
                        continue
                    if s == sign_wanted:
                        return True
                    continue  # negative self-loop: delete
                add((w, x, s, R, frozenset(I)))
                if total > EDGE_CAP:
                    return None
        alive = {u for u in alive if inn[u] and out[u]} | {u for u in alive if False}
        # vertices with no in or no out arcs cannot lie on a circuit
        dead = [u for u in list(alive) if not inn[u] or not out[u]]
        while dead:
            u = dead.pop()
            if u not in alive:
                continue
            alive.discard(u)
            for e in list(out[u]):
                inn[e[1]].remove(e); total -= 1
                if e[1] in alive and not inn[e[1]]:
                    dead.append(e[1])
            for e in list(inn[u]):
                out[e[0]].remove(e); total -= 1
                if e[0] in alive and not out[e[0]]:
                    dead.append(e[0])
            out[u], inn[u] = [], []
    return False


def decide(path):
    import numpy as np
    rr, flags = L.load(path)
    nodes, kinds, rule_syms = L.state_nodes(rr, flags)
    try:
        S = rr.getFullStoichiometryMatrix(); rids_S, rows = list(S.colnames), {s: i for i, s in enumerate(S.rownames)}
    except Exception:
        S, rids_S, rows = None, [], {}
    rids, rsign, gsign, jac = L.derivative_signs(rr, nodes, kinds, rule_syms)
    N = np.zeros((len(nodes), len(rids)))
    for k, s in enumerate(nodes):
        if s in rows:
            full = np.array(S[rows[s]])
            for c, r in enumerate(rids):
                if r in rids_S:
                    N[k, c] = full[rids_S.index(r)]
    arcs = L.influence_arcs(nodes, rids, N, rsign, rule_syms, gsign, flags.get('_reversible'))
    cls, rev = L.reaction_classes(N, rids)
    active = [i for i in range(N.shape[0]) if np.any(N[i])]
    sup_active, inv_ok = L.p_invariant_supports(N[active]) if active else ([], True)
    supports = [frozenset(active[i] for i in sp) for sp in sup_active] if inv_ok else []
    return {'model': pathlib.Path(path).stem, 'status': 'ok',
            'refined_positive_elim': positive_circuit_exists(len(nodes), [(a, b, cls.get(l, l), s) for a, b, l, s in arcs if not (a == b and s < 0)], rev, supports)}


def run_list(paths, out_file, jobs, timeout, signs):
    me = pathlib.Path(__file__).resolve()

    def one(f):
        try:
            p = subprocess.run([sys.executable, str(me), '--one', f, '--signs', signs], capture_output=True, text=True, timeout=timeout)
            line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
            return json.loads(line) if line.startswith('{') else {'model': pathlib.Path(f).stem, 'status': 'error', 'error': (p.stderr or '')[-300:]}
        except subprocess.TimeoutExpired:
            return {'model': pathlib.Path(f).stem, 'status': 'timeout'}
    with ThreadPoolExecutor(jobs) as ex, open(out_file, 'w') as fh:
        for r in ex.map(one, paths):
            fh.write(json.dumps(r) + '\n'); fh.flush()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--one'); ap.add_argument('--list'); ap.add_argument('--out')
    ap.add_argument('--jobs', type=int, default=4); ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--signs', choices=['trajectory', 'random'], default='trajectory')
    a = ap.parse_args()
    L.SIGN_MODE = a.signs
    if a.one:
        try:
            print(json.dumps(decide(a.one)))
        except Exception as e:
            print(json.dumps({'model': pathlib.Path(a.one).stem, 'status': 'error', 'error': repr(e)[:300]}))
    else:
        run_list([l.strip() for l in open(a.list) if l.strip()], a.out, a.jobs, a.timeout, a.signs)
