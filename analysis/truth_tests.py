"""Three truth tests of the loop theory on the BioModels census (release 31).

1. Rules.  Memory needs an amplifying loop; a sustained rhythm needs a braking loop. Checked on every autonomous
           model from the census's own sign graph (plain and refined), independently of the census summary.
2. Gain.   Topology permits, strength decides. A clock built from one braking loop of n stages can only lose its
           steady state if the loop gain G = prod |J[b,a]| / prod |J[i,i]| exceeds sec(pi/n)^n (Thron 1991).
           A memory built from one amplifying loop needs a steady state with G > 1 (where det(-J) changes sign).
           G is read at the model's own steady states; controls are one-loop models that do not tick or remember.
3. Capability.
           a. Models of the same system at different detail: do they agree on what they can do (keep time, hold
              states, settle) where their loop counts disagree?
           b. Step and return: in every settling autonomous model, raise each global parameter by 20% and look for a
              variable that moves by more than 5% and comes back to within 0.5% of where it was while others stay
              moved. That is exact adaptation, found from behaviour rather than read from the equations.

Usage: .venv/bin/python analysis/truth_tests.py            all tests, writes results/truth_tests.json
       .venv/bin/python analysis/truth_tests.py --one KIND MODEL    one model (used by the driver; JSON to stdout)
"""
import concurrent.futures as cf
import json
import math
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
DATA = ROOT / 'data' / 'r31_curated'
OUT = ROOT / 'results' / 'truth_tests.json'
STEP, MOVE, BACK, OTHERS = 0.2, 0.05, 0.005, 0.05

# models drawn of one system at different detail, or alternative models of one phenomenon (named in the census)
FAMILIES = {
    'fruit fly day clock': ['BIOMD0000000016', 'BIOMD0000000036', 'BIOMD0000000021', 'BIOMD0000000298', 'BIOMD0000000171'],
    'Tyson 1991 cell cycle, 6 and 2 variables': ['BIOMD0000000005', 'BIOMD0000000006'],
    'Morris-Lecar muscle fibre, full and reduced': ['BIOMD0000000324', 'BIOMD0000000280'],
    'Singh 2006 TCA cycle, two versions': ['BIOMD0000000219', 'BIOMD0000000218'],
    'Smallbone 2013 colon crypt, versions 0 to 3': ['BIOMD0000000520', 'BIOMD0000000519', 'BIOMD0000000518', 'BIOMD0000000517'],
    'Borghans 1997 calcium oscillations, models 1 to 3': ['BIOMD0000000043', 'BIOMD0000000044', 'BIOMD0000000045'],
}


# ---------------------------------------------------------------- shared
def setup(mid, promote=False):
    """The census's own loader; with promote, local reaction parameters become global so a step can reach them."""
    import libsbml
    import roadrunner
    import dynamics as DY
    path = DATA / f'{mid}.xml'
    if promote:
        doc = libsbml.readSBMLFromFile(str(path))
        props = libsbml.ConversionProperties(); props.addOption('promoteLocalParameters', True)
        doc.convert(props)
        roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
        rr = roadrunner.RoadRunner(libsbml.writeSBMLToString(doc))
        try:
            rr.integrator.relative_tolerance = 1e-8; rr.integrator.absolute_tolerance = 1e-12; rr.integrator.maximum_num_steps = 200000
        except Exception:
            pass
        m = doc.getModel()
    else:
        rr = DY.load(path)
        m = libsbml.readSBMLFromFile(str(path)).getModel()
    assigned = {m.getRule(i).getVariable() for i in range(m.getNumRules()) if m.getRule(i).isAssignment()}
    rate_vars = [m.getRule(i).getVariable() for i in range(m.getNumRules()) if m.getRule(i).isRate()]
    species = [s for s in rr.model.getFloatingSpeciesIds() if s not in assigned]
    ids = species + [v for v in rate_vars if v not in species]
    spset = set(species)
    x0 = np.array([rr.getValue(DY.sel(s, spset)) for s in ids], dtype=float)
    return DY, rr, ids, spset, x0, assigned, rate_vars


def rhs(rr, DY, ids, spset, x):
    """Rates of change of the state variables at x (species as concentrations, rate-rule variables as written)."""
    DY.put_state(rr, ids, spset, x)
    a = rr.getRatesOfChangeNamedArray()
    named = {c.rstrip("'"): float(v) for c, v in zip(a.colnames, a[0])}
    out = np.zeros(len(ids))
    for k, s in enumerate(ids):
        if s in named:
            v = named[s]
            if s in spset:  # amount rate to concentration rate
                try:
                    conc = rr.getValue('[' + s + ']'); amt = rr.getValue(s)
                    if conc and amt:
                        v = v * conc / amt
                except Exception:
                    pass
            out[k] = v
    return out


