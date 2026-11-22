"""Score the essential-loops test: three fail lines and three controls, from the per-model records.

Reads:  build/essential_loops/{controls,r31,holdout}/*.json (essential_loops.py), results/fingerprints.json,
        results/r31_structure_traj.jsonl, results/r31_dynamics.jsonl, results/essential_loops_found_families.json
Writes: results/essential_loops.json
Run:    .venv/bin/python analysis/essential_loops_report.py

Every threshold and counting rule is in essential_loops.py's docstring, written before the first run. Two more are
fixed here, also before the first run:
  - Fail line 3 is scored on the rule-found families with at least two reduced drawings; the others are counted.
  - The control that should fail compares the hand-picked families with random families: for each family, as many
    models as it has reduced drawings, each drawn with the same atlas answer as the drawing it replaces, from the
    reduced release-31 models outside every hand-picked family (10,000 draws, seed 20261122). The control holds if
    random families agree less often than the real ones (p = share of draws with at least as many agreeing).
    Pairwise agreement of all same-answer pairs is given beside it.
"""

from __future__ import annotations

import collections
import itertools
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import address_predicts as AP  # noqa: E402
import essential_loops as EL  # noqa: E402
import truth_tests as TT  # noqa: E402

DRAWS, SEED = 10000, 20261122


def records(stage: str) -> dict[str, dict]:
    """Per-model records of one stage, by tag."""
    return {p.stem: json.loads(p.read_text()) for p in sorted((EL.WORK / stage).glob('*.json'))}


def reduced(rec: dict | None) -> tuple[int, ...] | None:
    return tuple(rec['reduced']) if rec and rec.get('status') == 'ok' and rec.get('reduced') is not None else None


def family_row(name: str, ids: list[str], R: dict[str, dict]) -> dict:
    """One family: each drawing's raw and reduced address, and whether the reduced (and raw) addresses agree."""
    rows = [
        {
            'model': m,
            'status': R.get(m, {}).get('status', 'not run'),
            'answer': (R.get(m, {}).get('answer') or {}).get('row'),
            'raw': R.get(m, {}).get('raw'),
            'reduced': R.get(m, {}).get('reduced'),
            'reduced_without_lost': R.get(m, {}).get('reduced_without_lost'),
        }
        for m in ids
    ]
    red = [tuple(r['reduced']) for r in rows if r['status'] == 'ok' and r['reduced'] is not None]
    raw = [tuple(r['raw']) for r in rows if r['raw'] is not None]
    return {
        'family': name,
        'drawings': rows,
        'reduced_drawings': len(red),
        'agrees': len(red) >= 2 and len(set(red)) == 1,
        'raw_agrees': len(raw) >= 2 and len(raw) == len(rows) and len(set(raw)) == 1,
    }


def control_known(C: dict[str, dict]) -> dict:
    """The repressilator, Gardner's toggle and their relay copies."""
    rep, tog = C.get(EL.REPRESSILATOR, {}), C.get(EL.TOGGLE, {})
    out = {
        'repressilator': {k: rep.get(k) for k in ('status', 'raw', 'reduced', 'settled')},
        'toggle': {k: tog.get(k) for k in ('status', 'raw', 'reduced', 'settled')},
        'repressilator_one_essential_brake': rep.get('reduced', [None] * 3)[:2] == [1, 1],
        'toggle_one_essential_self_feeding_loop': tog.get('reduced', [None] * 3)[:2] == [1, 0],
    }
    for key, mid in (('repressilator', EL.REPRESSILATOR), ('toggle', EL.TOGGLE)):
        twin = C.get(f'{mid}_relay', {})
        out[f'{key}_relay'] = {k: twin.get(k) for k in ('status', 'raw', 'reduced')}
        out[f'{key}_relay_same_address'] = reduced(twin) is not None and reduced(twin) == reduced(C.get(mid))
    out['holds'] = all(v for k, v in out.items() if isinstance(v, bool))
    return out


