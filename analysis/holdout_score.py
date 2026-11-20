"""Score the hold-out census against the fail lines frozen on 2026-11-16 (Figure 1 of proto/tests.html).

    python3 analysis/holdout_score.py      # reads results/holdout_* and release 31's results, writes results/holdout_score.json

Reads:  results/holdout_ids.json, holdout_manifest.json, holdout_structure_traj.jsonl, holdout_dynamics.jsonl,
        holdout_truth_tests.json, holdout_fingerprints.json, holdout_address_predicts.json, holdout_tables_traj.json,
        holdout_robust_return.json, and release 31's results/tables_traj.json
Writes: results/holdout_score.json
Run:    python3 analysis/holdout_score.py   (standard library only)

Definitions, fixed before the hold-out results existed (written while the census was still running):
  sign rules     FAIL if truth_tests lists a ticking model with no brake or a two-state model with no self-feeding
                 loop, on the unfiltered graph, and the exception survives a hand check (the hand check is a person's;
                 this script lists the candidates).
  strength       rings single as drawn (defs.thomas.c == 1, as fold_census.truth_numbers counts them), status ok,
                 gain read. A miss is the forbidden case: a ring that ticks with gain at or below its floor.
                 FAIL if misses / rings > 1/10. Calm rings above the floor are reported, not counted (the theorem
                 allows them).
  six answers    FAIL if follows / filed > 1/2. The second half of the line (a new shape in 5 of 20 random "follows"
                 traces, read blind) needs a person: the 20 are drawn here with seed 20261116 and listed.
  blank squares  strict reading (tables_traj defs.ref24_rank rows[n].essay.cells). FAIL if no running-total square
                 (totals >= 1, one to three loops) is filled in the hold-out that release 31 left empty, or if a row
                 of two or three loops shows more kinds of behaviour (distinct_autonomous_behaviours) than squares.
  the address    results/holdout_address_predicts.json, amended form, primary scope: the script's own verdict.
"""

from __future__ import annotations

import collections
import json
import pathlib
import random
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
R = ROOT / 'results'


def J(name: str) -> Any:
    """A results/ JSON file, parsed."""
    return json.loads((R / name).read_text())


def JL(name: str) -> list[dict[str, Any]]:
    """A results/ JSON-lines file, one record per line."""
    return [json.loads(line) for line in (R / name).read_text().splitlines()]