def jacobian(rr, DY, ids, spset, x):
    f0 = rhs(rr, DY, ids, spset, x)
    J = np.zeros((len(ids), len(ids)))
    scale = np.maximum(np.abs(x), 1e-6 * (np.abs(x).max() or 1.0))
    for i in range(len(ids)):
        h = 1e-6 * scale[i]
        xp, xm = x.copy(), x.copy()
        xp[i] += h; xm[i] -= h
        J[:, i] = (rhs(rr, DY, ids, spset, xp) - rhs(rr, DY, ids, spset, xm)) / (2 * h)
    return J, f0


def steady_from(rr, DY, ids, spset, x):
    from scipy.optimize import root
    sol = root(lambda z: rhs(rr, DY, ids, spset, z), x, method='hybr', options={'maxfev': 800})
    f = rhs(rr, DY, ids, spset, sol.x)
    ok = np.all(np.isfinite(sol.x)) and np.max(np.abs(f)) <= 1e-6 * max(1.0, np.max(np.abs(sol.x)))
    return sol.x, bool(ok)


def loop_gain(J, idx, nodes):
    diag, off = [], []
    for i in range(len(nodes)):
        a, b = idx.get(nodes[i]), idx.get(nodes[(i + 1) % len(nodes)])
        if a is None or b is None:
            return None, 'node not a state variable'
        diag.append(J[a, a]); off.append(J[b, a])
    if any(d >= 0 for d in diag):
        return None, 'a loop node has no decay of its own'
    if any(o == 0 for o in off):
        return None, 'an arrow is zero here'
    return float(np.prod(np.abs(off)) / np.prod(np.abs(diag))), ''


def secant(n):
    return math.inf if n <= 2 else (1 / math.cos(math.pi / n)) ** n


