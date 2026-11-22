"""Essential loops: does a circuit keep its square once each drawing is reduced to the loops it needs?

Reads:  data/r31_curated/*.xml, data/holdout_curated/*.xml, results/r31_structure_traj.jsonl,
        results/holdout_structure_traj.jsonl, results/r31_dynamics.jsonl
Writes: build/essential_loops/<stage>/<model>.json (one record per model, kept so a killed run resumes);
        analysis/essential_loops_report.py turns them into results/essential_loops.json
Run:    .venv/bin/python analysis/essential_loops.py controls | families | census | found [--jobs N]

THE RULE AND THE FAIL LINES, COPIED 2026-11-22 BEFORE ANY RESULT WAS READ
From the plan Kat approved ("Yes, after publish"), plan-reduction-test.md, word for word:

  Essential loops. For each loop the census lists in a model, cut it (hold one of its arrows at its settled
  value) and rerun the model. A loop is essential if the cut changes the model's atlas answer (ticks, remembers,
  returns exactly, returns partly, rings, follows). The reduced address is (essential loops, essential brakes,
  essential running totals).

  1. Agreement. Reduced addresses agree within a family in at least 4/5 of the hand-picked families.
     Fewer: the rule fails.
  2. It must still say something. Among the 96 ticking models, reduced addresses take at least 3 distinct
     values, and the reduced address predicts the atlas answer of held-out models better than the sign rules
     alone (the test of analysis/address_predicts.py, same split). If every clock reduces to "one brake", the
     reduced table is the atlas under another name, and the essay says so.
  3. Not just these five. Families found by a rule, not by hand (same first author and year, or one paper,
     in release 31 and the 435 newer models), listed before their addresses are read. Agreement in at least
     2/3 of them.

  Controls
  - Should pass: a model and its own copy with one relay step inserted by script land on one reduced address.
  - Should fail: random pairs of models with the same atlas answer agree less often than families do. If they
    agree as often, the rule sorts by behaviour, not by circuit (fail line 2 again).
  - Known answer: the repressilator reduces to one essential brake; Gardner's toggle to one essential
    self-feeding loop.

The essay published the same three lines in Supplement F (commit 5412b3b) in other words, thresholds unchanged:
  "Agreement. Drawings of one circuit must share a reduced address in at least 4/5 families, where the raw address
  agrees in 1/5."
  "It must still say something. Among the 96 ticking models the reduced address must take at least 3 values, and it
  must call the answers of held-out models better than the two sign rules alone. If every clock reduces to one
  brake, the atlas is the table, and loop counts are the theory behind its rows."
  "Not only these families. Families picked by a rule (one paper, or one first author and year), listed before
  their addresses are read, must agree in at least 2/3."
Where the essay is silent (the split, the pool of models) the plan's wording decides.

THE PLAN'S TWO OPEN POINTS, SETTLED HERE BEFORE THE FIRST RUN
  A. Loops that share arrows. Each loop is cut at the one of its arrows that the fewest listed loops use (ties: the
     first by name). A cut kills every loop that uses its arrow, and each record lists them. The essential loops
     of a model are a smallest set of loops that accounts for every answer-changing cut: each such cut kills at
     least one of them (ties: loops with fewer steps first, then census order). A loop cut at an arrow of its own
     is therefore essential exactly when its cut changes the answer, which is the plan's rule; loops that can only
     be cut together count once.
  B. The settled value. A model that settles is held at its steady state. A model that ticks is held at its cycle
     mean, the time average between the first and last peak of its most swinging molecule over a further 2T of
     running; each record says which was used.

OTHER CHOICES, ALSO FIXED BEFORE THE FIRST RUN
  - An arrow is every way its source enters its target's rate of change (sbml_cut.py); the cut model is an SBML
    file, so fingerprints.one files it with the code that filed the original, and the uncut model is filed again
    the same way (its row is compared with results/fingerprints.json in the report).
  - "Changes the answer": the cut model files in another row ('flat' included), or no longer settles or ticks
    ('baseline unbounded', 'baseline unsettled', 'still drifting': verdict 'lost', counted as changed; the report
    also gives the tallies with those models left out). A cut whose run spends its work budget, fails in the
    solver, or could not be written is 'unread', and its model has no reduced address.
  - A model is reduced only if the atlas files it in one of the six rows, the census listed all its loops, and
    there are at most MAX_LOOPS of them; every model left out is counted with its reason.
  - A family agrees when at least two of its drawings were reduced and all of those share one reduced address;
    a family with fewer than two reduced drawings counts as not agreeing.
  - Fail line 1 is scored on the five families the plan names. truth_tests.FAMILIES also holds Borghans 1997
    (three models), added after the plan's count; it is run and reported beside the five, outside the fail line.
  - "Beats the sign rules alone" is address_predicts.run's amended verdict (PASS needs p < 0.05, a lead of at
    least 5 points over the sign bits, and more than a size control) with the reduced address in place of the raw.
  - loops.py is not edited: its loop list is read by wrapping loops.pf_filtered during loops.analyze.
Budgets are counts of work (budget.py): fingerprints.WORK_BUDGET derivative evaluations per filing, loops.py's own
search-step limits; budget.py's 6-hour wall-clock safety net is the only clock.
"""