def main() -> None:
    """Score the hold-out against the frozen fail lines, write results/holdout_score.json and print the verdicts."""
    out = {}
    ids = J('holdout_ids.json')
    man = J('holdout_manifest.json')
    S = {r['model']: r for r in JL('holdout_structure_traj.jsonl')}
    D = {r['model']: r for r in JL('holdout_dynamics.jsonl')}
    T = J('holdout_truth_tests.json')
    F = J('holdout_fingerprints.json')
    A = J('holdout_address_predicts.json')
    tab, tab31 = J('holdout_tables_traj.json'), J('tables_traj.json')

    def short_name(m: str) -> str:
        return (S.get(m, {}).get('name') or '')[:60]

    # funnel
    ok = [m for m, r in S.items() if r.get('status') == 'ok']
    complete = [m for m in ok if (S[m].get('defs') or {}).get('ref24_rank', {}).get('complete')]
    small = [m for m in complete if S[m]['defs']['ref24_rank']['c'] in (1, 2, 3)]
    own = [m for m, d in D.items() if d.get('status') == 'ok' and not d.get('forced')]
    filed = {k: v for k, v in F['rows'].items() if k != 'flat'}
    out['funnel'] = {
        'listed': len(ids['holdout']),
        'downloaded': sum(1 for v in man.values() if v.get('sha256')),
        'structure records': len(S),
        'read as equations': len(ok),
        'every loop listed': len(complete),
        'one to three loops': len(small),
        'run on their own': len(own),
        'match a behaviour label': T['rules']['autonomous'],
        'atlas read': sum(1 for m in F['models'] if m.get('status') == 'ok'),
        'atlas filed': sum(filed.values()),
        'structure status': dict(collections.Counter((r.get('status') or '')[:40] for r in S.values()).most_common(8)),
        'atlas status': dict(collections.Counter(m.get('status') for m in F['models']).most_common(8)),
    }

    # sign rules
    ru = T['rules']
    exc = [
        {'model': m, 'name': short_name(m), 'rule': 'ticks with no brake'} for m in ru['clock_without_braking_loop']
    ] + [
        {'model': m, 'name': short_name(m), 'rule': 'two states with no self-feeding loop'}
        for m in ru['memory_without_amplifying_loop']
    ]
    out['sign rules'] = {
        'n': ru['autonomous'],
        'clocks': ru['clock'],
        'switches': ru['memory'],
        'candidate exceptions': exc,
        'verdict': 'PASS' if not exc else 'CANDIDATES: hand check each model before calling it',
    }

    # strength
    rings = [r for r in T['gain_brake'] if r.get('status') == 'ok' and r.get('G') is not None]
    raw = {r['model']: S[r['model']]['defs']['thomas']['c'] for r in rings}
    single = [r for r in rings if raw[r['model']] == 1]
    miss = [r for r in single if r['ticks'] and r['G'] <= r['threshold']]
    calm_above = [r for r in single if not r['ticks'] and r['G'] >= r['threshold']]
    miss_all = [r for r in rings if r['ticks'] and r['G'] <= r['threshold']]

    def show(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {'model': r['model'], 'name': r.get('name'), 'gain': r['G'], 'floor': r['threshold'], 'ticks': r['ticks']}
            for r in rs
        ]

    out['strength'] = {
        'rings read': len(rings),
        'single as drawn': len(single),
        'misses (ticks at or below floor)': show(miss),
        'calm above floor (allowed, reported)': show(calm_above),
        'misses counting rings the filters leave': show(miss_all),
        'unread rings': [
            {'model': r['model'], 'why': r.get('status') or r.get('why')} for r in T['gain_brake'] if r not in rings
        ],
        'verdict': ('NO RINGS' if not single else 'FAIL' if len(miss) / len(single) > 0.1 else 'PASS'),
    }

    # six answers
    n_filed = sum(filed.values())
    follows = sorted(m['model'] for m in F['models'] if m.get('status') == 'ok' and m.get('row') == 'follows')
    twenty = random.Random(20261116).sample(follows, min(20, len(follows)))
    out['six answers'] = {
        'rows': F['rows'],
        'filed': n_filed,
        'follows share': round(F['rows']['follows'] / n_filed, 4) if n_filed else None,
        'release 31 follows share': round(111 / 273, 4),
        'twenty for the blind read': [{'model': m, 'name': short_name(m)} for m in twenty],
        'blind read': 'not done: a person reads the traces',
        'verdict (catch-all half)': 'FAIL' if n_filed and F['rows']['follows'] / n_filed > 0.5 else 'PASS',
    }

    # blank squares
    def cells(t):
        rows = t['defs']['ref24_rank']['rows']
        return {(int(n), *eval(c)): v for n in rows for c, v in rows[n]['essay']['cells'].items()}

    new, old = cells(tab), cells(tab31)
    totals_new = {k: v for k, v in new.items() if k[2] >= 1}
    newly = {k: v for k, v in totals_new.items() if k not in old}
    kinds = {
        n: (tab['defs']['ref24_rank']['rows'][n]['distinct_autonomous_behaviours'], (int(n) + 1) ** 2)
        for n in tab['defs']['ref24_rank']['rows']
    }
    over = [n for n in ('2', '3') if n in kinds and kinds[n][0] > kinds[n][1]]
    out['blank squares'] = {
        'squares filled in the hold-out (loops, brakes, totals)': {str(k): v for k, v in sorted(new.items())},
        'running-total squares filled': {str(k): v for k, v in sorted(totals_new.items())},
        'newly filled, empty in release 31': {str(k): v for k, v in sorted(newly.items())},
        'kinds of behaviour against squares, by row': {n: list(v) for n, v in kinds.items()},
        'models per row': {
            n: tab['defs']['ref24_rank']['rows'][n]['models'] for n in tab['defs']['ref24_rank']['rows']
        },
        'verdict': 'FAIL' if (not newly or over) else 'PASS',
        'why': ('no running-total square newly filled' if not newly else '')
        + (f'; row(s) {over} exceed their squares' if over else ''),
    }

    # the address
    P = A['amended_primary']
    out['the address'] = {
        'n': P['n'],
        'squares': P['distinct_addresses'],
        'chance': P['chance'],
        'accuracy': P['accuracy'],
        'p': P['p'],
        'fails': P['fails'],
        'verdict': 'VOID' if A['amended_void'] else P['verdict'],
        'first form void': A['void'],
        'first form': {
            'accuracy': A['primary']['accuracy'],
            'p': A['primary']['p'],
            'rule breakers': len(A['primary']['rule_breakers']),
        },
        'with loop-free models': {
            'n': A['amended_secondary']['n'],
            'accuracy': A['amended_secondary']['accuracy'],
            'p': A['amended_secondary']['p'],
            'fails': A['amended_secondary']['fails'],
        },
        'control should fail': A['amended_control_should_fail']['verdict'],
        'control should pass': A['control_should_pass'],
    }

    # exact returns, for the regulator row (no fail line rides on it here)
    RR = J('holdout_robust_return.json')
    rob = [m for m in RR if any(q.get('robust') for q in m.get('pairs', []))]
    out['exact returns'] = {
        'exact': len(RR),
        'robust': len(rob),
        'robust in rows one to three': [
            {'model': m['model'], 'name': m.get('name'), 'running_totals': m.get('running_totals')}
            for m in rob
            if 1 <= (m.get('loops') or 0) <= 3
        ],
    }

    (R / 'holdout_score.json').write_text(json.dumps(out, indent=1, default=str))
    for k in ('sign rules', 'strength', 'six answers', 'blank squares', 'the address'):
        v = out[k]
        print(f"{k:<14} {v.get('verdict') or v.get('verdict (catch-all half)')}")
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