def predicts(R: dict[str, dict]) -> dict:
    """address_predicts.run (amended: sign bits from the unfiltered graph) with the reduced, then the raw, address."""
    size = {}
    for line in (ROOT / 'results' / 'r31_dynamics.jsonl').read_text().splitlines():
        r = json.loads(line)
        size[r['model']] = (
            len(r['state_variables']) if isinstance(r.get('state_variables'), list) else r.get('state_variables')
        )
    S = EL.listed('r31_structure_traj.jsonl')
    recs = [
        {
            'model': m,
            'answer': r['answer']['row'],
            'reduced': reduced(r),
            'raw': tuple(r['raw']),
            'plain': (bool(S[m].get('plain_negative')), bool(S[m].get('plain_positive'))),
            'size': size.get(m),
        }
        for m, r in R.items()
        if reduced(r) is not None and r['raw'][0] >= 1 and m in S and size.get(m) is not None
    ]
    out = {}
    for label, scope in (('1 to 16 loops', recs), ('1 to 3 loops', [r for r in recs if r['raw'][0] <= 3])):
        for key in ('reduced', 'raw'):
            rng = random.Random(AP.SEED + 1)
            run = AP.run([dict(r, address=r[key]) for r in scope], f'{key} address, {label}', rng, 'plain')
            run['rule_breakers'] = len(run['rule_breakers'])
            out[f'{key}, {label}'] = run
    return out


def control_random(fams: list[dict], R: dict[str, dict], hand: set[str]) -> dict:
    """Random families of same-answer models against the real ones; and all same-answer pairs."""
    pool = collections.defaultdict(list)
    for m, r in R.items():
        if reduced(r) is not None and m not in hand:
            pool[r['answer']['row']].append(reduced(r))
    shapes = [
        [d['answer'] for d in f['drawings'] if d['status'] == 'ok' and d['reduced'] is not None]
        for f in fams
        if f['reduced_drawings'] >= 2
    ]
    observed = sum(f['agrees'] for f in fams)
    rng, hits, total = random.Random(SEED), 0, 0
    for _ in range(DRAWS):
        n = 0
        for shape in shapes:
            draw = [rng.choice(pool[a]) for a in shape if pool[a]]
            n += len(draw) >= 2 and len(set(draw)) == 1
        hits += n >= observed
        total += n
    same = [a == b for row in pool.values() for a, b in itertools.combinations(row, 2)]
    fam_pairs = [
        tuple(a['reduced']) == tuple(b['reduced'])
        for f in fams
        for a, b in itertools.combinations([d for d in f['drawings'] if d['status'] == 'ok' and d['reduced']], 2)
        if a['answer'] == b['answer']
    ]
    return {
        'families_scored': len(shapes),
        'families_agreeing': observed,
        'random_families_agreeing_mean': round(total / DRAWS, 3),
        'p_random_at_least_observed': round((1 + hits) / (1 + DRAWS), 4),
        'same_answer_pairs': {'n': len(same), 'agree': sum(same)},
        'family_same_answer_pairs': {'n': len(fam_pairs), 'agree': sum(fam_pairs)},
        'holds': (total / DRAWS < observed and (1 + hits) / (1 + DRAWS) < 0.05) if shapes and same else None,
    }


def census(R: dict[str, dict]) -> dict:
    """What happened to each of the 392 labelled models, and the reduced addresses of the ticking ones."""
    atlas = json.loads((ROOT / 'results' / 'fingerprints.json').read_text())['models']
    S = EL.listed('r31_structure_traj.jsonl')
    fate, moved, ticking = collections.Counter(), [], collections.Counter()
    for m in atlas:
        mid, row, r = m['model'], m.get('row'), R.get(m['model'])
        if row not in EL.SIX:
            fate['not in the six rows of the atlas'] += 1
        elif not EL.worth_running(mid, S):
            rank = (S.get(mid, {}).get('defs') or {}).get('ref24_rank') or {}
            fate['loops not all listed' if not rank.get('complete') else f'more than {EL.MAX_LOOPS} loops'] += 1
        elif r is None:
            fate['not run'] += 1
        elif reduced(r) is None:
            fate['not reduced: ' + (r['status'] if r['status'] != 'ok' else 'a cut was unread')] += 1
        else:
            fate['reduced'] += 1
        if r and r.get('answer') and r['answer'].get('row') != row:
            moved.append({'model': mid, 'atlas': row, 'refiled': r['answer'].get('row') or r['answer'].get('status')})
        if row == 'ticks':
            ticking[str(list(reduced(r))) if reduced(r) is not None else 'not reduced'] += 1
    values = {k: v for k, v in ticking.items() if k != 'not reduced'}
    return {
        'labelled_models': len(atlas),
        'fate': dict(fate),
        'refiled_in_another_row': moved,
        'ticking_models': sum(ticking.values()),
        'ticking_reduced': sum(values.values()),
        'ticking_reduced_addresses': dict(sorted(values.items(), key=lambda kv: -kv[1])),
        'ticking_distinct_values': len(values),
    }