from __future__ import annotations

import concurrent.futures as cf
import contextlib
import itertools
import json
import os
import pathlib
import shutil
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import budget  # noqa: E402

WORK = ROOT / 'build' / 'essential_loops'
R31, HOLDOUT = ROOT / 'data' / 'r31_curated', ROOT / 'data' / 'holdout_curated'
SIX = ['ticks', 'remembers', 'returns exactly', 'returns partly', 'rings', 'follows']
# The largest hand-picked drawing has 15 loops (Singh 2006, model 1); 16 keeps every family model in reach.
MAX_LOOPS = 16
RELAY_SPEEDUP = 10.0  # the relay follows its source this many times faster than the model's fastest own rate
REPRESSILATOR, TOGGLE = 'BIOMD0000000012', 'BIOMD0000000507'
PLAN_FAMILIES = [
    'fruit fly day clock',
    'Tyson 1991 cell cycle, 6 and 2 variables',
    'Morris-Lecar muscle fibre, full and reduced',
    'Singh 2006 TCA cycle, two versions',
    'Smallbone 2013 colon crypt, versions 0 to 3',
]


# ---------------------------------------------------------------- the rule, as pure functions
def choose_cuts(loops: list[dict]) -> list[dict]:
    """One cut per loop, at its least shared arrow; loops choosing the same arrow share the cut."""
    arrows = [sorted({(a[0], a[1]) for a in lp['arcs']}) for lp in loops]
    users = {}
    for i, arr in enumerate(arrows):
        for a in arr:
            users.setdefault(a, []).append(i)
    cuts = {}
    for arr in arrows:
        a = min(arr, key=lambda a: (len(users[a]), a))
        cuts.setdefault(a, {'arrow': list(a), 'kills': users[a]})
    for a, c in cuts.items():
        if a[0] == a[1]:  # a molecule's arrow to itself: only the reactions the census named
            c['only'] = sorted({x[2][2:] for i in c['kills'] for x in loops[i]['arcs'] if x[2].startswith('R:')})
    return list(cuts.values())


def verdict(base_row: str, rec: dict) -> str:
    """What a cut did to the answer: 'same', 'changed', 'lost' (no longer settles or ticks) or 'unread'."""
    status = rec.get('status', '')
    if status == 'ok':
        return 'same' if rec.get('row') == base_row else 'changed'
    if status in ('baseline unbounded', 'baseline unsettled') or status.startswith('still drifting'):
        return 'lost'
    return 'unread'


def essential(loops: list[dict], cuts: list[dict], verdicts: list[str], lost_counts: bool = True) -> list[int] | None:
    """Indices of a smallest set of loops that accounts for every answer-changing cut; None if a cut is unread."""
    if 'unread' in verdicts or (not lost_counts and 'lost' in verdicts):
        return None
    changing = [set(c['kills']) for c, v in zip(cuts, verdicts) if v in ('changed', 'lost')]
    order = sorted(range(len(loops)), key=lambda i: (len(loops[i]['nodes']), i))
    for size in range(len(loops) + 1):
        for pick in itertools.combinations(order, size):
            if all(kills & set(pick) for kills in changing):
                return sorted(pick)
    raise AssertionError('every cut kills a loop, so the full set always accounts for the cuts')


def address(loops: list[dict], picked: list[int] | None) -> list[int] | None:
    """(essential loops, essential brakes, essential running totals)."""
    if picked is None:
        return None
    return [
        len(picked),
        sum(loops[i]['sign'] == '-' for i in picked),
        sum(bool(loops[i]['integrates']) for i in picked),
    ]