# ---------------------------------------------------------------- per-model work
def one_gain(mid, loop):
    DY, rr, ids, spset, x0, *_ = setup(mid)
    idx = {s: i for i, s in enumerate(ids)}
    # a point near the steady state: the time-average of the model's own run, then a root solve
    DY.put_state(rr, ids, spset, x0)
    try:
        r = np.array(rr.simulate(0, 1000, 4001, [DY.sel(s, spset) for s in ids]))
        guess = r[len(r) // 2:].mean(axis=0)
    except Exception:
        guess = x0
    xs, ok = steady_from(rr, DY, ids, spset, guess)
    if not ok:
        return {'model': mid, 'status': 'no steady state found'}
    J, _ = jacobian(rr, DY, ids, spset, xs)
    G, why = loop_gain(J, idx, loop['nodes'])
    ev = np.linalg.eigvals(J)
    return {'model': mid, 'status': 'ok', 'n': len(loop['nodes']), 'G': G, 'why': why, 'threshold': secant(len(loop['nodes'])),
            'unstable': bool(np.max(ev.real) > 1e-9 * max(1, np.abs(ev).max()))}


def one_memory(mid, loop):
    """All steady states reachable by root solves from the model's spread starts; G at each."""
    DY, rr, ids, spset, x0, *_ = setup(mid)
    idx = {s: i for i, s in enumerate(ids)}
    try:
        S = rr.getFullStoichiometryMatrix(); rows = {s: i for i, s in enumerate(S.rownames)}
        N = np.array([np.array(S[rows[s]]) if s in rows else np.zeros(S.shape[1]) for s in ids])
    except Exception:
        N = np.zeros((len(ids), 0))
    starts = [x0] + DY.spread_starts(x0, N, 11, 0)
    stable = []
    for st in starts:            # the stable states: where the model's own runs settle
        r = DY.run_from(rr, ids, st, spset)
        if r['kind'] == 'steady':
            xs = np.array(r['state'])
            if not any(np.allclose(xs, y, rtol=1e-3, atol=1e-9) for y in stable):
                stable.append(xs)
    found = list(stable)

    def basin(x):
        r = DY.run_from(rr, ids, x, spset)
        if r['kind'] != 'steady':
            return None
        e = np.array(r['state'])
        d = [np.max(np.abs(e - y) / np.maximum(np.abs(y), 1e-9 * (np.abs(y).max() or 1.0))) for y in stable]
        return int(np.argmin(d)) if min(d) < 1e-2 else None
    for i, a in enumerate(stable):   # the tipping point: bisect the line between two stable states to the boundary
        for j in range(i + 1, len(stable)):                     # between their basins, then follow the run that
            b = stable[j]                                       # lingers there and solve from its slowest point
            lo, hi = 0.0, 1.0
            if basin(a) != i or basin(b) != j:
                continue
            for _ in range(30):
                t = (lo + hi) / 2
                k = basin(a + t * (b - a))
                if k == i:
                    lo = t
                elif k == j:
                    hi = t
                else:
                    break
            edge = a + (lo + hi) / 2 * (b - a)
            DY.put_state(rr, ids, spset, edge)
            try:
                tr = np.array(rr.simulate(0, 200, 2001, [DY.sel(s, spset) for s in ids]))
                speeds = [np.max(np.abs(rhs(rr, DY, ids, spset, z))) for z in tr[::20]]
                guess = tr[::20][int(np.argmin(speeds))]
            except Exception:
                guess = edge
            for g in (guess, edge):
                xs, ok = steady_from(rr, DY, ids, spset, g)
                if ok and np.all(xs >= -1e-9) and not any(np.allclose(xs, y, rtol=1e-3, atol=1e-9) for y in found):
                    found.append(xs)
                    break
    out = []
    for xs in found:
        J, _ = jacobian(rr, DY, ids, spset, xs)
        G, why = loop_gain(J, idx, loop['nodes'])
        ev = np.linalg.eigvals(J)
        out.append({'G': G, 'why': why, 'unstable': bool(np.max(ev.real) > 1e-9 * max(1, np.abs(ev).max()))})
    return {'model': mid, 'status': 'ok', 'steady_states': out}


def one_step(mid):
    DY, rr, ids, spset, x0, assigned, rate_vars = setup(mid, promote=True)
    base = DY.run_from(rr, ids, x0, spset)
    if base['kind'] != 'steady':
        return {'model': mid, 'status': 'baseline not steady: ' + base['kind']}
    xs = np.array(base['state']); T = float(min(max(3 * base['T'], 100.0), 1e5))
    params = [p for p in rr.model.getGlobalParameterIds() if p not in assigned and p not in rate_vars]
    hits, tried = [], 0
    for p in params:
        try:
            DY.put_state(rr, ids, spset, xs)
            v = rr.getValue(p)
            if not v or not np.isfinite(v):
                continue
            rr.setValue(p, v * (1 + STEP))
            y = np.array(rr.simulate(0, T, 2001, [DY.sel(s, spset) for s in ids]))
        except Exception:
            continue
        tried += 1
        if not np.all(np.isfinite(y)):
            continue
        tail = y[int(0.8 * len(y)):]
        level = np.maximum(np.abs(xs), 1e-9 * (np.abs(xs).max() or 1.0))
        settled = np.all(np.ptp(tail, axis=0) <= 1e-4 * np.maximum(np.abs(tail).mean(axis=0), 1e-12) + 1e-12)
        if not settled:
            continue
        peak = np.max(np.abs(y - xs), axis=0) / level
        final = np.abs(y[-1] - xs) / level
        moved = final > OTHERS
        for k, s in enumerate(ids):
            if abs(xs[k]) > 1e-9 * (np.abs(xs).max() or 1.0) and peak[k] > MOVE and final[k] < BACK and moved.any():
                hits.append({'parameter': p, 'variable': s, 'peak': round(float(peak[k]), 3), 'final': round(float(final[k]), 5)})
    return {'model': mid, 'status': 'ok', 'parameters_tried': tried, 'exact_returns': hits}


# ---------------------------------------------------------------- driver
def run_one(kind, mid, arg=None, timeout=300):
    cmd = [sys.executable, str(pathlib.Path(__file__)), '--one', kind, mid] + ([json.dumps(arg)] if arg is not None else [])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'PATH': '/usr/bin:/bin'})
        line = [l for l in p.stdout.splitlines() if l.startswith('{')]
        return json.loads(line[-1]) if line else {'model': mid, 'status': 'error: ' + p.stderr.strip()[-160:]}
    except subprocess.TimeoutExpired:
        return {'model': mid, 'status': f'timeout after {timeout} s'}


