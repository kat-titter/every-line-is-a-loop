"""Trace the four small exact returns for a hidden running total.

Reads:  results/robust_return.json, data/r31_curated/*.xml
Writes: results/trace_four.json (and scratch model copies in data/trace_tmp/)
Run:    .venv/bin/python analysis/trace_four.py

The census found 22 exact returns that survive redrawn rates, 4 of them in models with one to three loops, and read a
running total in none. Fail line, frozen 2026-11-16 (Figure 1 of proto/tests.html): the claim "exact return, at any
rates, needs a running total" fails if one of the 4 has no quantity whose rate depends on the error alone and no
loop-free route.

For each (model, pushed rate, returning molecule) this script reports three things, all from the model's own
equations as the census loads them (truth_tests.setup, fingerprints.rhs_at):

  exact?       the returning molecule's resting level after the pushed rate is set to 0.5, 0.8, 1.2, 2 and 5 times its
               value. Exact means it moves by less than 1e-6 of itself. (The census called a return exact within 0.5%.)
  any rates?   every rate that is exactly zero in the file is given a small value and the sweep is repeated: a redraw
               that scales rates cannot move a zero, so this is the check the census's redraw could not make.
  the total    a certificate: hold the returning molecule(s) at rest, set every other molecule and the pushed rate at
               random, and look for a combination of molecules whose rate of change is zero in every sample. Such a
               combination can only rest when the returning molecule sits at its set point: a running total of the
               error. Conservation laws (combinations whose rate is zero everywhere) are removed first; a certificate
               must also move when the returning molecule is off its set point.

Usage: .venv/bin/python analysis/trace_four.py      (writes results/trace_four.json)
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import fingerprints as FP  # noqa: E402
import truth_tests as TT  # noqa: E402

FACTORS = (0.5, 0.8, 1.2, 2.0, 5.0)
EXACT = 1e-6
TMP = ROOT / 'data' / 'trace_tmp'


def load(
    mid: str, overrides: dict[str, float] | None = None
) -> tuple[object, object, list[str], set[str], np.ndarray, set[str], list[str]]:
    """The census loader, on a copy of the model with some rates overwritten. put_state resets every rate to the
    file's value, so an override has to live in the file the model is loaded from."""
    if not overrides:
        return TT.setup(mid, promote=True)
    import libsbml

    doc = libsbml.readSBMLFromFile(str(ROOT / 'data' / 'r31_curated' / f'{mid}.xml'))
    for q, v in overrides.items():
        par = doc.getModel().getParameter(q)
        assert par is not None, q
        par.setValue(float(v))
    TMP.mkdir(parents=True, exist_ok=True)
    libsbml.writeSBMLToFile(doc, str(TMP / f'{mid}.xml'))
    keep, TT.DATA = TT.DATA, TMP
    try:
        return TT.setup(mid, promote=True)
    finally:
        TT.DATA = keep


def state(rr: object, DY: object, ids: list[str], spset: set[str]) -> np.ndarray:
    """Current value of every state variable, in ids order."""
    return np.array([rr.getValue(DY.sel(s, spset)) for s in ids], dtype=float)


def settle(
    rr: object,
    DY: object,
    ids: list[str],
    spset: set[str],
    x: np.ndarray,
    p: str | None = None,
    val: float | None = None,
    T: float = 1e3,
) -> tuple[np.ndarray, bool]:
    """Run until the rates of change are negligible; returns the state and whether it settled."""
    DY.put_state(rr, ids, spset, x)
    if p is not None:
        rr.setValue(p, val)  # after put_state, which resets every rate
    for _ in range(14):
        try:
            rr.simulate(0, T, 20)
        except Exception:
            return state(rr, DY, ids, spset), False
        x = state(rr, DY, ids, spset)
        f = FP.rhs_at(rr, DY, ids, spset, x, p, val)
        if np.max(np.abs(f) / np.maximum(np.abs(x), 1e-9)) < 1e-11:
            return x, True
        DY.put_state(rr, ids, spset, x)
        if p is not None:
            rr.setValue(p, val)
        T *= 3
    return x, False


