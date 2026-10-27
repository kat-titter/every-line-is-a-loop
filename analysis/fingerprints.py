"""The atlas: sort circuits by how they answer a push, not by how they are wired.

For each autonomous model in release 31, settle it, then push it four standard ways and read the shape of the answer:
  1. step: raise one parameter 20% and hold; how far the most moved molecule peaks, and how far back it comes
  2. ramp: walk the same parameter from a quarter to four times its value and back; a gap between the two paths is
     memory (hysteresis)
  3. rhythm: the linear frequency response of that molecule to that parameter, from the Jacobian at the steady state,
     which is what a small sine sweep measures; no answer to slow change means exact return, a peak means ringing
  4. baseline: a model that ticks on its own is filed as ticking before any push
A model can answer differently on different (parameter, molecule) pairs; it is filed by the most telling
answer it can give, in this order: ticks, remembers, returns exactly (on any pair), then its biggest answer's shape.
The answer files the model in one row: ticks, remembers, returns exactly, returns partly, rings, follows (or flat, if
no parameter moves anything). Each row lists the loop addresses (loops, brakes, running totals) of its members, so the
atlas shows how many wirings make the same answer. Writes results/fingerprints.json.
Usage: .venv/bin/python analysis/fingerprints.py [--one MODEL [PARAM SPECIES]]"""
import concurrent.futures as cf, json, pathlib, subprocess, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))

STEP, MOVE, BACK, MEMORY = 0.2, 0.05, 0.005, 0.05     # step size; peak that counts as moved; exact return; memory gap
MAX_PARAMS = 40                                          # parameters scanned for the input, in name order
RAMP = 2.0 ** np.linspace(-2, 2, 9)                      # a quarter to four times the parameter's own value


def rhs_at(rr, DY, ids, spset, x, p=None, val=None):
    """Rates of change at state x, with parameter p set to val (the census's rhs, plus one parameter)."""
    DY.put_state(rr, ids, spset, x)
    if p is not None:
        rr.setValue(p, val)
    a = rr.getRatesOfChangeNamedArray()
    named = {c.rstrip("'"): float(v) for c, v in zip(a.colnames, a[0])}
    out = np.zeros(len(ids))
    for k, s in enumerate(ids):
        if s in named:
            v = named[s]
            if s in spset:
                try:
                    conc, amt = rr.getValue('[' + s + ']'), rr.getValue(s)
                    if conc and amt:
                        v = v * conc / amt
                except Exception:
                    pass
            out[k] = v
    return out


def step(rr, DY, ids, spset, xs, p, v, T):
    DY.put_state(rr, ids, spset, xs)
    rr.setValue(p, v * (1 + STEP))
    return np.array(rr.simulate(0, T, 801, [DY.sel(s, spset) for s in ids]))


def ramp_gap(rr, DY, ids, spset, xs, p, v, k, T):
    """Largest gap between the up and down paths of molecule k, relative to its largest value."""
    DY.put_state(rr, ids, spset, xs)
    sel, t, up, down, ups, downs = [DY.sel(s, spset) for s in ids], 0.0, [], [], [], []
    for f in list(RAMP) + list(RAMP[::-1][1:]):
        rr.setValue(p, v * f)
        y = np.array(rr.simulate(t, t + T, 201, sel)); t += T
        if not np.all(np.isfinite(y)):
            return None
        if len(up) < len(RAMP):
            up.append(float(y[-1, k])); ups.append(y[-1])
        else:
            down.append(float(y[-1, k])); downs.append(y[-1])
    down, downs = down[::-1] + [up[-1]], downs[::-1] + [ups[-1]]
    top = max(max(map(abs, up)), max(map(abs, down)), 1e-12)
    gaps = [abs(a - b) / top for a, b in zip(up, down)]
    i = int(np.argmax(gaps))
    if gaps[i] <= MEMORY:
        return gaps[i]
    # memory means two states that both hold still at the same setting: run each for 3T more and require no drift
    for x in (ups[i], downs[i]):
        DY.put_state(rr, ids, spset, x); rr.setValue(p, v * RAMP[i])
        z = np.array(rr.simulate(0, 3 * T, 301, sel))
        if not np.all(np.isfinite(z)) or np.max(np.abs(z[-1] - x) / np.maximum(np.abs(x), 1e-9 * (np.abs(x).max() or 1.0))) > 1e-3:
            return 0.0
    return gaps[i]