# ---------------------------------------------------------------- one model: loops, settled state, cut files
def census_loops(path: pathlib.Path) -> dict:
    """The census's loops for one model, with their arrows: loops.analyze, read through loops.pf_filtered."""
    import loops as L

    calls, orig = [], L.pf_filtered

    def spy(la, signs, *a, **k):
        calls.append((la, signs))
        return orig(la, signs, *a, **k)

    L.pf_filtered = spy
    try:
        rec = L.analyze(path)
    finally:
        L.pf_filtered = orig
    rank = (rec.get('defs') or {}).get('ref24_rank') or {}
    if rec.get('status') != 'ok' or not rank.get('complete'):
        return {'status': rec.get('status') if rec.get('status') != 'ok' else 'loops not all listed', 'loops': []}
    rr, flags = L.load(path)
    nodes = L.state_nodes(rr, flags)[0]
    changes = {}
    with contextlib.suppress(RuntimeError):  # no matrix when no reaction changes a molecule (rate rules only)
        S = rr.getFullStoichiometryMatrix()
        changes = {s: [r for j, r in enumerate(S.colnames) if S[i][j] != 0] for i, s in enumerate(S.rownames)}
    deps, rdeps = flags.get('_deps', {}), flags.get('_rule_deps', {})
    integ = set()
    for v in nodes:  # loops.analyze's structural integrators: no law that changes v names v
        laws = [deps.get(r, set()) for r in changes.get(v, [])] + ([rdeps[v]] if v in rdeps else [])
        if laws and all(v not in d for d in laws):
            integ.add(v)
    la, signs = calls[-1] if rank['c'] else ([], [])
    out = [
        {
            'arcs': sorted([nodes[a], nodes[b], lab] for a, b, lab in arcs),
            'nodes': sorted({nodes[a] for a, _, _ in arcs}),
            'sign': '+' if s > 0 else '-',
            'integrates': bool({nodes[a] for a, _, _ in arcs} & integ),
        }
        for arcs, s in zip(la, signs)
    ]
    raw = [len(out), sum(lp['sign'] == '-' for lp in out), sum(lp['integrates'] for lp in out)]
    if raw != [rank['c'], rank['k'], rank['j']]:
        raise AssertionError(f'loop list {raw} does not match the census address {[rank["c"], rank["k"], rank["j"]]}')
    return {'status': 'ok', 'loops': out, 'raw': raw, 'name': rec.get('name')}


def settle(folder: pathlib.Path, mid: str) -> dict:
    """Settled value of every state variable: the steady state, or the cycle mean of a model that ticks."""
    import fingerprints as FP
    import truth_tests as TT

    TT.DATA = folder
    DY, rr, ids, spset, x0, _, _ = TT.setup(mid, promote=True)
    budget.meter(rr, FP.WORK_BUDGET)
    base = DY.run_from(rr, ids, x0, spset)
    if base['kind'] == 'steady':
        x, how = np.array(base['state']), 'steady state'
    elif base['kind'] == 'oscillating':
        T = base['T']
        y = np.array(rr.simulate(3 * T, 5 * T, 4001, [DY.sel(s, spset) for s in ids]))
        z = y[:, ids.index(base['species'])]
        pk = [i for i in range(1, len(z) - 1) if z[i] > z[i - 1] and z[i] >= z[i + 1]]
        span = y[pk[0] : pk[-1]] if len(pk) >= 2 else y
        x, how = span.mean(axis=0), f'cycle mean over {max(len(pk) - 1, 0)} periods'
    else:
        return {'status': 'baseline ' + base['kind']}
    J, _ = TT.jacobian(rr, DY, ids, spset, x)
    volume = {}
    for s in spset:
        try:
            conc, amt = rr.getValue('[' + s + ']'), rr.getValue(s)
            volume[s] = amt / conc if conc else 1.0
        except Exception:
            volume[s] = 1.0
    return {
        'status': 'ok',
        'settled': how,
        'value': dict(zip(ids, map(float, x))),
        'start': dict(zip(ids, map(float, x0))),
        'volume': volume,
        'fastest_rate': float(np.max(np.abs(np.diag(J)))) if np.all(np.isfinite(J)) else None,
    }