def sweep(mid: str, p: str, ys: list[str], zero_fix: dict[str, float] | None = None) -> dict[str, object]:
    """Relative change of each returning molecule's resting level when rate p is scaled."""
    DY, rr, ids, spset, x0, assigned, rate_vars = load(mid, zero_fix)
    base, ok = settle(rr, DY, ids, spset, x0)
    p0 = rr.getValue(p)
    out = {
        'settled': bool(ok),
        'rest': {y: float(base[ids.index(y)]) for y in ys},
        'moves': {y: {} for y in ys},
        'others move': {},
    }
    allmove = {}
    for fac in FACTORS:
        x, ok2 = settle(rr, DY, ids, spset, base, p, p0 * fac)
        for y in ys:
            k = ids.index(y)
            out['moves'][y][str(fac)] = float(abs(x[k] - base[k]) / abs(base[k])) if ok2 else None
        if ok2:
            out['others move'][str(fac)] = float(
                max(abs(x[k] - base[k]) / max(abs(base[k]), 1e-12) for k in range(len(ids)) if ids[k] not in ys)
            )
            if fac in (0.8, 1.2):
                for k, sname in enumerate(ids):
                    allmove[sname] = max(allmove.get(sname, 0.0), float(abs(x[k] - base[k]) / max(abs(base[k]), 1e-12)))
    worst = [v for y in ys for v in out['moves'][y].values() if v is not None]
    out['largest move'] = max(worst) if worst else None
    out['exact'] = bool(worst) and max(worst) < EXACT
    out['all that return exactly at 0.8x and 1.2x'] = sorted(k for k, v in allmove.items() if v < EXACT)
    out['largest move at 0.8x and 1.2x'] = max(
        (v for y in ys for f, v in out['moves'][y].items() if f in ('0.8', '1.2') and v is not None), default=None
    )
    return out


