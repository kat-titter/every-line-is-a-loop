"""Second integrator detector: near-integrators measured at the model's own states.

A variable keeps a near-running total when its own level barely moves its net rate:
    r_i = |df_i/dx_i| * |x_i| / (flux through i),  flux = sum_j max(N_ij v_j, 0) (+ |rate rule|)
First-order decay gives r_i = 1 at steady state; saturated (zero-order) removal gives r_i << 1;
a structural integrator gives 0. A node is a near-integrator if r_i < R_CUT at the last state
reached (t = 1000, or the latest state the integrator reached) with non-zero flux.

Third detector: paired running totals. Two variables a and b keep a running total together when some
weighted sum z = c_a x_a + c_b x_b changes at a rate that depends on neither a nor b, at every state read,
but does depend on something else. That is c^T J[S, S] = 0 at every state for S = {a, b}, with both weights
non-zero, and c^T J[S, rest] != 0 somewhere. Khammash's antithetic controller is the example: z1 and z2
destroy each other, and z1 - z2 integrates the error. Pairs in which one variable alone already integrates
are left to the strict reading, and so are pair totals that equal one variable plus a constant once the
model's conserved totals are used (in E + S <-> ES -> E + P, E - S is P in disguise). The rate must also be
free of every variable that shares a conserved total with a or b, such as their complexes: otherwise the
total still feels its own members through them, and the independence is only a change of coordinates.
The states a model
visits can hide a dependence (a pathway that is idle there) or fake one away (a saturated enzyme), so each
candidate found at those states is then confirmed from the rate laws: the weights are rounded to a small
ratio, and the exact derivative of the weighted sum's rate with respect to each member must cancel at
random states spread over six orders of magnitude, with the parameters at the model's values.

Usage: python analysis/integrators.py --list FILE --out FILE.jsonl [--jobs 8]
       python analysis/integrators.py --one MODEL.xml
"""
import argparse
import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import loops as L  # noqa: E402

R_CUT = 0.1
PAIR_TOL = 1e-4     # a 2 x 2T matrix counts as rank one when s2/s1 < PAIR_TOL (finite differences carry ~1e-6 error)


def measure(path):
    rr, flags = L.load(path)
    nodes, kinds, rule_syms = L.state_nodes(rr, flags)
    L.SIGN_MODE = 'trajectory'
    rids, rsign, gsign, jac = L.derivative_signs(rr, nodes, kinds, rule_syms)
    out = {'model': pathlib.Path(path).stem, 'status': 'ok'}
    if not jac:
        out['status'] = 'no states'; return out
    try:
        S = rr.getFullStoichiometryMatrix(); rows = {s: i for i, s in enumerate(S.rownames)}; cols = list(S.colnames)
    except Exception:
        S, rows, cols = None, {}, []
    N = np.zeros((len(nodes), len(rids)))
    for k, s in enumerate(nodes):
        if s in rows:
            full = np.array(S[rows[s]])
            for c, r in enumerate(rids):
                if r in cols:
                    N[k, c] = full[cols.index(r)]
    dv, dg, x = jac[-1]                       # last state reached
    put = L.setter(rr, kinds)
    for nd, v in zip(nodes, x):
        try:
            put(nd, v)
        except Exception:
            pass
    v = np.array(rr.model.getReactionRates())
    flux = np.array([np.sum(np.maximum(N[i] * v, 0.0)) for i in range(len(nodes))])
    diag = (N * dv.T).sum(axis=1)
    for q, y in enumerate(rule_syms):
        if y in nodes:
            i = nodes.index(y)
            diag[i] += dg[q, i]
            try:
                flux[i] += abs(float(rr.getRatesOfChangeNamedArray()[0][list(c.rstrip("'") for c in rr.getRatesOfChangeNamedArray().colnames).index(y)]))
            except Exception:
                pass
    ratio = {nodes[i]: (abs(diag[i]) * abs(x[i]) / flux[i]) for i in range(len(nodes)) if flux[i] > 1e-300}
    out['near_integrators'] = sorted(n for n, r in ratio.items() if r < R_CUT)
    out['ratios'] = {n: round(float(r), 4) for n, r in ratio.items() if r < 1.0}
    out['states_used'] = len(jac)
    cands = pair_integrators(nodes, N, rule_syms, jac, [kinds.get(nd) == 'species' and nd not in rule_syms for nd in nodes])
    pairs, unchecked = [], 0
    for a, b, ca, cb, part in cands:
        ok = confirm_pair(path, rr, flags, nodes, kinds, rids, N, a, b, ca, cb, part)
        if ok is None:
            unchecked += 1
        elif ok:
            pairs.append(ok)
    out['pair_candidates'] = len(cands)
    out['pair_unchecked'] = unchecked
    out['pair_integrators'] = pairs
    out['pair_nodes'] = sorted({v for a, b, _, _ in pairs for v in (a, b)})
    return out


