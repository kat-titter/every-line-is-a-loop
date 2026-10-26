"""Is each exact return found by truth_tests.py robust? Integral control returns exactly whatever the other rates are;
a coincidence does not. For each (model, parameter, variable) hit, draw 5 random sets of all the other global
parameters (each scaled by 10^U(-0.15, 0.15), seeded), settle, step the parameter by 20%, and check the return again.
Robust: returns within 0.5% in every draw that settles (at least 3). Writes results/robust_return.json.
Usage: .venv/bin/python analysis/robust_return.py [--one MODEL]"""
import concurrent.futures as cf, json, pathlib, subprocess, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))

def one(mid, pairs):
    import truth_tests as T
    DY, rr, ids, spset, x0, assigned, rate_vars = T.setup(mid, promote=True)
    params = [p for p in rr.model.getGlobalParameterIds() if p not in assigned and p not in rate_vars]
    base = {p: rr.getValue(p) for p in params}
    rng = np.random.default_rng(11)
    draws = [{p: v * 10 ** rng.uniform(-0.15, 0.15) for p, v in base.items()} for _ in range(5)]
    out = []
    for pair in pairs:
        p, var = pair['parameter'], pair['variable']; k = ids.index(var)
        res = []
        for dr in draws:
            try:
                rr.resetToOrigin()
                for q, v in dr.items():
                    rr.setValue(q, v)
                r = DY.run_from_keep(rr, ids, x0, spset) if hasattr(DY, 'run_from_keep') else None
            except Exception:
                r = None
            # settle under the drawn rates (run_from resets the model, so set the rates again after it)
            try:
                DY.put_state(rr, ids, spset, x0)
                for q, v in dr.items():
                    rr.setValue(q, v)
                y = np.array(rr.simulate(0, 1e4, 2001, [DY.sel(s, spset) for s in ids]))
                xs = y[-1]
                tail = y[int(0.8 * len(y)):]
                if not np.all(np.ptp(tail, axis=0) <= 1e-5 * np.maximum(np.abs(tail).mean(axis=0), 1e-12) + 1e-12):
                    res.append(None); continue
                rr.setValue(p, dr[p] * 1.2)
                z = np.array(rr.simulate(1e4, 3e4, 2001, [DY.sel(s, spset) for s in ids]))
                lvl = max(abs(xs[k]), 1e-12)
                peak = float(np.max(np.abs(z[:, k] - xs[k])) / lvl); fin = float(abs(z[-1, k] - xs[k]) / lvl)
                res.append({'peak': round(peak, 4), 'final': round(fin, 5)})
            except Exception:
                res.append(None)
        good = [x for x in res if x]
        robust = len(good) >= 3 and all(x['final'] < 0.005 for x in good)
        out.append({'parameter': p, 'variable': var, 'draws': res, 'robust': robust})
    return {'model': mid, 'pairs': out}

if __name__ == '__main__':
    if '--one' in sys.argv:
        i = sys.argv.index('--one'); mid = sys.argv[i + 1]; pairs = json.loads(sys.argv[i + 2])
        try:
            print(json.dumps(one(mid, pairs)))
        except Exception as e:
            print(json.dumps({'model': mid, 'error': repr(e)[:160]}))
        sys.exit()
    R = json.load(open(ROOT / 'results' / 'truth_tests.json'))
    hits = [r for r in R['step'] if r.get('status') == 'ok' and r['exact_returns']]
    def run(r):
        pairs = r['exact_returns'][:3]
        try:
            p = subprocess.run([sys.executable, __file__, '--one', r['model'], json.dumps(pairs)], capture_output=True, text=True, timeout=600,
                               env={'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'PATH': '/usr/bin:/bin'})
            line = [l for l in p.stdout.splitlines() if l.startswith('{')]
            out = json.loads(line[-1]) if line else {'model': r['model'], 'error': p.stderr[-160:]}
        except subprocess.TimeoutExpired:
            out = {'model': r['model'], 'error': 'timeout'}
        out.update(name=r.get('name'), loops=r.get('loops'), running_totals=r.get('running_totals'))
        return out
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(run, hits))
    (ROOT / 'results' / 'robust_return.json').write_text(json.dumps(res, indent=1))
    rob = [x for x in res if any(p['robust'] for p in x.get('pairs', []))]
    print('models with exact return', len(res), '| robust', len(rob))
    for x in res:
        if 1 <= (x.get('loops') or 0) <= 3:
            print('  1-3 loops', x['model'][-4:], str(x['name'])[:38], 'robust' if x in rob else 'not robust', x.get('error', ''))