def found(R: dict[str, dict], H: dict[str, dict]) -> dict:
    """Fail line 3: the rule-found families."""
    listed = json.loads((ROOT / 'results' / 'essential_loops_found_families.json').read_text())['families']
    both = {**H, **R}
    rows = [family_row(f'rule family {f["id"]}', [m['model'] for m in f['models']], both) for f in listed]
    scored = [r for r in rows if r['reduced_drawings'] >= 2]
    agree = sum(r['agrees'] for r in scored)
    return {
        'families_listed': len(rows),
        'families_scored': len(scored),
        'agree': agree,
        'raw_agree_among_scored': sum(r['raw_agrees'] for r in scored),
        'holds': bool(scored) and agree / len(scored) >= 2 / 3,
        'families': scored,
    }


def main() -> None:
    """Score everything that has been run and write results/essential_loops.json."""
    C, R, H = records('controls'), records('r31'), records('holdout')
    fams = [family_row(n, ids, R) for n, ids in TT.FAMILIES.items()]
    five = [f for f in fams if f['family'] in EL.PLAN_FAMILIES]
    hand = {m for ids in TT.FAMILIES.values() for m in ids}
    atlas = json.loads((ROOT / 'results' / 'fingerprints.json').read_text())['models']
    six = {m['model'] for m in atlas if m.get('row') in EL.SIX}
    A = {m: r for m, r in R.items() if m in six}  # the labelled models only: family runs also reduce forced models
    cen, pred = census(R), predicts(A)
    lead = pred['reduced, 1 to 16 loops']
    line2 = cen['ticking_distinct_values'] >= 3 and lead['verdict'] == 'PASS'
    out = {
        'protocol': 'analysis/essential_loops.py docstring, committed 75eb035 before any model was cut',
        'settings': {'max_loops': EL.MAX_LOOPS, 'relay_speedup': EL.RELAY_SPEEDUP, 'draws': DRAWS, 'seed': SEED},
        'controls': {'known_answers_and_relay': control_known(C), 'random_families': control_random(five, A, hand)},
        'fail_line_1': {
            'families_agreeing': sum(f['agrees'] for f in five),
            'of': len(five),
            'raw_agreeing': sum(f['raw_agrees'] for f in five),
            'holds': sum(f['agrees'] for f in five) >= 4,
            'families': five,
            'outside_the_fail_line': [f for f in fams if f['family'] not in EL.PLAN_FAMILIES],
        },
        'fail_line_2': {'holds': line2, 'census': cen, 'predicts': pred},
        'fail_line_3': found(R, H),
        'models': {
            stage: {
                t: {
                    k: r.get(k)
                    for k in (
                        'model',
                        'status',
                        'answer',
                        'settled',
                        'raw',
                        'reduced',
                        'reduced_without_lost',
                        'essential',
                        'loops',
                        'cuts',
                    )
                }
                for t, r in recs.items()
            }
            for stage, recs in (('controls', C), ('r31', R), ('holdout', H))
        },
    }
    (ROOT / 'results' / 'essential_loops.json').write_text(json.dumps(out, indent=1))
    k = out['controls']['known_answers_and_relay']
    print(
        'controls: known answers and relay',
        'HOLD' if k['holds'] else 'FAIL',
        {a: b for a, b in k.items() if isinstance(b, bool)},
    )
    print('control: random families', out['controls']['random_families'])
    print(
        'fail line 1:',
        out['fail_line_1']['families_agreeing'],
        '/',
        len(five),
        'raw',
        out['fail_line_1']['raw_agreeing'],
    )
    print('fail line 2:', line2, cen['ticking_reduced_addresses'], lead['accuracy'], lead['p'], lead['verdict'])
    print('fail line 3:', {a: b for a, b in out['fail_line_3'].items() if a != 'families'})
    print('fate', cen['fate'])


if __name__ == '__main__':
    main()