def rhythm(rr, DY, ids, spset, xs, p, v, k):
    """|G(w)| of molecule k to parameter p over frequencies spanning the model's own rates."""
    import truth_tests as TT
    J, _ = TT.jacobian(rr, DY, ids, spset, xs)
    h = 1e-4 * abs(v)
    b = (rhs_at(rr, DY, ids, spset, xs, p, v + h) - rhs_at(rr, DY, ids, spset, xs, p, v - h)) / (2 * h)
    lam = np.abs(np.linalg.eigvals(J)); lam = lam[lam > 1e-12]
    if not len(lam) or not np.all(np.isfinite(J)):
        return None
    w = np.logspace(np.log10(0.01 * lam.min()), np.log10(100 * lam.max()), 60)
    n = len(ids)
    g = np.array([abs(np.linalg.solve(1j * wi * np.eye(n) - J, b)[k]) for wi in w])
    if not np.all(np.isfinite(g)) or g.max() <= 0:
        return None
    i = int(np.argmax(g))
    return {'dc': float(g[0] / g.max()), 'peak': float(g.max() / max(g[0], 1e-300)), 'peak_at': i / (len(w) - 1),
            'curve': [round(float(x / g.max()), 4) for x in g[::4]]}


def one(mid, inp=None, out=None):
    import truth_tests as TT
    D = {}
    for l in open(ROOT / 'results' / 'r31_dynamics.jsonl'):
        r = json.loads(l)
        if r['model'] == mid:
            D = r
    continuum = 'continuum' in (D.get('behaviours') or [])
    DY, rr, ids, spset, x0, assigned, rate_vars = TT.setup(mid, promote=True)
    base = DY.run_from(rr, ids, x0, spset)
    if base['kind'] == 'oscillating':
        return {'model': mid, 'status': 'ok', 'row': 'ticks', 'why': 'ticks before any push'}
    if base['kind'] != 'steady':
        return {'model': mid, 'status': 'baseline ' + base['kind']}
    xs = np.array(base['state']); T = float(min(max(3 * base['T'], 100.0), 1e5))
    level = np.maximum(np.abs(xs), 1e-9 * (np.abs(xs).max() or 1.0))
    params = [p for p in sorted(rr.model.getGlobalParameterIds()) if p not in assigned and p not in rate_vars]
    if inp:
        params = [inp]
    best, exact = None, []
    for p in params[:MAX_PARAMS]:
        try:
            v = rr.getValue(p)
            if not v or not np.isfinite(v):
                continue
            y = step(rr, DY, ids, spset, xs, p, v, T)
        except Exception:
            continue
        if not np.all(np.isfinite(y)):
            continue
        peak = np.max(np.abs(y - xs), axis=0) / level
        peak[np.abs(xs) <= 1e-9 * (np.abs(xs).max() or 1.0)] = 0
        tail = y[int(0.8 * len(y)):]
        if np.all(np.ptp(tail, axis=0) <= 1e-4 * np.maximum(np.abs(tail).mean(axis=0), 1e-12) + 1e-12):
            final = np.abs(y[-1] - xs) / level
            if (final > MOVE).any():   # the step moved something for good, so a return is a real answer
                exact += [(p, ids[j]) for j in range(len(ids)) if peak[j] > MOVE and final[j] < BACK]
        k = ids.index(out) if out else int(np.argmax(peak))
        if best is None or peak[k] > best[2]:
            best = (p, k, float(peak[k]), y, v)
    if best is None:
        return {'model': mid, 'status': 'no parameter could be stepped'}
    p, k, pk, y, v = best
    rec = {'model': mid, 'status': 'ok', 'input': p, 'output': ids[k], 'step_peak': round(pk, 4),
           'exact_pairs': [list(e) for e in exact[:5]], 'exact_count': len(exact)}
    if pk < MOVE:
        return dict(rec, row='flat', why='no 20% step moves any molecule by 5%')
    z = y[:, k]; fin = abs(z[-1] - xs[k]) / level[k]
    tail = z[int(0.8 * len(z)):]
    settled = np.ptp(tail) <= 1e-4 * max(abs(tail.mean()), 1e-12) + 1e-12
    d = z - z[-1]; big = np.abs(d) > 1e-3 * (abs(z[-1]) + 1e-9); sg = np.sign(d[big])
    crossings = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
    off = np.where(np.abs(d) > 0.05 * pk * level[k])[0]
    rec.update(step_final=round(float(fin), 5), crossings=crossings,
               settle=round(float((off[-1] + 1) / len(z)) if len(off) else 0.0, 3), settled=bool(settled))
    gap = None
    try:
        gap = ramp_gap(rr, DY, ids, spset, xs, p, v, k, T)
    except Exception:
        pass
    rec['ramp_gap'] = None if gap is None else round(gap, 4)
    try:
        rec['rhythm'] = rhythm(rr, DY, ids, spset, xs, p, v, k)
    except Exception:
        rec['rhythm'] = None
    rh = rec['rhythm'] or {}
    half = z[len(z) // 2:]
    pks = [i for i in range(1, len(half) - 1) if half[i] > half[i - 1] and half[i] >= half[i + 1]]
    amps = [half[i] - half.min() for i in pks]
    ticking = (not settled and len(pks) >= 3 and amps[-1] >= 0.9 * amps[0]
               and np.ptp(half) / max(abs(half.mean()), 1e-12) > 1e-3)
    rec['sustained_peaks'] = len(pks) if ticking else 0
    if ticking:
        row, why = 'ticks', 'the push starts it ticking'
    elif not settled:
        return dict(rec, status='still drifting after the step')
    elif gap is not None and gap > MEMORY and not continuum:
        row, why = 'remembers', f'up and down paths differ by {gap:.0%}'
    elif fin < BACK or exact:
        row, why = 'returns exactly', 'some molecule comes back within 0.5% while others stay moved'
    elif fin < 0.5 * pk:
        row, why = 'returns partly', 'peaks, then comes back part way'
    elif crossings >= 2 or (rh.get('peak', 1) > 1.25 and 0.05 < rh.get('peak_at', 0) < 0.95):
        row, why = 'rings', 'overshoots, or answers one speed of rhythm best'
    else:
        row, why = 'follows', 'moves with the push and stays'
    return dict(rec, row=row, why=why)


def run_one(mid, args=(), timeout=240):
    cmd = [sys.executable, str(pathlib.Path(__file__)), '--one', mid, *args]
    env = {'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'PATH': '/usr/bin:/bin'}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        line = [l for l in r.stdout.splitlines() if l.startswith('{')]
        return json.loads(line[-1]) if line else {'model': mid, 'status': 'error: ' + r.stderr.strip()[-160:]}
    except subprocess.TimeoutExpired:
        return {'model': mid, 'status': f'timeout after {timeout} s'}


ROWS = ['ticks', 'remembers', 'returns exactly', 'returns partly', 'rings', 'follows']


def main(jobs=8):
    S = {}
    for l in open(ROOT / 'results' / 'r31_structure_traj.jsonl'):
        r = json.loads(l)
        if 'defs' in r:
            S[r['model']] = r
    D = {json.loads(l)['model']: json.loads(l) for l in open(ROOT / 'results' / 'r31_dynamics.jsonl')}
    auto = sorted(m for m, d in D.items() if d.get('status') == 'ok' and not d.get('forced') and d.get('behaviours'))
    print(len(auto), 'autonomous models', flush=True)
    with cf.ThreadPoolExecutor(jobs) as ex:
        res = list(ex.map(run_one, auto))
    # the check that can fail: yeast osmo-adaptation, salt outside in, nuclear Hog1 out (Muzzey 2009: exact return)
    check = [dict(protocol_check(m, o, a, b, sv), expect=why) for m, o, a, b, sv, why in CHECKS]
    atlas = {r: [] for r in ROWS + ['flat']}
    for r in res:
        if r.get('status') == 'ok':
            a = S.get(r['model'], {}).get('defs', {}).get('ref24_rank', {})
            r['address'] = [a.get('c'), a.get('k'), a.get('j')] if a.get('complete') and a.get('c') is not None and a['c'] <= 3 else None
            r['census'] = D[r['model']]['behaviours']
            atlas[r['row']].append(r['model'])
    out = {'settings': {'step': STEP, 'moved': MOVE, 'exact': BACK, 'memory_gap': MEMORY, 'params_scanned': MAX_PARAMS},
           'models': res, 'rows': {k: len(v) for k, v in atlas.items()}, 'checks': check}
    (ROOT / 'results' / 'fingerprints.json').write_text(json.dumps(out, indent=1))
    print('rows', out['rows'], flush=True)
    for c in check:
        print('check', c['model'], {k: c.get(k) for k in ('output', 'peak', 'final', 'row', 'solver_stopped_at')}, flush=True)


def protocol_check(mid, out, t_pre, t_end, set_values=None, chunk=None):
    """Run a model's own input protocol and read molecule `out` just before its step (t_pre), at its peak and at
    t_end. Simulated in chunks so a solver failure keeps what came before it."""
    import dynamics as DY
    rr = DY.load(ROOT / 'data' / 'r31_curated' / f'{mid}.xml')
    for k, v in (set_values or {}).items():
        rr.setValue(k, v)
    chunk = chunk or (t_end / 100)
    t, rows, stopped = 0.0, [], None
    while t < t_end:
        try:
            y = np.array(rr.simulate(t, t + chunk, 21, ['time', out])); rows.extend(y[1:].tolist()); t += chunk
        except Exception as e:
            stopped = round(t, 1); break
    y = np.array(rows); tt, z = y[:, 0], y[:, 1]
    pre = float(z[tt <= t_pre][-1]); after = z[tt > t_pre]
    peak = float(np.max(np.abs(after - pre)) / max(abs(pre), 1e-12)); fin = float(abs(z[-1] - pre) / max(abs(pre), 1e-12))
    complete = stopped is None
    row = ('returns exactly' if fin < BACK and peak > MOVE else 'returns partly' if fin < 0.5 * peak else 'follows') if complete else 'inconclusive'
    return {'model': mid, 'output': out, 'pre': pre, 'peak': round(peak, 4), 'final': round(fin, 5), 'row': row,
            'solver_stopped_at': stopped, 'last_time': round(float(tt[-1]), 1),
            'trace': [[round(float(a), 2), round(float(b) / pre, 4)] for a, b in zip(tt[::max(1, len(tt) // 120)], z[::max(1, len(tt) // 120)])]}


CHECKS = [  # models whose own papers say what the answer should be
    ('BIOMD0000000312', 'R', 399.0, 599.0, {'tau': 200.0}, 'Tyson 2003 perfect adaptation (feed-forward, no loop): returns exactly'),
    ('BIOMD0000000603', 'Hog1PP', 3599.0, 3600.0 + 7200.0, None, 'yeast osmo-adaptation, salt step (Muzzey 2009 measured exact return in cells)'),
]


if __name__ == '__main__':
    if '--one' in sys.argv:
        i = sys.argv.index('--one'); a = sys.argv[i + 1:]
        try:
            print(json.dumps(one(a[0], *(a[1:3] if len(a) >= 3 else ()))))
        except Exception as e:
            print(json.dumps({'model': a[0], 'status': 'error: ' + repr(e)[:160]}))
        sys.exit()
    main()
