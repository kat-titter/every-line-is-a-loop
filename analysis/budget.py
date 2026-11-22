"""Work budgets: every per-model limit in the census counts work, never seconds, so a record does not depend on the
machine's speed or load.

Reads:  a --list file of model paths (run_list only); imported by dynamics.py, truth_tests.py, fingerprints.py,
        robust_return.py, loops.py, integrators.py, elim.py
Writes: one JSONL file per run_list call; nothing otherwise

Solver work is counted in derivative evaluations: each time CVODE evaluates the model's right-hand side (in its
Newton iterations, or column by column for its difference-quotient Jacobian) it computes one rate of change per state
variable, so a simulate call's work is (RHS calls + Jacobian RHS calls) x state variables, read from CVODE's own
counters after the call. The count is the same on any machine. Its cost is not: measured alone on the Apple M5 that
made the committed results, models run from 1.2e7 (BIOMD0000000045) to 1.7e8 (BIOMD0000000137) derivative
evaluations per CPU second. libroadrunner restarts CVODE, and so its counters, at every event and piecewise switch,
so for models with those the count covers each call's last stretch only: still deterministic, but an undercount.

meter(rr, limit) counts every simulate call on one RoadRunner instance and raises Spent after the call that takes
the total past limit. Spent is a BaseException, so the scripts' `except Exception` paths, which turn a solver
failure into a 'failed' run, cannot swallow it; each script's --one entry turns it into the status 'budget: ...'.
The check falls between calls, so a model may overshoot by its last call; the count, and so the outcome, is the same
on any machine.

run() runs one per-model subprocess under a wall-clock safety net, SAFETY_NET_S, set far above any real run. It
should never fire; if it does, it prints a loud line to stderr and the caller records the status SAFETY_NET.
run_list() runs a script's --one entry on each model of a list that way, in parallel, and writes one JSON line per
model (dynamics.py, integrators.py and elim.py use it).
"""

from __future__ import annotations

import ctypes
import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# 6 hours: far above any run the budgets allow. The slowest per-model run measured is BIOMD0000000235 in dynamics.py,
# 59 minutes alone (ten full-Jacobian reads of 431 variables, not solver work); the largest budget,
# 1.1e11 derivative evaluations (truth_tests.py, robust_return.py), takes about 2.5 hours at the slowest CVODE-bound
# rate measured, 1.2e7 a second (BIOMD0000000045).
SAFETY_NET_S = 6 * 3600
SAFETY_NET = f'safety net: past {SAFETY_NET_S} s of wall clock'


class Spent(BaseException):
    """A model's work budget ran out; not an Exception, so solver-failure handlers do not record it as 'failed'."""


def _cvode() -> tuple[Any, dict[str, Any]]:
    """libroadrunner 2.7.0's exported CVODE symbols (requirements.txt pins it); fails loudly if they move."""
    import roadrunner

    lib = ctypes.CDLL(roadrunner._roadrunner.__file__)
    try:
        mem = lib._ZNK2rr15CVODEIntegrator14getCvodeMemoryEv
        vec = lib._ZNK2rr15CVODEIntegrator14getStateVectorEv
        fns = {n: getattr(lib, n) for n in ('CVodeGetNumRhsEvals', 'CVodeGetNumLinRhsEvals', 'N_VGetLength')}
    except AttributeError as e:
        raise RuntimeError(f'libroadrunner no longer exports a CVODE counter budget.py reads: {e}') from e
    mem.restype = vec.restype = ctypes.c_void_p
    mem.argtypes = vec.argtypes = [ctypes.c_void_p]
    for n in ('CVodeGetNumRhsEvals', 'CVodeGetNumLinRhsEvals'):
        fns[n].argtypes, fns[n].restype = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_long)], ctypes.c_int
    fns['N_VGetLength'].argtypes, fns['N_VGetLength'].restype = [ctypes.c_void_p], ctypes.c_long
    return (mem, vec), fns


_SYMS: tuple[Any, dict[str, Any]] | None = None


def work(rr: Any) -> int:
    """Derivative evaluations CVODE spent in rr's last simulate call (0 if the model has no state to integrate)."""
    global _SYMS
    if _SYMS is None:
        _SYMS = _cvode()
    (mem_of, vec_of), f = _SYMS
    this = int(rr.integrator.this)
    mem, vec = mem_of(this), vec_of(this)
    if not mem or not vec:
        return 0
    calls = 0
    for name in ('CVodeGetNumRhsEvals', 'CVodeGetNumLinRhsEvals'):
        n = ctypes.c_long(0)
        if f[name](mem, ctypes.byref(n)) != 0:
            raise RuntimeError(f'{name} failed on a live CVODE memory')
        calls += n.value
    return calls * int(f['N_VGetLength'](vec))


class Meter:
    """The work spent so far by one model's simulate calls, against its limit."""

    def __init__(self, limit: float) -> None:
        self.limit, self.used = limit, 0


def meter(rr: Any, limit: float) -> Meter:
    """Count the work of every rr.simulate call; raise Spent after the call that takes the total past limit."""
    sim, m = rr.simulate, Meter(limit)

    def simulate(*args: Any, **kwargs: Any) -> Any:
        try:
            return sim(*args, **kwargs)
        finally:
            m.used += work(rr)
            if m.used > m.limit:
                raise Spent(f'solver work past {m.limit:.0e} derivative evaluations')

    rr.simulate = simulate
    return m


def run(cmd: list[str], model: str, **kwargs: Any) -> subprocess.CompletedProcess | None:
    """subprocess.run with captured text output under the safety net; None, said loudly on stderr, if it fired."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=SAFETY_NET_S, **kwargs)
    except subprocess.TimeoutExpired:
        print(f'!!! SAFETY NET FIRED: {model} ran past {SAFETY_NET_S} s; its record depends on load', file=sys.stderr)
        sys.stderr.flush()
        return None


def run_list(
    script: str | pathlib.Path,
    list_file: str | pathlib.Path,
    out_file: str | pathlib.Path,
    jobs: int,
    extra: tuple[str, ...] = (),
) -> None:
    """Run `script --one PATH *extra` on each path in list_file (one per line), each in its own process; write one
    JSON line per model to out_file, in list order. A run whose last output line does not start with '{' is recorded
    as an error with the tail of its stderr."""
    paths = [line.strip() for line in pathlib.Path(list_file).read_text().splitlines() if line.strip()]

    def one(f):
        p = run([sys.executable, str(script), '--one', f, *extra], pathlib.Path(f).stem)
        if p is None:
            return {'model': pathlib.Path(f).stem, 'status': SAFETY_NET}
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