def null_space(F: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Orthonormal basis (columns) of the null space of F, by SVD."""
    u, s, vt = np.linalg.svd(F, full_matrices=True)
    rank = int(np.sum(s > tol * s[0])) if s.size and s[0] > 0 else 0
    return vt[rank:].T  # columns span the null space


def rref(M: np.ndarray, tol: float = 1e-8) -> np.ndarray:
    """Reduced row echelon form: the sparsest basis of the row space."""
    M = M.astype(float).copy()
    r = 0
    for c in range(M.shape[1]):
        if r == M.shape[0]:
            break
        k = r + int(np.argmax(np.abs(M[r:, c])))
        if abs(M[k, c]) < tol:
            continue
        M[[r, k]] = M[[k, r]]
        M[r] /= M[r, c]
        for i in range(M.shape[0]):
            if i != r:
                M[i] -= M[i, c] * M[r]
        r += 1
    return M[:r]


def tidy(w: np.ndarray) -> np.ndarray:
    """Scale a vector so its smallest clear entry is 1 and round away noise."""
    w = np.where(np.abs(w) < 1e-9 * np.max(np.abs(w)), 0.0, w)
    nz = np.abs(w[w != 0])
    w = w / nz.min()
    return w if w[np.flatnonzero(w)[0]] > 0 else -w


def certificate(
    mid: str, p: str, ys: list[str], zero_fix: dict[str, float] | None = None, n: int = 80, seed: int = 3
) -> dict[str, object]:
    """Look for a running total of the error: combinations of molecules whose rate is zero while ys rest (n samples)."""
    DY, rr, ids, spset, x0, assigned, rate_vars = load(mid, zero_fix)
    base, ok = settle(rr, DY, ids, spset, x0)
    p0 = rr.getValue(p)
    rng = np.random.default_rng(seed)
    held = [ids.index(y) for y in ys]
    free = [k for k in range(len(ids)) if k not in held]

    def sample(hold):
        rows = []
        for _ in range(n):
            x = base * 10 ** rng.uniform(-1, 1, len(ids))
            if hold:
                x[held] = base[held]
            rows.append(FP.rhs_at(rr, DY, ids, spset, x, p, p0 * 10 ** rng.uniform(-0.5, 0.5)))
        rr.setValue(p, p0)
        return np.array(rows)

    cons = null_space(sample(False))  # rate zero everywhere: conservation laws
    N = null_space(sample(True))  # rate zero whenever the returning molecule is at rest
    if cons.shape[1]:
        N = N - cons @ (cons.T @ N)  # remove the conservation laws
    u, s, _ = np.linalg.svd(N, full_matrices=False) if N.size else (np.zeros((len(ids), 0)), np.array([]), None)
    W = u[:, s > 1e-6] if s.size else u
    W = rref(W.T).T if W.shape[1] else W
    found = []
    off = base.copy()
    off[held] = base[held] * 1.3  # off the set point the total must move
    f_off = FP.rhs_at(rr, DY, ids, spset, off, p, p0)
    for j in range(W.shape[1]):
        w = tidy(W[:, j])
        found.append(
            {
                'combination': {ids[k]: round(float(w[k]), 6) for k in range(len(ids)) if w[k] != 0},
                'rate when the returning molecule is 30% off': float(w @ f_off),
            }
        )
    return {
        'conservation laws': int(cons.shape[1]),
        'totals found': len(found),
        'needed': len(ys),
        'totals': found,
        'held at rest': list(ys),
        'free molecules': [ids[k] for k in free],
        'pinned': len(found) + int(cons.shape[1]) >= len(ys),
    }


def main() -> None:
    """Trace the four small exact returns, then every robust return, and write results/trace_four.json."""
    R = json.loads((ROOT / 'results' / 'robust_return.json').read_text())
    four = [m for m in R if any(q.get('robust') for q in m['pairs']) and 1 <= (m.get('loops') or 0) <= 3]
    assert len(four) == 4
    out = []
    for m in four:
        mid = m['model']
        DY, rr, ids, spset, x0, assigned, rate_vars = TT.setup(mid, promote=True)
        zeros = [q for q in rr.model.getGlobalParameterIds() if q not in assigned and rr.getValue(q) == 0.0]
        nonzero = [
            abs(rr.getValue(q)) for q in rr.model.getGlobalParameterIds() if q not in assigned and rr.getValue(q) != 0.0
        ]
        eps = 0.01 * float(np.median(nonzero))
        pushes = {}
        for q in m['pairs']:
            if q.get('robust'):
                pushes.setdefault(q['parameter'], []).append(q['variable'])
        rec = {
            'model': mid,
            'name': m.get('name'),
            'molecules': ids,
            'rates set to zero in the file': zeros,
            'pushes': [],
        }
        for p, ys in pushes.items():
            e = {'pushed rate': p, 'returning': ys, 'exact?': sweep(mid, p, ys)}
            e['the total'] = certificate(mid, p, ys)
            if zeros:
                fix = dict.fromkeys(zeros, eps)
                e[f'any rates? zero rates set to {eps:.3g}'] = sweep(mid, p, ys, fix)
            rec['pushes'].append(e)
        if mid == 'BIOMD0000000413':  # the leak: VENUS photobleaching, lambda
            rec['leak test, lambda set to 0'] = []
            for p, ys in pushes.items():
                sw = sweep(mid, p, ys, {'lambda': 0.0})
                rec['leak test, lambda set to 0'].append(
                    {
                        'pushed rate': p,
                        'returning': sw['all that return exactly at 0.8x and 1.2x'],
                        'exact?': sw,
                        'the total': certificate(
                            mid, p, sw['all that return exactly at 0.8x and 1.2x'], {'lambda': 0.0}
                        ),
                    }
                )
        if mid == 'BIOMD0000000159':  # the nonlinear total for the signal psi, checked at random states and signals
            g = {q: rr.getValue(q) for q in ('beta_x', 'beta_y', 'alpha_xy', 'alpha_y')}
            rng = np.random.default_rng(5)
            worst = 0.0
            for _ in range(200):
                x = x0 * 10 ** rng.uniform(-1, 1, len(ids))
                psi = 10 ** rng.uniform(-1, 1)
                f = FP.rhs_at(rr, DY, ids, spset, x, 'psi', psi)
                X, Y0, Y = (x[ids.index(k)] for k in ('x', 'y0', 'y'))
                grad = np.zeros(len(ids))
                grad[ids.index('x')] = -g['beta_y'] / g['beta_x'] * X
                grad[ids.index('y0')] = 1
                grad[ids.index('y')] = 1
                want = Y * (g['beta_y'] * g['alpha_xy'] / g['beta_x'] * X**2 - g['alpha_y'])
                worst = max(worst, abs(grad @ f - want) / max(abs(want), 1e-12))
            rec['p53 identity'] = {
                'total': 'y0 + y - (beta_y / (2 beta_x)) x^2',
                'rate': 'y * ((beta_y alpha_xy / beta_x) x^2 - alpha_y)',
                'largest relative gap over 200 random states and signals': worst,
                'set point of x': float((g['beta_x'] * g['alpha_y'] / (g['beta_y'] * g['alpha_xy'])) ** 0.5),
            }
        out.append(rec)
        print('\n==', mid, m.get('name'), '| zero rates:', zeros)
        for e in rec['pushes']:
            x = e['exact?']
            print(
                '  push',
                e['pushed rate'],
                '-> returning',
                e['returning'],
                f'| largest move of the resting level over 0.5x to 5x: {x["largest move"]:.2e}',
                '| EXACT' if x['exact'] else '| NOT EXACT',
                '| settled' if x['settled'] else '| baseline not settled',
                '| by push size',
                {k: f'{v:.1e}' for k, v in x['moves'][e['returning'][0]].items() if v is not None},
                '| others move up to',
                f"{max(x['others move'].values()):.2g}" if x['others move'] else None,
            )
            for k, v in e.items():
                if k.startswith('any rates'):
                    print(
                        '     ', k, f'-> largest move {v["largest move"]:.2e}', 'EXACT' if v['exact'] else 'NOT EXACT'
                    )
            c = e['the total']
            print(
                '      totals found',
                c['totals found'],
                'of',
                c['needed'],
                'needed | conservation laws removed',
                c['conservation laws'],
            )
            for t in c['totals']:
                print(
                    '        ',
                    ' '.join(f'{v:+g} {k}' for k, v in t['combination'].items()),
                    f"| rate 30% off the set point: {t['rate when the returning molecule is 30% off']:.3g}",
                )
        for k in ('leak test, lambda set to 0',):
            for e in rec.get(k, []):
                x, c = e['exact?'], e['the total']
                print(
                    '   ',
                    k,
                    '| push',
                    e['pushed rate'],
                    '| held',
                    e['returning'],
                    f'| largest move {x["largest move"]:.2e}',
                    'EXACT' if x['exact'] else 'NOT EXACT',
                    '| totals found',
                    c['totals found'],
                    '+ conservation laws',
                    c['conservation laws'],
                    'pinned' if c['pinned'] else 'NOT pinned',
                    [' '.join(f'{v:+g} {n}' for n, v in t['combination'].items()) for t in c['totals']],
                )
        if 'p53 identity' in rec:
            print('    p53 identity:', rec['p53 identity'])
    every = []
    for m in R:
        rob = {}
        for q in m['pairs']:
            if q.get('robust'):
                rob.setdefault(q['parameter'], []).append(q['variable'])
        if not rob:
            continue
        worst, why, base_ok = 0.0, '', True
        for prm, ys in rob.items():
            try:
                global FACTORS
                keep, FACTORS = FACTORS, (0.8, 1.2)
                sw = sweep(m['model'], prm, ys)
                FACTORS = keep
                v = sw['largest move at 0.8x and 1.2x']
                base_ok = base_ok and sw['settled']
                if not sw['settled']:
                    why = 'baseline did not settle'
                elif v is None:
                    why = 'did not settle after the push'
                else:
                    worst = max(worst, v)
            except Exception as e:
                FACTORS = (0.5, 0.8, 1.2, 2.0, 5.0)
                why = 'error: ' + repr(e)[:60]
        kind = (
            'unread'
            if why
            else 'exact'
            if worst < EXACT
            else 'within 0.5%'
            if worst < 0.005
            else 'moves more than 0.5%'
        )
        every.append(
            {
                'model': m['model'],
                'name': m.get('name'),
                'loops': m.get('loops'),
                'largest move at 0.8x and 1.2x': worst,
                'exact': kind == 'exact',
                'kind': kind,
                'note': why,
            }
        )
    import collections

    print(
        '\nall robust exact returns of the census, pushed 0.8x and 1.2x and run to rest:',
        dict(collections.Counter(e['kind'] for e in every)),
    )
    for e in every:
        print(
            '   ',
            e['model'][-4:],
            str(e['name'])[:40].ljust(40),
            'loops',
            str(e['loops']).rjust(4),
            f"| move {e['largest move at 0.8x and 1.2x']:.1e}",
            '|',
            e['kind'],
            e['note'],
        )
    (ROOT / 'results' / 'trace_four.json').write_text(
        json.dumps({'the four': out, 'all robust returns': every}, indent=1)
    )


if __name__ == '__main__':
    main()