def _write(doc: object, folder: pathlib.Path, mid: str) -> None:
    import libsbml

    folder.mkdir(parents=True, exist_ok=True)
    libsbml.writeSBMLToFile(doc, str(folder / f'{mid}.xml'))


def prepare(path: pathlib.Path, work: pathlib.Path) -> dict:
    """List a model's loops, settle it, and write its uncut copy (work/base) and one SBML file per cut (work/cutN)."""
    import libsbml
    import sbml_cut

    mid = path.stem
    plan = census_loops(path)
    if plan['status'] != 'ok':
        return plan
    if len(plan['loops']) > MAX_LOOPS:
        return {'status': f'more than {MAX_LOOPS} loops', 'raw': plan['raw']}
    base = libsbml.readSBMLFromFile(str(path))
    sbml_cut.promote_locals(base)
    _write(base, work / 'base', mid)
    plan['cuts'] = choose_cuts(plan['loops'])
    if not plan['cuts']:
        return plan
    state = settle(work / 'base', mid)
    if state['status'] != 'ok':
        return dict(plan, status=state['status'])
    plan.update(settled=state['settled'], fastest_rate=state['fastest_rate'])
    for n, c in enumerate(plan['cuts']):
        src, dst = c['arrow']
        doc = base.clone()
        value = sbml_cut.symbol_value(doc, src, state['value'][src], state['volume'].get(src, 1.0))
        c['held_at'] = value
        c['start'] = sbml_cut.symbol_value(doc, src, state['start'][src], state['volume'].get(src, 1.0))
        c['rewired'] = sbml_cut.cut(doc, src, dst, value, f'c{n}', set(c['only']) if 'only' in c else None)
        if c['rewired']:
            _write(doc, work / f'cut{n}', mid)
    return plan


def relay_copy(path: pathlib.Path, plan: dict, out: pathlib.Path) -> list[str]:
    """Write a copy of the model with one relay step on the first cut's arrow (the control that should pass)."""
    import libsbml
    import sbml_cut

    c = plan['cuts'][0]
    doc = libsbml.readSBMLFromFile(str(path))
    sbml_cut.promote_locals(doc)
    src, dst = c['arrow']
    done = sbml_cut.relay(doc, src, dst, c['start'], RELAY_SPEEDUP * plan['fastest_rate'], 'r0')
    _write(doc, out, path.stem)
    return done


# ---------------------------------------------------------------- subprocess entry points
def _call(args: list[str], mid: str) -> dict:
    """Run this script with args in a single-threaded subprocess; the last JSON line it prints, or a status."""
    env = {'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'PATH': '/usr/bin:/bin'}
    r = budget.run([sys.executable, str(pathlib.Path(__file__)), *args], mid, env=env)
    if r is None:
        return {'status': budget.SAFETY_NET}
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith('{')]
    return json.loads(lines[-1]) if lines else {'status': 'error: ' + r.stderr.strip()[-200:]}


def file_answer(folder: pathlib.Path, mid: str) -> dict:
    """fingerprints.one on the SBML file folder/mid.xml (the atlas's own filing, on a cut or uncut copy)."""
    import fingerprints as FP
    import truth_tests as TT

    TT.DATA = folder
    try:
        return FP.one(mid)
    except budget.Spent as e:
        return {'model': mid, 'status': f'budget: {e}'}
    except Exception as e:
        return {'model': mid, 'status': 'error: ' + repr(e)[:160]}


def _brief(rec: dict) -> dict:
    return {k: rec.get(k) for k in ('status', 'row', 'why', 'input', 'output') if rec.get(k) is not None}


