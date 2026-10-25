"""Loop census for SBML models, following Baudier, Fages and Soliman 2018 (reference 24).

For one SBML model this builds the reaction-labelled influence multigraph (arc i -> k
labelled by reaction j with sign of dv_j/dx_i * N_kj; rate rules act as one labelled
pseudo-reaction each), estimating the partial derivatives by central differences at
several random positive states and keeping every sign seen (an over-approximation, as in
reference 24). Negative self-loops are dropped (decay); positive self-loops are kept
(autocatalysis).

Circuits are then counted two ways:
  plain    elementary circuits of the signed influence graph (Thomas's setting)
  refined  circuits that use no reaction twice, not a reaction and its reverse, and not all
           species of a conservation law (reference 24, Corollaries 2.3, 2.4, 2.5)

Reported per model: whether plain negative / positive circuits exist; whether a refined
positive circuit exists; the refined loop count c (distinct node cycles with their sign),
its negative count k, the number j that pass through an integrator (a node whose own rate
does not depend on itself), the cyclomatic number nu of the refined core (E - N + C), and
whether the loops share arcs (when they do, k depends on how loops are chosen).

Usage:
  python analysis/loops.py --one MODEL.xml           one model, JSON to stdout
  python analysis/loops.py --all DIR --out FILE.jsonl [--jobs 8] [--timeout 180]
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

CIRCUIT_CAP = 20000      # stop enumerating after this many labelled circuits
DFS_STEPS = 5_000_000    # search-step budget per enumeration (a count, not a clock, so results do not depend on machine load)
SAMPLES = 5              # states at which derivative signs are read
SIGN_MODE = 'trajectory' # 'trajectory': the model's own states at t = 0, 1, 10, 100, 1000
                         # 'random': random states, each variable within the range it reaches on its own run
REL_STEP = 1e-3


# ---------------------------------------------------------------- model loading
def load(path):
    import libsbml
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
    doc = libsbml.readSBMLFromFile(str(path))
    m = doc.getModel()
    rules = [m.getRule(i) for i in range(m.getNumRules())]
    flags = {
        'species': m.getNumSpecies(), 'reactions': m.getNumReactions(), 'events': m.getNumEvents(),
        'rate_rules': sum(1 for r in rules if r.isRate()), 'assignment_rules': sum(1 for r in rules if r.isAssignment()),
        'algebraic_rules': sum(1 for r in rules if r.isAlgebraic()),
        'fast': any(m.getReaction(i).getFast() for i in range(m.getNumReactions()) if m.getReaction(i).isSetFast()),
        'name': m.getName() or m.getId(),
    }
    flags['_assigned'] = sorted({r.getVariable() for r in rules if r.isAssignment()})
    flags['_rate_vars'] = [r.getVariable() for r in rules if r.isRate()]
    assign = {r.getVariable(): r.getMath() for r in rules if r.isAssignment()}

    def names(node, seen=frozenset()):
        out = set()
        if node is None:
            return out
        if node.getType() == libsbml.AST_NAME:
            nm = node.getName()
            out.add(nm)
            if nm in assign and nm not in seen:
                out |= names(assign[nm], seen | {nm})
        for i in range(node.getNumChildren()):
            out |= names(node.getChild(i), seen)
        return out
    flags['_reversible'] = {m.getReaction(i).getId(): bool(m.getReaction(i).getReversible()) for i in range(m.getNumReactions())}
    flags['_deps'] = {m.getReaction(i).getId(): names(m.getReaction(i).getKineticLaw().getMath()) if m.getReaction(i).isSetKineticLaw() else set()
                      for i in range(m.getNumReactions())}
    flags['_rule_deps'] = {r.getVariable(): names(r.getMath()) for r in rules if r.isRate()}
    try:
        conv = libsbml.ConversionProperties(); conv.addOption('expandFunctionDefinitions', True)
        doc2 = libsbml.readSBMLFromFile(str(path)); doc2.convert(conv); m2 = doc2.getModel()
        flags['_laws'] = {m2.getReaction(i).getId(): libsbml.formulaToL3String(m2.getReaction(i).getKineticLaw().getMath())
                          for i in range(m2.getNumReactions()) if m2.getReaction(i).isSetKineticLaw()}
        flags['_assign_txt'] = {m2.getRule(i).getVariable(): libsbml.formulaToL3String(m2.getRule(i).getMath())
                                for i in range(m2.getNumRules()) if m2.getRule(i).isAssignment()}
        locals_ = {}
        for i in range(m2.getNumReactions()):
            kl = m2.getReaction(i).getKineticLaw()
            if kl is not None:
                for q in list(kl.getListOfParameters()) + list(kl.getListOfLocalParameters() if hasattr(kl, 'getListOfLocalParameters') else []):
                    locals_.setdefault(m2.getReaction(i).getId(), {})[q.getId()] = q.getValue()
        flags['_local_params'] = locals_
    except Exception:
        flags['_laws'], flags['_assign_txt'], flags['_local_params'] = {}, {}, {}
    rr = roadrunner.RoadRunner(str(path))
    return rr, flags


def state_nodes(rr, flags):
    m = rr.model
    fl = list(m.getFloatingSpeciesIds())
    assigned = set(flags['_assigned'])
    rule_syms = list(flags['_rate_vars'])
    nodes = [s for s in fl if s not in assigned] + [s for s in rule_syms if s not in fl]
    kinds = {s: 'species' for s in fl}
    return nodes, kinds, rule_syms


def setter(rr, kinds):
    def put(node, value):
        if kinds.get(node) == 'species':
            rr.setValue('[' + node + ']', float(value))
        else:
            rr.setValue(node, float(value))
    return put


def getter(rr, kinds):
    def get(node):
        return rr.getValue('[' + node + ']') if kinds.get(node) == 'species' else rr.getValue(node)
    return get


# ---------------------------------------------------------------- derivatives
def derivative_signs(rr, nodes, kinds, rule_syms, seed=0):
    """Return (reaction ids, sign sets for reactions, sign sets for rate rules, samples).
    Each sample state is read in its own context: 'trajectory' mode resets the model and
    simulates to t = 0, 1, 10, 100, 1000 separately (so events and the clock apply only where
    they belong, and one failed run loses one state); 'random' mode draws species levels
    10^U(-1, 1) around the initial ones. Only exact zeros of species are lifted to a small
    positive level; signed variables such as voltages keep their values."""
    m = rr.model
    put, get = setter(rr, kinds), getter(rr, kinds)
    rids = list(m.getReactionIds())
    is_sp = np.array([kinds.get(s) == 'species' for s in nodes], dtype=bool)
    rr.resetToOrigin()
    x0 = np.array([get(s) for s in nodes], dtype=float)
    pos = x0[is_sp & np.isfinite(x0) & (x0 > 0)]
    fill = float(np.median(pos)) if len(pos) else 1.0

    def lift(x):
        y = np.array(x, dtype=float)
        y[is_sp & (y <= 0)] = 1e-6 * fill
        return y

    def rule_rates():
        if not rule_syms:
            return np.zeros(0)
        out = np.full(len(rule_syms), np.nan)
        try:
            a = rr.getRatesOfChangeNamedArray()
            named = {c.rstrip("'"): float(v) for c, v in zip(a.colnames, a[0])}
        except Exception:
            named = {}
        for q, y in enumerate(rule_syms):
            if y in named:
                out[q] = named[y]
            else:
                try:
                    out[q] = rr.getValue(y + "'")
                except Exception:
                    pass
        return out

    rng = np.random.default_rng(seed)
    contexts = []  # (time to simulate to, state or None to read after simulation)
    if SIGN_MODE == 'trajectory':
        contexts = [(t, None) for t in (0, 1, 10, 100, 1000)]
    else:  # random states, each variable drawn log-uniformly within the range it reaches on its own run
        lo, hi = np.abs(lift(x0)), np.abs(lift(x0))
        try:
            rr.resetToOrigin()
            tr = np.array(rr.simulate(0, 1000, 201, [('[' + s + ']') if kinds.get(s) == 'species' else s for s in nodes]))
            ok_ = np.all(np.isfinite(tr), axis=1)
            if ok_.any():
                a = np.abs(tr[ok_])
                lo, hi = np.minimum(lo, a.min(axis=0)), np.maximum(hi, a.max(axis=0))
        except Exception:
            pass
        lo = np.where(lo > 0, lo, np.maximum(hi, 1e-6 * fill) * 1e-3)
        hi = np.maximum(hi, lo)
        sgn = np.where(np.sign(x0) < 0, -1.0, 1.0)
        draw = lambda: sgn * np.exp(rng.uniform(np.log(lo), np.log(hi)))
        contexts = [(0, lift(x0))] + [(0, np.where(is_sp, np.abs(draw()), draw())) for _ in range(SAMPLES - 1)]
    rsign = [[set() for _ in nodes] for _ in rids]
    gsign = [[set() for _ in nodes] for _ in rule_syms]
    jac_rows, neg_at_large = [], set()
    for ci, (t, given) in enumerate(contexts):
        try:
            rr.resetToOrigin()
            if t > 0:
                rr.simulate(0, t, 3)
            x = lift(np.array([get(s) for s in nodes], dtype=float)) if given is None else np.array(given, dtype=float)
            for nd, v in zip(nodes, x):
                put(nd, v)
        except Exception:
            continue
        if ci == 0:  # rate turns negative when one variable is pushed 1000x (fallback self-loop test)
            for i, nd in enumerate(nodes):
                try:
                    put(nd, x[i] * 1e3); vv = np.array(m.getReactionRates()); put(nd, x[i])
                    for j in np.nonzero(np.isfinite(vv) & (vv < 0))[0]:
                        neg_at_large.add((int(j), i))
                except Exception:
                    pass
        dv = np.zeros((len(rids), len(nodes)))
        dg = np.zeros((len(rule_syms), len(nodes)))
        for i, nd in enumerate(nodes):
            h = REL_STEP * abs(x[i]) if x[i] != 0 else 1e-6 * fill
            try:
                put(nd, x[i] + h); vp = np.array(m.getReactionRates()); gp = rule_rates()
                put(nd, x[i] - h); vm = np.array(m.getReactionRates()); gm = rule_rates()
                put(nd, x[i])
            except Exception:
                try:
                    put(nd, x[i])
                except Exception:
                    pass
                continue
            for arr_p, arr_m, outm, signs in ((vp, vm, dv, rsign), (gp, gm, dg, gsign)):
                if not len(arr_p):
                    continue
                d = arr_p - arr_m
                ok = np.isfinite(d) & (np.abs(d) > 1e-13 * (np.abs(arr_p) + np.abs(arr_m)) + 1e-300)
                outm[:, i] = np.where(ok, d / (2 * h), 0.0)
                for j in np.nonzero(ok)[0]:
                    signs[j][i].add(1 if d[j] > 0 else -1)
        jac_rows.append((dv, dg, x))
    derivative_signs.neg_at_large = neg_at_large
    derivative_signs.states_used = len(jac_rows)
    return rids, rsign, gsign, jac_rows


# ---------------------------------------------------------------- graph pieces
def _dep(v, var, assign, seen=None):
    """True if assignment variable v depends on var, directly or through other assignments."""
    import re
    seen = seen or set()
    e = assign.get(v, '')
    if re.search(r'\b' + re.escape(var) + r'\b', e):
        return True
    return any(_dep(w, var, assign, seen | {v}) for w in assign
               if w not in seen and w != v and re.search(r'\b' + re.escape(w) + r'\b', e))


def rate_has_positive_root(rr, flags, rid, var, ref_values):
    """True if reaction rid's rate law, as a function of var with every other symbol at its
    reference value, has a numerator root at a positive value of var (an implicit substrate runs
    out, or the flux reverses). None if the law cannot be handled symbolically."""
    import re
    import sympy as sp
    law = flags.get('_laws', {}).get(rid)
    if not law:
        return None
    txt = law.replace('^', '**')
    for _ in range(10):  # substitute assignment rules
        hit = False
        for v, e in flags.get('_assign_txt', {}).items():
            if not _dep(v, var, flags.get('_assign_txt', {})):
                continue  # not driven by var: keep as a symbol, take its reference value below
            if re.search(r'\b' + re.escape(v) + r'\b', txt):
                txt = re.sub(r'\b' + re.escape(v) + r'\b', '(' + e.replace('^', '**') + ')', txt); hit = True
        if not hit:
            break
    if re.search(r'\b(piecewise|delay|and|or|not|lt|gt|leq|geq|eq|neq)\b', txt):
        return None
    ids = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', re.sub(r'\b\d+\.?\d*[eE][-+]?\d+', '0', txt))) - {'exp', 'ln', 'log', 'sqrt', 'abs', 'pow', 'pi', 'exponentiale'}
    syms = {i: sp.Symbol('v_' + i) for i in ids}
    try:
        expr = sp.sympify(txt.replace('ln(', 'log('), locals={**syms, 'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt, 'abs': sp.Abs, 'pow': sp.Pow})
    except Exception:
        return None
    if var not in syms:
        return False
    local = flags.get('_local_params', {}).get(rid, {})
    subs = {}
    for i, sym in syms.items():
        if i == var:
            continue
        if i in local:
            subs[sym] = local[i]; continue
        try:
            val = ref_values.get(i)
            if val is None:
                val = rr.getValue('[' + i + ']') if i in ref_values.get('_species', ()) else rr.getValue(i)
            subs[sym] = float(val)
        except Exception:
            return None
    x = syms[var]
    try:
        e2 = expr.subs(subs).subs(sp.Symbol('time'), 0)
        num = sp.numer(sp.together(e2))
        poly = sp.Poly(sp.expand(num), x)
        if poly.free_symbols - {x} or not poly.domain.is_Numerical:
            return None
        if poly.degree() <= 0:
            return False
        roots = [complex(r) for r in poly.nroots(n=15, maxsteps=200)]
    except Exception:
        return None
    return any(abs(r.imag) < 1e-9 * max(1, abs(r.real)) and r.real > 1e-12 for r in roots)


def influence_arcs(nodes, rids, N, rsign, rule_syms, gsign, reversible=None, neg_at_large=None, root_test=None):
    """Arcs (src, dst, label, sign); N is species x reactions aligned to nodes (rows) and rids.
    Self-loops: a negative self-loop is kept only where a reaction producing the species slows as
    the species rises and its rate stays non-negative when the species is pushed 1000x higher
    (end-product inhibition, autorepression); decay, consumption and reverse flux are dropped.
    A positive self-loop from a consumed species whose rate falls as it rises is dropped when
    that rate turns negative at 1000x (a substrate written as total minus itself)."""
    neg_at_large = neg_at_large if neg_at_large is not None else getattr(derivative_signs, 'neg_at_large', set())
    idx = {s: i for i, s in enumerate(nodes)}
    arcs = set()
    for j, r in enumerate(rids):
        targets = [(k, N[k, j]) for k in range(len(nodes)) if N[k, j] != 0]
        for i in range(len(nodes)):
            for s in rsign[j][i]:
                for k, st in targets:
                    sg = s * (1 if st > 0 else -1)
                    if i == k:
                        flips = None
                        if root_test is not None and ((sg < 0 and st > 0 and s < 0) or (sg > 0 and st < 0 and s < 0)):
                            flips = root_test(r, nodes[i])
                        if flips is None or (flips is False and (j, i) in neg_at_large):
                            flips = (j, i) in neg_at_large   # numeric evidence that the rate turns negative wins
                        if sg < 0 and not (st > 0 and s < 0 and not flips):
                            continue                     # decay, consumption, reverse flux
                        if sg > 0 and st < 0 and s < 0 and flips:
                            continue                     # consumed species written as total minus itself
                    arcs.add((i, k, 'R:' + r, sg))
    for q, y in enumerate(rule_syms):
        if y not in idx:
            continue
        k = idx[y]
        for i in range(len(nodes)):
            for s in gsign[q][i]:
                if i == k and s < 0:
                    continue
                arcs.add((i, k, 'rule:' + y, s))
    return sorted(arcs)


def reaction_classes(N, rids):
    """Map each reaction label to a class label shared by reactions whose net stoichiometry
    columns are equal up to positive scaling (reference 24's 'same reaction', read through the
    rank condition of Theorem 2.2), and return reverse pairs at class level."""
    key_of, cls = {}, {}
    for j, r in enumerate(rids):
        col = N[:, j]
        nz = np.nonzero(np.abs(col) > 1e-12)[0]
        if len(nz) == 0:
            cls['R:' + r] = 'R:' + r
            continue
        v = col / abs(col[nz[0]])
        key = tuple(np.round(v, 9))
        cls['R:' + r] = key_of.setdefault(key, 'C:' + r)
    rev = {}
    keys = {v: k for k, v in key_of.items()}
    for k, lab in key_of.items():
        neg = tuple(-x for x in k)
        if neg in key_of:
            rev.setdefault(lab, set()).add(key_of[neg])
    return cls, rev


def reverse_pairs(N, rids):
    pairs = {}
    cols = [N[:, j] for j in range(N.shape[1])]
    for a in range(len(cols)):
        if not np.any(cols[a]):
            continue
        for b in range(a + 1, len(cols)):
            if np.allclose(cols[a], -cols[b]):
                pairs.setdefault('R:' + rids[a], set()).add('R:' + rids[b])
                pairs.setdefault('R:' + rids[b], set()).add('R:' + rids[a])
    return pairs


def p_invariant_supports(N, cap=3000):
    """Supports of minimal semi-positive conservation laws (y >= 0, y^T N = 0), Farkas method."""
    n, R = N.shape
    if n == 0:
        return [], True
    A = np.hstack([N.astype(float), np.eye(n)])
    rows = [A[i] for i in range(n)]
    for j in range(R):
        keep = [r for r in rows if abs(r[j]) < 1e-12]
        P = [r for r in rows if r[j] > 1e-12]
        M = [r for r in rows if r[j] < -1e-12]
        new = []
        for p in P:
            for q in M:
                c = (-q[j]) * p + p[j] * q
                c[np.abs(c) < 1e-12] = 0
                new.append(c)
                if len(keep) + len(new) > cap:
                    return [], False
        rows = keep + new
        # keep minimal supports only
        sup = [frozenset(np.nonzero(r[R:] > 1e-12)[0]) for r in rows]
        order = sorted(range(len(rows)), key=lambda i: len(sup[i]))
        kept, kept_sup = [], []
        for i in order:
            if any(ks <= sup[i] for ks in kept_sup):
                continue
            kept.append(rows[i]); kept_sup.append(sup[i])
        rows = kept
    sups = [frozenset(np.nonzero(r[R:] > 1e-12)[0]) for r in rows]
    return [s for s in sups if s], True


def sccs(n, adj):
    """Tarjan, iterative. adj: list of iterables of successor indices."""
    index, low, on, st, out, counter = {}, {}, set(), [], [], [0]
    for v0 in range(n):
        if v0 in index:
            continue
        work = [(v0, iter(adj[v0]))]
        index[v0] = low[v0] = counter[0]; counter[0] += 1; st.append(v0); on.add(v0)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1; st.append(w); on.add(w)
                    work.append((w, iter(adj[w]))); advanced = True; break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = st.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                out.append(comp)
    return out


def circuits(n, arcs, refined, reverse, supports, want=None, cap=CIRCUIT_CAP, steps=DFS_STEPS, cls=None):
    """Enumerate elementary circuits. Returns (list of (nodes, labels, sign), complete flag).
    want='+' or '-' stops at the first circuit of that sign."""
    if not refined:  # plain: one arc per (src, dst, sign)
        arcs = sorted({(a, b, '+' if s > 0 else '-', s) for a, b, _, s in arcs})
    succ = [set() for _ in range(n)]
    for a, b, _, _ in arcs:
        succ[a].add(b)
    comp_of = {}
    for ci, comp in enumerate(sccs(n, succ)):
        for v in comp:
            comp_of[v] = ci
    out = [[] for _ in range(n)]
    for a, b, lab, s in arcs:
        if comp_of[a] == comp_of[b]:
            out[a].append((b, lab, s))
    found, budget = [], steps
    complete = True
    sys.setrecursionlimit(100000)

    cls = cls or {}

    def bad_labels(lab, used):
        c = cls.get(lab, lab)
        if c in used:
            return True
        return bool(reverse.get(c, set()) & used)

    for s0 in range(n):
        path, labs, used = [s0], [], set()
        onpath = {s0}
        stack = [(s0, iter(out[s0]), 1)]
        while stack:
            budget -= 1
            if len(found) >= cap or budget < 0:
                return found, False
            v, it, sg = stack[-1]
            step = None
            for (w, lab, s) in it:
                if refined and bad_labels(lab, used):
                    continue
                if w == s0:
                    cyc_sign = sg * s
                    if refined and supports:
                        cset = set(path)
                        if any(sp <= cset for sp in supports):
                            continue
                    if want and ((want == '+') != (cyc_sign > 0)):
                        continue  # existence mode: only the wanted sign counts toward the cap
                    found.append((tuple(path), tuple(labs + [lab]), cyc_sign))
                    if want:
                        return found, complete
                    continue
                if w > s0 and w not in onpath:
                    step = (w, lab, s)
                    break
            if step is None:
                stack.pop()
                if len(path) > 1:
                    onpath.discard(path.pop()); _l = labs.pop(); used.discard(cls.get(_l, _l))
                continue
            w, lab, s = step
            path.append(w); onpath.add(w); labs.append(lab); used.add(cls.get(lab, lab))
            stack.append((w, iter(out[w]), sg * s))
    return found, complete


def has_negative_circuit(n, arcs):
    """Exact: a strongly connected component has no negative directed circuit iff its nodes
    can be two-coloured so each arc's sign is the product of its end colours (directed
    circuits span the cycle space of a strongly connected digraph)."""
    succ = [set() for _ in range(n)]
    for a, b, _, _ in arcs:
        succ[a].add(b)
    for comp in sccs(n, succ):
        cset = set(comp)
        inner = [(a, b, s) for a, b, _, s in arcs if a in cset and b in cset]
        if len(comp) == 1 and not inner:
            continue
        if any(a == b and s < 0 for a, b, s in inner):
            return True
        nbr = {v: [] for v in comp}
        for a, b, s in inner:
            nbr[a].append((b, s)); nbr[b].append((a, s))
        col = {comp[0]: 1}
        todo = [comp[0]]
        while todo:
            v = todo.pop()
            for w, s in nbr[v]:
                want = col[v] * s
                if w not in col:
                    col[w] = want; todo.append(w)
                elif col[w] != want:
                    return True
    return False


def exists(n, arcs, sign, refined, reverse, supports):
    f, complete = circuits(n, arcs, refined, reverse, supports, want=sign)
    hit = any((c[2] > 0) == (sign == '+') for c in f)
    return True if hit else (False if complete else None)


def pf_filtered(loop_arcs, signs, max_classes=20):
    """Fewest arc sign flips that make every accepted loop positive (Sontag et al. 2008's
    distance-to-positive-feedback restricted to the loops that pass the filters). Arcs are
    grouped by which loops they lie on; flipping two arcs of one group cancels, so the
    minimum flips at most one arc per group. Returns None if there are too many groups."""
    if not loop_arcs:
        return 0
    groups = {}
    for a in set().union(*loop_arcs):
        sig = tuple(i for i, la in enumerate(loop_arcs) if a in la)
        groups.setdefault(sig, 0)
    keys = list(groups)
    if len(keys) > max_classes:
        return None
    need = [1 if s < 0 else 0 for s in signs]
    best = None
    for mask in range(1 << len(keys)):
        par = [0] * len(signs)
        cnt = 0
        for g, sig in enumerate(keys):
            if mask >> g & 1:
                cnt += 1
                for i in sig:
                    par[i] ^= 1
        if par == need and (best is None or cnt < best):
            best = cnt
    return best


def cyclomatic(edges):
    nodes = sorted({a for a, _, _ in edges} | {b for _, b, _ in edges})
    if not nodes:
        return 0, 0, 0, 0
    parent = {v: v for v in nodes}

    def f(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]; v = parent[v]
        return v
    for a, b, _ in edges:
        ra, rb = f(a), f(b)
        if ra != rb:
            parent[ra] = rb
    C = len({f(v) for v in nodes})
    return len(edges) - len(nodes) + C, len(edges), len(nodes), C


# ---------------------------------------------------------------- one model
def analyze(path):
    t0 = time.time()
    out = {'model': pathlib.Path(path).stem}
    rr, flags = load(path)
    out.update(flags)
    nodes, kinds, rule_syms = state_nodes(rr, flags)
    for k in ('_assigned', '_rate_vars', '_reversible', '_deps', '_rule_deps', '_laws', '_assign_txt', '_local_params'):
        out.pop(k, None)
    try:
        S = rr.getFullStoichiometryMatrix()
        rids_S, rows = list(S.colnames), {s: i for i, s in enumerate(S.rownames)}
    except Exception:
        S, rids_S, rows = None, [], {}
    N = np.zeros((len(nodes), len(rids_S)))
    for k, s in enumerate(nodes):
        if s in rows:
            N[k] = np.array(S[rows[s]])
    rids, rsign, gsign, jac = derivative_signs(rr, nodes, kinds, rule_syms)
    if rids != rids_S:  # align stoichiometry columns to the reaction order used for derivatives
        N2 = np.zeros((len(nodes), len(rids)))
        for c, r in enumerate(rids):
            if r in rids_S:
                N2[:, c] = N[:, rids_S.index(r)]
        out['stoichiometry_missing'] = sum(1 for r in rids if r not in rids_S)
        N = N2
    rr.resetToOrigin()
    refv = {'_species': set(kinds), 'time': 0.0}
    for nd in nodes:
        try:
            refv[nd] = float(getter(rr, kinds)(nd))
        except Exception:
            pass
    _pos = [v for k_, v in refv.items() if k_ in kinds and isinstance(v, float) and v > 0]
    for nd in nodes:
        if kinds.get(nd) == 'species' and isinstance(refv.get(nd), float) and refv[nd] <= 0:
            refv[nd] = float(np.median(_pos)) if _pos else 1.0
    arcs = influence_arcs(nodes, rids, N, rsign, rule_syms, gsign, flags.get('_reversible'),
                          root_test=lambda rid, var: rate_has_positive_root(rr, flags, rid, var, refv))
    arcs_nr = [a for a in arcs if not (a[0] == a[1] and a[3] < 0)]  # reference 24 omits negative self-loops
    out.update(nodes=len(nodes), arcs=len(arcs), negative_selfloops_kept=len(arcs) - len(arcs_nr),
               sign_states=getattr(derivative_signs, 'states_used', None))
    if not arcs:
        out.update(status='no influence arcs', seconds=round(time.time() - t0, 2))
        return out
    cls, reverse = reaction_classes(N, rids)
    active = [i for i in range(N.shape[0]) if np.any(N[i])]
    sup_active, inv_ok = p_invariant_supports(N[active]) if active else ([], True)
    supports = [frozenset(active[i] for i in sp) for sp in sup_active]
    out['conservation_laws'] = len(supports) if inv_ok else None
    n = len(nodes)
    out['plain_negative'] = has_negative_circuit(n, arcs_nr)
    import elim
    uniq = [(a, b, f'u{q}', s_) for q, (a, b, _, s_) in enumerate(arcs_nr)]
    pp = elim.positive_circuit_exists(n, uniq, {}, [])
    out['plain_positive'] = pp if pp is not None else exists(n, arcs_nr, '+', False, {}, [])
    carcs = [(a, b, cls.get(l, l), s_) for a, b, l, s_ in arcs_nr]
    rp = elim.positive_circuit_exists(n, carcs, reverse, supports if inv_ok else [])
    out['refined_positive'] = rp if rp is not None else exists(n, carcs, '+', True, reverse, supports if inv_ok else [])
    found, complete = circuits(n, arcs, True, reverse, supports if inv_ok else [], cls=cls)
    out['refined_labelled_circuits'] = len(found)
    out['refined_complete'] = complete
    rid_index = {r: j for j, r in enumerate(rids)}
    idx = {v: i for i, v in enumerate(nodes)}

    def column(lab):
        if lab.startswith('R:'):
            return N[:, rid_index[lab[2:]]]
        col = np.zeros(n); col[idx[lab[5:]]] = 1.0  # rate rule: unit gain on its own variable
        return col

    def degenerate(nd, labs):
        """Reference 24's rank condition (Theorem 2.2, condition 2, read at the circuit): the
        reactions on a circuit must have linearly independent net stoichiometry columns. This
        removes 1:1 state cycles, a reaction and its reverse, and reactions with identical
        stoichiometry, and keeps autocatalytic cycles with non-unit gain."""
        M = np.array([column(l) for l in labs]).T
        return np.linalg.matrix_rank(M, tol=1e-9 * max(1.0, float(np.abs(M).max()))) < len(labs)

    loops, degen = {}, set()
    for nd, labs, sg in found:  # distinct node cycles with sign, from a canonical rotation
        k = min(range(len(nd)), key=lambda i: nd[i])
        key = (nd[k:] + nd[:k], sg)
        d = degenerate(nd, labs)
        if key not in loops:
            loops[key] = labs
            if d:
                degen.add(key)
        elif not d:
            degen.discard(key)  # some realisation of this loop is non-degenerate
    # structural integrators: the variable's own name appears in none of the laws that change it
    deps, rdeps = flags.get('_deps', {}), flags.get('_rule_deps', {})
    integ = set()
    for i, v in enumerate(nodes):
        laws = [deps.get(r, set()) for jx, r in enumerate(rids) if N[i, jx] != 0]
        if v in rdeps:
            laws.append(rdeps[v])
        if laws and all(v not in d for d in laws):
            integ.add(i)
    fb = [(list(k[0]), k[1]) for k in loops if k not in degen]

    def metrics(cycles, done, labmap):
        if not done:
            return {'complete': False, 'c_at_least': len(cycles)}
        types = {'n_pos': 0, 'n_pos_int': 0, 'n_neg': 0, 'n_neg_int': 0}
        for nd, s_ in cycles:
            types[('n_pos' if s_ > 0 else 'n_neg') + ('_int' if set(nd) & integ else '')] += 1
        la = []
        for nd, s_ in cycles:
            labs = labmap[(tuple(nd), s_)]
            la.append({(nd[i], nd[(i + 1) % len(nd)], labs[i]) for i in range(len(nd))})
        use = {}
        for x in la:
            for a in x:
                use[a] = use.get(a, 0) + 1
        nu_, E_, N_, C_ = cyclomatic(list(use))
        return {'complete': True, 'c': len(cycles), 'k': sum(1 for _, s_ in cycles if s_ < 0),
                'j': sum(1 for nd, _ in cycles if set(nd) & integ), 'types': types,
                'cactus': all(v == 1 for v in use.values()), 'k_pf': pf_filtered(la, [s_ for _, s_ in cycles]),
                'nu_core': nu_}
    found_p, complete_p = circuits(n, arcs, False, {}, [])
    plain = {}
    for nd, labs, sg in found_p:
        k = min(range(len(nd)), key=lambda i: nd[i])
        plain.setdefault((nd[k:] + nd[:k], sg), labs[k:] + labs[:k])
    lab24, lab_ok = {}, set()
    for nd, labs, sg in found:
        k = min(range(len(nd)), key=lambda i: nd[i])
        key = (nd[k:] + nd[:k], sg)
        good = not degenerate(nd, labs)
        if key not in lab24 or (good and key not in lab_ok):
            lab24[key] = labs[k:] + labs[:k]
            if good:
                lab_ok.add(key)
    defs = {'thomas': metrics([(list(k[0]), k[1]) for k in plain], complete_p, plain),
            'ref24': metrics([(list(k[0]), k[1]) for k in loops], complete, lab24),
            'ref24_rank': metrics(fb, complete, lab24)}
    out['defs'] = defs
    m = defs['ref24_rank']
    c = len(fb)
    loop_list = fb
    out.update(loops_filtered=len(loops) if complete else None, degenerate_cycles=len(degen) if complete else None,
               loops=m.get('c'), loops_at_least=c, negative=m.get('k'), integrating=m.get('j'), k_pf=m.get('k_pf'),
               types=m.get('types'), cactus=m.get('cactus'), nu_core=m.get('nu_core'),
               integrator_nodes=len(integ & {v for nd, _ in fb for v in nd}))
    if complete and c <= 12:
        out['loop_list'] = [{'nodes': [nodes[v] for v in nd], 'sign': '+' if s_ > 0 else '-',
                             'integrates': bool(set(nd) & integ)} for nd, s_ in loop_list]
    out['status'] = 'ok'
    out['seconds'] = round(time.time() - t0, 2)
    return out


def run_all(folder, out_file, jobs, timeout):
    files = sorted(pathlib.Path(folder).glob('*.xml'))
    me = pathlib.Path(__file__).resolve()

    def one(f):
        try:
            p = subprocess.run([sys.executable, str(me), '--one', str(f), '--signs', SIGN_MODE], capture_output=True, text=True, timeout=timeout)
            line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
            return json.loads(line) if line.startswith('{') else {'model': f.stem, 'status': 'error', 'error': (p.stderr or '')[-300:]}
        except subprocess.TimeoutExpired:
            return {'model': f.stem, 'status': 'timeout'}
    with ThreadPoolExecutor(jobs) as ex, open(out_file, 'w') as fh:
        for i, r in enumerate(ex.map(one, files)):
            fh.write(json.dumps(r) + '\n'); fh.flush()
            if (i + 1) % 50 == 0:
                print(f'{i + 1}/{len(files)}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--one'); ap.add_argument('--all'); ap.add_argument('--out')
    ap.add_argument('--jobs', type=int, default=8); ap.add_argument('--timeout', type=int, default=180)
    ap.add_argument('--signs', choices=['trajectory', 'random'], default='trajectory')
    a = ap.parse_args()
    SIGN_MODE = a.signs
    if a.one:
        try:
            print(json.dumps(analyze(a.one)))
        except Exception as e:
            print(json.dumps({'model': pathlib.Path(a.one).stem, 'status': 'error', 'error': repr(e)[:300]}))
    else:
        run_all(a.all, a.out, a.jobs, a.timeout)