def confirm_pair(path, rr, flags, nodes, kinds, rids, N, a, b, ca, cb, part=()):
    """Exact check of a numeric candidate. Returns [a, b, wa, wb] with rational weights, False, or None
    if a rate law cannot be read symbolically."""
    import re
    from fractions import Fraction
    import sympy as sp
    ratio = Fraction(cb / ca).limit_denominator(12)
    if abs(float(ratio) - cb / ca) > 1e-3 * max(1.0, abs(cb / ca)):
        return False  # not a small whole-number ratio: an approximate cancellation
    wa, wb = sp.Integer(ratio.denominator), sp.Integer(ratio.numerator)
    ia, ib = nodes.index(a), nodes.index(b)
    assign = {v: e.replace('^', '**') for v, e in flags.get('_assign_txt', {}).items()}
    rate_txt = rate_rules(path)
    terms = []
    for j, rid in enumerate(rids):
        w = wa * sp.Rational(N[ia, j]).limit_denominator(1000) + wb * sp.Rational(N[ib, j]).limit_denominator(1000)
        if w != 0:
            law = flags.get('_laws', {}).get(rid)
            if not law:
                return None
            terms.append((w, law.replace('^', '**'), flags.get('_local_params', {}).get(rid, {})))
    for v, w in ((a, wa), (b, wb)):
        if v in rate_txt:
            terms.append((w, rate_txt[v].replace('^', '**'), {}))
    if not terms:
        return False

    def expand(txt):
        for _ in range(25):
            hit = False
            for v, e in assign.items():
                if re.search(r'\b' + re.escape(v) + r'\b', txt):
                    txt = re.sub(r'\b' + re.escape(v) + r'\b', '(' + e + ')', txt); hit = True
            if not hit:
                return txt
        return None
    syms, exprs = {}, []
    for w, txt, local in terms:
        txt = expand(txt)
        if txt is None or re.search(r'\b(piecewise|delay|and|or|not|lt|gt|leq|geq|eq|neq|rateOf)\b', txt):
            return None
        ids = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', re.sub(r'\b\d+\.?\d*[eE][-+]?\d+', '0', txt))) - {'exp', 'ln', 'log', 'sqrt', 'abs', 'pow', 'pi', 'exponentiale'}
        loc = {i: sp.Symbol('v_' + i) for i in ids}
        try:
            e = sp.sympify(txt.replace('ln(', 'log('), locals={**loc, 'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt, 'abs': sp.Abs, 'pow': sp.Pow})
        except Exception:
            return None
        e = e.subs({loc[i]: val for i, val in local.items() if i in loc})
        syms.update({i: loc[i] for i in ids if i not in local})
        exprs.append(w * e)
    total = sp.Add(*exprs)
    var = {nd: syms[nd] for nd in nodes if nd in syms}
    fixed = {}
    for i, sym in syms.items():
        if i in var:
            continue
        try:
            fixed[sym] = float(rr.getValue('[' + i + ']') if i in kinds else rr.getValue(i)) if i != 'time' else 0.0
        except Exception:
            return None
    rr.resetToOrigin()
    ref = {}
    for nd in var:
        try:
            x = float(rr.getValue('[' + nd + ']') if kinds.get(nd) == 'species' else rr.getValue(nd))
        except Exception:
            x = 1.0
        ref[nd] = x if x != 0 else 1.0
    rng = np.random.default_rng(len(nodes) * 7919 + ia * 31 + ib)
    parts = {v: [sp.diff(e_, var[v]) for e_ in exprs] for v in (a, b, *part) if v in var}
    for _ in range(4):
        pt = dict(fixed)
        for nd, sym in var.items():
            pt[sym] = ref[nd] * 10 ** rng.uniform(-3, 3)
        for v, ds in parts.items():
            try:
                vals = [complex(d.evalf(subs=pt)) for d in ds]
            except Exception:
                return None
            tot, scale = abs(sum(vals)), sum(abs(x) for x in vals)
            if not np.isfinite(scale):
                return None
            if tot > 1e-9 * scale + 1e-300:
                return False
    return [a, b, int(wa), int(wb)] if wa > 0 else [a, b, -int(wa), -int(wb)]


_RATE_RULES = {}


def rate_rules(path):
    if path not in _RATE_RULES:
        import libsbml
        doc = libsbml.readSBMLFromFile(str(path))
        conv = libsbml.ConversionProperties(); conv.addOption('expandFunctionDefinitions', True); doc.convert(conv)
        m = doc.getModel()
        _RATE_RULES[path] = {m.getRule(i).getVariable(): libsbml.formulaToL3String(m.getRule(i).getMath())
                             for i in range(m.getNumRules()) if m.getRule(i).isRate()}
    return _RATE_RULES[path]


def jacobians(nodes, N, rule_syms, jac):
    Js = []
    for dv, dg, _ in jac:
        J = N @ dv
        for q, y in enumerate(rule_syms):
            if y in nodes:
                J[nodes.index(y), :] += dg[q, :]
        Js.append(J)
    return np.array(Js)


def conservation_projector(N, is_reacting):
    """(I - P, P), where P projects onto the conserved totals (left null space of the stoichiometry of species).
    P[i, a] != 0 means i and a share a conserved total."""
    n = N.shape[0]
    rows = [i for i in range(n) if is_reacting[i]]
    P = np.zeros((n, n))
    if rows and N.shape[1]:
        A = N[rows]
        u, sv, _ = np.linalg.svd(A, full_matrices=True)
        rank = int(np.sum(sv > 1e-9 * (sv[0] if len(sv) else 1.0)))
        L = np.zeros((n, A.shape[0] - rank))
        L[rows] = u[:, rank:]
        P = L @ L.T
    return np.eye(n) - P, P


def partners(P, a, b):
    return [i for i in range(P.shape[0]) if i not in (a, b) and (abs(P[i, a]) > 1e-9 or abs(P[i, b]) > 1e-9)]


def pair_integrators(nodes, N, rule_syms, jac, is_reacting):
    Js = jacobians(nodes, N, rule_syms, jac)
    n = len(nodes)
    Q, P = conservation_projector(N, is_reacting)
    qn = np.linalg.norm(Q, axis=0)
    touch = np.any(Js != 0, axis=0)
    found = []
    for a in range(n):
        for b in range(a + 1, n):
            if not (touch[a, b] or touch[b, a]):
                continue  # without a link between them the matrix is diagonal, and rank one means a single integrator
            cols = [a, b] + partners(P, a, b)
            M = np.concatenate([J[np.ix_([a, b], cols)] for J in Js], axis=1)
            k = len(cols)
            if not (np.any(M[0]) and np.any(M[1]) and np.any(M[:, 0::k]) and np.any(M[:, 1::k])):
                continue
            rn = np.max(np.abs(M), axis=1)
            s_ = np.linalg.svd(M / rn[:, None], compute_uv=True)
            U, sv = s_[0], s_[1]
            if sv[1] > PAIR_TOL * sv[0]:
                continue
            c = U[:, 1] / rn
            c = c / np.max(np.abs(c))
            if np.min(np.abs(c)) < 1e-3:
                continue
            rest = [i for i in range(n) if i not in cols]
            resp = max((np.max(np.abs(c @ J[[a, b]][:, rest])) / (np.max(np.abs(J[[a, b]])) or 1.0)) for J in Js) if rest else 0.0
            if resp < PAIR_TOL:
                continue  # a conserved total, or one that responds to nothing
            full = np.zeros(n)
            full[[a, b]] = c
            r = Q @ full
            if np.linalg.norm(r) > 0 and np.max(np.abs(Q.T @ r) / (qn * np.linalg.norm(r) + 1e-300)) > 1 - 1e-8:
                continue  # one variable plus a constant, given the conserved totals
            if c[0] < 0:
                c = -c
            found.append([nodes[a], nodes[b], round(float(c[0]), 4), round(float(c[1]), 4), [nodes[i] for i in cols[2:]]])
    return found


def run_list(paths, out_file, jobs, timeout=240):
    me = pathlib.Path(__file__).resolve()

    def one(f):
        try:
            p = subprocess.run([sys.executable, str(me), '--one', f], capture_output=True, text=True, timeout=timeout)
            line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
            return json.loads(line) if line.startswith('{') else {'model': pathlib.Path(f).stem, 'status': 'error', 'error': (p.stderr or '')[-300:]}
        except subprocess.TimeoutExpired:
            return {'model': pathlib.Path(f).stem, 'status': 'timeout'}
    with ThreadPoolExecutor(jobs) as ex, open(out_file, 'w') as fh:
        for r in ex.map(one, paths):
            fh.write(json.dumps(r) + '\n'); fh.flush()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--one'); ap.add_argument('--list'); ap.add_argument('--out'); ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args()
    if a.one:
        try:
            print(json.dumps(measure(a.one)))
        except Exception as e:
            print(json.dumps({'model': pathlib.Path(a.one).stem, 'status': 'error', 'error': repr(e)[:300]}))
    else:
        run_list([l.strip() for l in open(a.list) if l.strip()], a.out, a.jobs)