def main():
    S = {json.loads(l)['model']: json.loads(l) for l in open(ROOT / 'results' / 'r31_structure_traj.jsonl')}
    D = {json.loads(l)['model']: json.loads(l) for l in open(ROOT / 'results' / 'r31_dynamics.jsonl')}
    auto = [m for m, d in D.items() if d.get('status') == 'ok' and not d.get('forced') and d.get('behaviours')]
    res = {'settings': {'step': STEP, 'moves_more_than': MOVE, 'returns_within': BACK, 'others_stay_moved_by': OTHERS}}

    # 1. rules
    rules = {'autonomous': len(auto), 'memory': 0, 'memory_without_amplifying_loop': [], 'clock': 0, 'clock_without_braking_loop': []}
    for m in auto:
        b, d = D[m]['behaviours'], S.get(m, {})
        if 'multistable' in b:
            rules['memory'] += 1
            if not (d.get('plain_positive') or d.get('refined_positive')):
                rules['memory_without_amplifying_loop'].append(m)
        if 'oscillating' in b:
            rules['clock'] += 1
            if not d.get('plain_negative'):
                rules['clock_without_braking_loop'].append(m)
    res['rules'] = rules
    print('rules', {k: (v if not isinstance(v, list) else len(v)) for k, v in rules.items()}, flush=True)

    one_loop = lambda m, sign: S.get(m, {}).get('loop_list') and len(S[m]['loop_list']) == 1 and S[m]['loop_list'][0]['sign'] == sign
    jobs = []
    with cf.ThreadPoolExecutor(8) as ex:
        # 2. gain: one-brake clocks and one-brake models that do not tick
        clocks = [m for m in auto if one_loop(m, '-') and 'oscillating' in D[m]['behaviours']]
        quiet = [m for m in auto if one_loop(m, '-') and 'oscillating' not in D[m]['behaviours']]
        mems = [m for m in auto if one_loop(m, '+') and 'multistable' in D[m]['behaviours']]
        single = [m for m in auto if one_loop(m, '+') and 'multistable' not in D[m]['behaviours']]
        f_clock = {m: ex.submit(run_one, 'gain', m, S[m]['loop_list'][0]) for m in clocks + quiet}
        f_mem = {m: ex.submit(run_one, 'memory', m, S[m]['loop_list'][0]) for m in mems + single}
        # 3b. step and return on every settling autonomous model
        settle = [m for m in auto if 'steady' in D[m]['behaviours'] and 'oscillating' not in D[m]['behaviours']]
        f_step = {m: ex.submit(run_one, 'step', m, None, 600) for m in settle}
        res['gain_brake'] = [dict(f_clock[m].result(), ticks=m in clocks, name=S[m]['name']) for m in clocks + quiet]
        print('gain: brake done', flush=True)
        res['gain_amplify'] = [dict(f_mem[m].result(), memory=m in mems, name=S[m]['name']) for m in mems + single]
        print('gain: amplify done', flush=True)
        res['step'] = []
        for m in settle:
            r = f_step[m].result()
            d = S.get(m, {})
            r.update(name=d.get('name'), loops=d.get('loops'), running_totals=d.get('integrating'))
            res['step'].append(r)
        print('step done', flush=True)

    # 3a. families
    fam = {}
    for f, ms in FAMILIES.items():
        rows = []
        for m in ms:
            d, y = S.get(m, {}), D.get(m, {})
            step = next((r for r in res['step'] if r['model'] == m), None)
            rows.append({'model': m, 'name': d.get('name'), 'loops': d.get('loops'), 'brakes': d.get('negative'),
                         'running_totals': d.get('integrating'), 'forced': y.get('forced'), 'behaviours': y.get('behaviours'),
                         'exact_return': (bool(step['exact_returns']) if step and step.get('status') == 'ok' else None)})
        fam[f] = rows
    res['families'] = fam
    OUT.write_text(json.dumps(res, indent=1))
    print('wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    if '--one' in sys.argv:
        i = sys.argv.index('--one')
        kind, mid = sys.argv[i + 1], sys.argv[i + 2]
        arg = json.loads(sys.argv[i + 3]) if len(sys.argv) > i + 3 else None
        try:
            out = {'gain': lambda: one_gain(mid, arg), 'memory': lambda: one_memory(mid, arg), 'step': lambda: one_step(mid)}[kind]()
        except Exception as e:
            out = {'model': mid, 'status': 'error: ' + repr(e)[:160]}
        print(json.dumps(out, default=float))
    else:
        main()
