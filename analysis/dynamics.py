"""Classify what an SBML model does, for the counting experiment.

Reads:  SBML models: one file (--one MODEL.xml) or a text file of model paths (--list results/list_ok.txt, one per line).
Writes: one JSON line per model to FILE.jsonl (--list ... --out results/r31_dynamics.jsonl), or the one line to stdout (--one).
Run:    python analysis/dynamics.py --list results/list_ok.txt --out results/r31_dynamics.jsonl --jobs 8

Behaviours recorded (several can hold at once):
  steady       every run settles to a fixed point
  multistable  runs from different starting states, inside the same conservation class,
               settle to different fixed points (memory)
  oscillating  a run ends on a sustained oscillation
  damped       a run settles after at least two overshoots of its final value
  unbounded    a state grows past 1e6 times its starting scale, or the integrator fails
               while a state is still climbing (a ramp, the counter's signature)
Starting states: the model's own initial state, plus random states x0 + N*xi that keep every
conserved total fixed (moves along the stoichiometry), scaled back to stay non-negative.
Budget: a model's runs share WORK_BUDGET derivative evaluations of solver work (budget.py), on top of CVODE's
200,000 steps per output interval; a model that spends it gets the status 'budget: solver work ...' instead of a
behaviour, whatever machine runs it. Two costs are bounded by counts instead: models with events or piecewise
switches, whose CVODE counters restart at each switch (BIOMD0000000408, a heartbeat pulse, takes 14 minutes alone),
and the full Jacobian read at each distinct fixed point, at most twelve (325 s each for the 431-variable
BIOMD0000000235). Each model runs in its own process under budget.py's wall-clock safety net.

Usage: python analysis/dynamics.py --one MODEL.xml   (JSON to stdout)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys
import time
from typing import Any

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import budget  # noqa: E402

STARTS = 12
HORIZONS = (1e2, 1e3, 1e4, 1e5)
# Solver work per model, in derivative evaluations (budget.py). Rule: clear every record that finished in the
# committed run, with room. Measured alone on 2026-11-19 on all 28 models that took 88 s or more there (records
# unchanged): the most is BIOMD0000000137 at 1.17e10. Every other model took under 88 s there, so at most
# 88 s x 1.7e8 a second (the fastest rate measured, BIOMD0000000137 again) = 1.5e10. 3e10 clears both twice over.
WORK_BUDGET = 3e10


def forced(path: str | pathlib.Path) -> bool:
    """True if the model is not autonomous: events, or time read by a rate law, rule or function."""
    import libsbml

    m = libsbml.readSBMLFromFile(str(path)).getModel()
    if m.getNumEvents():
        return True
    maths = [
        m.getReaction(i).getKineticLaw().getMath()
        for i in range(m.getNumReactions())
        if m.getReaction(i).isSetKineticLaw()
    ]
    maths += [m.getRule(i).getMath() for i in range(m.getNumRules())]
    maths += [m.getFunctionDefinition(i).getMath() for i in range(m.getNumFunctionDefinitions())]

    def has_time(node):
        if node is None:
            return False
        if node.getType() == libsbml.AST_NAME_TIME:
            return True
        return any(has_time(node.getChild(i)) for i in range(node.getNumChildren()))

    return any(has_time(x) for x in maths)


def load(path: str | pathlib.Path) -> Any:
    """Return a RoadRunner instance for the model, with tight integrator tolerances (rel 1e-8, abs 1e-12)."""
    import roadrunner

    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
    rr = roadrunner.RoadRunner(str(path))
    with contextlib.suppress(Exception):
        rr.integrator.relative_tolerance = 1e-8
        rr.integrator.absolute_tolerance = 1e-12
        rr.integrator.maximum_num_steps = 200000
    return rr


def spread_starts(x0: np.ndarray, N: np.ndarray, k: int, seed: int = 0) -> list[np.ndarray]:
    """Starting states that keep every conserved total of x0: corners of the polytope
    {x >= 0, x = x0 + N xi, x <= U} found by linear programs with random objectives, then
    random mixtures of those corners. U caps directions with no conservation law."""
    from scipy.optimize import linprog

    rng = np.random.default_rng(seed)
    n, R = N.shape
    pos = x0[x0 > 0]
    U = 10 * max(float(pos.max()) if len(pos) else 1.0, 1e-9)
    if R == 0:
        return [x0 * 10 ** rng.uniform(-1, 1, n) for _ in range(k)]
    corners = []
    A_eq = np.hstack([np.eye(n), -N])
    bounds = [(0, U)] * n + [(None, None)] * R
    for _ in range(3 * k):
        c = np.concatenate([rng.normal(size=n), np.zeros(R)])
        try:
            res = linprog(c, A_eq=A_eq, b_eq=x0, bounds=bounds, method='highs')
        except Exception:
            continue
        if res.status == 0:
            x = np.maximum(res.x[:n], 0)
            if not any(np.allclose(x, y, rtol=1e-6, atol=1e-12) for y in corners):
                corners.append(x)
        if len(corners) >= k:
            break
    out = []  # sparse random mixtures: near the corners, never exactly on a symmetric one
    while len(out) < k and corners:
        w = rng.dirichlet(np.full(len(corners), 0.3))
        out.append(np.maximum(sum(wi * c for wi, c in zip(w, corners)), 0))
    while len(out) < k:
        out.append(x0.copy())
    return out


def sel(s: str, species: set[str]) -> str:
    """RoadRunner selection for variable s: '[s]' (concentration) for a species, s itself for a rate-rule variable."""
    return '[' + s + ']' if s in species else s


def put_state(rr: Any, ids: list[str], species: set[str], x: np.ndarray) -> None:
    """Reset the model to its origin, then set the variables ids to the values x."""
    rr.resetToOrigin()
    for s, v in zip(ids, x):
        with contextlib.suppress(Exception):
            rr.setValue(sel(s, species), float(v))


def run_from(rr: Any, ids: list[str], x: np.ndarray, species: set[str] | None = None) -> dict[str, Any]:
    """Simulate from state x; return a dict describing the end of the run."""
    species = species if species is not None else set(ids)
    put_state(rr, ids, species, x)
    pos = np.abs(x)[np.abs(x) > 0]
    base = np.maximum(np.abs(x), float(np.median(pos)) if len(pos) else 1.0)
    for T in HORIZONS:
        try:
            r = rr.simulate(0, T, 2001, ['time'] + [sel(s, species) for s in ids])
        except Exception as e:
            return {'kind': 'failed', 'error': repr(e)[:120]}
        y = np.array(r)[:, 1:]
        if not np.all(np.isfinite(y)):
            return {'kind': 'unbounded'}
        if np.any(np.abs(y[-1]) > 1e6 * base):
            return {'kind': 'unbounded'}
        tail = y[int(0.8 * len(y)) :]
        rngs = np.ptp(tail, axis=0)
        level = np.maximum(np.abs(tail).mean(axis=0), 1e-9)
        if np.all(rngs <= 1e-5 * level + 1e-12):
            final = y[-1]
            over = 0
            for k in range(y.shape[1]):  # count crossings of the final value (overshoots)
                d = y[:, k] - final[k]
                big = np.abs(d) > 1e-3 * (abs(final[k]) + 1e-9)
                sgn = np.sign(d[big])
                over = max(over, int(np.sum(sgn[1:] != sgn[:-1])) if len(sgn) > 1 else 0)
            return {'kind': 'steady', 'state': final.tolist(), 'overshoots': over, 'T': T}
        half = y[len(y) // 2 :]
        k = int(np.argmax(np.ptp(half, axis=0) / np.maximum(np.abs(half).mean(axis=0), 1e-12)))
        z = half[:, k]
        pk = [i for i in range(1, len(z) - 1) if z[i] > z[i - 1] and z[i] >= z[i + 1]]
        amp = np.ptp(z) / max(abs(z.mean()), 1e-12)
        if len(pk) >= 3 and amp > 1e-3:
            a = [z[i] - z.min() for i in pk]
            if a[-1] >= 0.9 * a[0]:
                try:  # confirm: continue for another 2T and require the swing to persist
                    r2 = np.array(rr.simulate(T, 3 * T, 2001, ['time'] + [sel(s, species) for s in ids]))[:, 1:]
                    z2 = r2[len(r2) // 2 :, k]
                    if np.ptp(z2) >= 0.8 * np.ptp(z) and np.ptp(z2) / max(abs(z2.mean()), 1e-12) > 1e-3:
                        return {'kind': 'oscillating', 'species': ids[k], 'peaks': len(pk), 'T': T}
                except Exception:
                    pass
        climbing = np.any((y[-1] - y[len(y) // 2]) > 0.5 * np.maximum(np.abs(y[len(y) // 2]), 1e-9)) and np.any(
            np.all(np.diff(y[len(y) // 2 :], axis=0) >= 0, axis=0) & (np.ptp(y[len(y) // 2 :], axis=0) > 1e-6)
        )
        if HORIZONS[-1] == T:
            return {'kind': 'unbounded' if climbing else 'unsettled', 'T': T}
    return {'kind': 'unsettled'}


def classify(path: str | pathlib.Path, seed: int = 0) -> dict[str, Any]:
    """Run the model from its own state and 11 spread states; return its record with the behaviours seen."""
    t0 = time.time()
    import libsbml

    rr = load(path)
    budget.meter(rr, WORK_BUDGET)
    m = libsbml.readSBMLFromFile(str(path)).getModel()
    assigned = {m.getRule(i).getVariable() for i in range(m.getNumRules()) if m.getRule(i).isAssignment()}
    rate_vars = [m.getRule(i).getVariable() for i in range(m.getNumRules()) if m.getRule(i).isRate()]
    species = [s for s in rr.model.getFloatingSpeciesIds() if s not in assigned]
    ids = species + [v for v in rate_vars if v not in species]
    out = {
        'model': pathlib.Path(path).stem,
        'species': len(species),
        'state_variables': len(ids),
        'forced': forced(path),
    }
    if not ids:
        out['status'] = 'no state variables'
        return out
    spset = set(species)
    x0 = np.array([rr.getValue(sel(s, spset)) for s in ids], dtype=float)
    try:
        S = rr.getFullStoichiometryMatrix()
        rows = {s: i for i, s in enumerate(S.rownames)}
        N = np.array([np.array(S[rows[s]]) if s in rows else np.zeros(S.shape[1]) for s in ids])
        free = [i for i, s in enumerate(ids) if s not in rows]  # rate-rule variables: no conservation
    except Exception:
        N = np.zeros((len(ids), 0))
        free = list(range(len(ids)))
    starts = [x0] + spread_starts(x0, N, STARTS - 1, seed)
    rng = np.random.default_rng(seed + 7)
    for x in starts[1:]:  # rate-rule variables carry no conservation law: spread them too
        for i in free:
            x[i] = abs(x0[i]) * 10 ** rng.uniform(-0.5, 0.5) if x0[i] else x[i]
    runs = [run_from(rr, ids, x, spset) for x in starts]
    kinds = [r['kind'] for r in runs]
    mag = float(np.max(np.abs(x0))) if np.any(x0) else 1.0
    steadies = [np.array(r['state']) for r in runs if r['kind'] == 'steady']
    distinct = []
    for s in steadies:
        if not any(np.all(np.abs(s - d) <= 1e-2 * np.maximum(np.abs(d), np.abs(s)) + 1e-6 * mag) for d in distinct):
            distinct.append(s)
    beh = set()
    if steadies:
        beh.add('steady')
    degenerate = False
    if len(distinct) >= 2:  # Soule's theorem concerns non-degenerate fixed points: test each one
        try:
            Q, _ = np.linalg.qr(N) if N.shape[1] else (np.eye(len(ids)), None)
            rk = np.linalg.matrix_rank(N) if N.shape[1] else len(ids)
            B = Q[:, :rk] if N.shape[1] else np.eye(len(ids))
            if free:
                B = np.hstack([B, np.eye(len(ids))[:, free]])
            for fp in distinct:
                put_state(rr, ids, spset, fp)
                J = np.array(rr.getFullJacobian())
                if J.shape[0] != len(ids):
                    continue
                ev = np.linalg.eigvals(B.T @ J @ B)
                if np.any(np.abs(ev) < 1e-8 * max(1.0, float(np.abs(ev).max()))):
                    degenerate = True
        except Exception:
            pass
    out['degenerate_fixed_point'] = degenerate
    if 2 <= len(distinct) <= max(2, len(steadies) // 3) and not degenerate:
        beh.add('multistable')
    elif len(distinct) >= 2:
        beh.add('continuum')  # end state moves with the start: a neutral direction, not a switch
    if 'oscillating' in kinds:
        beh.add('oscillating')
    if any(r.get('overshoots', 0) >= 2 for r in runs if r['kind'] == 'steady'):
        beh.add('damped')
    if 'unbounded' in kinds:
        beh.add('unbounded')
    out.update(
        status='ok', runs=kinds, fixed_points=len(distinct), behaviours=sorted(beh), seconds=round(time.time() - t0, 2)
    )
    return out


def record(path: str | pathlib.Path) -> dict[str, Any]:
    """classify, with a spent budget or a crash turned into the record's status: the line --one prints."""
    try:
        return classify(path)
    except budget.Spent as e:
        return {'model': pathlib.Path(path).stem, 'status': f'budget: {e}'}
    except Exception as e:
        return {'model': pathlib.Path(path).stem, 'status': 'error', 'error': repr(e)[:300]}


def run_list(paths: list[str], out_file: str | pathlib.Path, jobs: int) -> None:
    """Run classify on each path, each in its own process; write one JSON line per model."""
    from concurrent.futures import ThreadPoolExecutor

    me = pathlib.Path(__file__).resolve()

    def one(f):
        p = budget.run([sys.executable, str(me), '--one', str(f)], pathlib.Path(f).stem)
        if p is None:
            return {'model': pathlib.Path(f).stem, 'status': budget.SAFETY_NET}
        line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
        return (
            json.loads(line)
            if line.startswith('{')
            else {'model': pathlib.Path(f).stem, 'status': 'error', 'error': (p.stderr or '')[-300:]}
        )

    with ThreadPoolExecutor(jobs) as ex, open(out_file, 'w') as fh:
        for r in ex.map(one, paths):
            fh.write(json.dumps(r) + '\n')
            fh.flush()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--one')
    ap.add_argument('--list')
    ap.add_argument('--out')
    ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args()
    if a.one:
        print(json.dumps(record(a.one)))
    else:
        run_list(
            [line.strip() for line in pathlib.Path(a.list).read_text().splitlines() if line.strip()],
            a.out,
            a.jobs,
        )