def reduce_model(path: pathlib.Path, stage: str, tag: str | None = None) -> dict:
    """The whole rule on one model; its record is kept in build/essential_loops/<stage>/ and reused if present."""
    mid, tag = path.stem, tag or path.stem
    done = WORK / stage / f'{tag}.json'
    if done.exists():
        return json.loads(done.read_text())
    work = WORK / stage / tag
    shutil.rmtree(work, ignore_errors=True)
    rec = {'model': mid, 'tag': tag, **_call(['--prepare', str(path), str(work)], mid)}
    if rec['status'] == 'ok':
        base = _call(['--file', str(work / 'base'), mid], mid)
        rec['answer'] = _brief(base)
        if base.get('row') not in SIX:
            rec['status'] = 'no atlas answer: ' + str(base.get('row') or base.get('status'))
    if rec['status'] == 'ok':
        for n, c in enumerate(rec.get('cuts', [])):
            got = _call(['--file', str(work / f'cut{n}'), mid], mid) if c['rewired'] else {'status': 'cut not made'}
            c['answer'], c['verdict'] = _brief(got), verdict(rec['answer']['row'], got)
        verdicts = [c['verdict'] for c in rec.get('cuts', [])]
        rec['essential'] = essential(rec['loops'], rec.get('cuts', []), verdicts)
        rec['reduced'] = address(rec['loops'], rec['essential'])
        rec['reduced_without_lost'] = address(rec['loops'], essential(rec['loops'], rec['cuts'], verdicts, False))
    done.parent.mkdir(parents=True, exist_ok=True)
    tmp = done.with_suffix('.tmp')
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, done)
    return rec


# ---------------------------------------------------------------- stages
def _show(rec: dict) -> None:
    cuts = ' '.join(c.get('verdict', '-')[0] for c in rec.get('cuts', []))
    print(rec['tag'], rec['status'], 'raw', rec.get('raw'), 'reduced', rec.get('reduced'), '|', cuts, flush=True)


def run_many(paths: list[pathlib.Path], stage: str, jobs: int) -> list[dict]:
    """Reduce every model (jobs at a time), printing one line each as it lands."""
    out = []
    with cf.ThreadPoolExecutor(jobs) as ex:
        for rec in ex.map(lambda p: reduce_model(p, stage), paths):
            _show(rec)
            out.append(rec)
    return out


def controls() -> None:
    """The known answers and the relay copies. Prints the control table; the report reads the same records."""
    for mid in (REPRESSILATOR, TOGGLE):
        rec = reduce_model(R31 / f'{mid}.xml', 'controls')
        _show(rec)
        if rec['status'] != 'ok' or not rec.get('cuts'):
            continue
        out = WORK / 'controls' / f'{mid}_relay_src'
        rec['relay_rewired'] = relay_copy(R31 / f'{mid}.xml', rec, out)
        twin = reduce_model(out / f'{mid}.xml', 'controls', tag=f'{mid}_relay')
        _show(twin)


def listed(structure: str) -> dict[str, dict]:
    """Census records by model, from a results/*_structure_traj.jsonl file."""
    return {r['model']: r for r in map(json.loads, (ROOT / 'results' / structure).read_text().splitlines())}


def worth_running(mid: str, S: dict[str, dict]) -> bool:
    """False when the census record already says the model cannot be reduced (loops not all listed, or too many)."""
    rank = (S.get(mid, {}).get('defs') or {}).get('ref24_rank') or {}
    return bool(rank.get('complete')) and rank.get('c', MAX_LOOPS + 1) <= MAX_LOOPS


def main() -> None:
    """Dispatch a stage, or one of the two subprocess jobs (--prepare, --file)."""
    a = sys.argv[1:]
    if a[:1] == ['--prepare']:
        try:
            print(json.dumps(prepare(pathlib.Path(a[1]), pathlib.Path(a[2]))))
        except budget.Spent as e:
            print(json.dumps({'status': f'budget: {e}'}))
        return
    if a[:1] == ['--file']:
        print(json.dumps(file_answer(pathlib.Path(a[1]), a[2])))
        return
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 1
    if a[0] == 'controls':
        controls()
    elif a[0] == 'families':
        import truth_tests as TT

        run_many([R31 / f'{m}.xml' for ms in TT.FAMILIES.values() for m in ms], 'r31', jobs)
    elif a[0] == 'census':
        atlas = json.loads((ROOT / 'results' / 'fingerprints.json').read_text())['models']
        S = listed('r31_structure_traj.jsonl')
        filed = [m['model'] for m in atlas if m.get('row') in SIX and worth_running(m['model'], S)]
        run_many([R31 / f'{m}.xml' for m in filed], 'r31', jobs)
    elif a[0] == 'found':
        fam = json.loads((ROOT / 'results' / 'essential_loops_found_families.json').read_text())
        for stage, folder in (('r31', R31), ('holdout', HOLDOUT)):
            ids = sorted({m['model'] for f in fam['families'] for m in f['models'] if m['set'] == stage})
            run_many([folder / f'{m}.xml' for m in ids], stage, jobs)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
