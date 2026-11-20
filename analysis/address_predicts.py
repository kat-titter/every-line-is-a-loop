"""Does a model's loop address tell what it does, beyond the two sign rules?

Chemistry's second test (essay chapter 07, "the address predicts"), put to the loop table in published models.
Reads only files already in results/; no model is run. Standard library only.

Reads:  results/fingerprints.json, results/r31_dynamics.jsonl, results/r31_structure_traj.jsonl
Writes: results/address_predicts.json
Run:    /usr/bin/python3 analysis/address_predicts.py

PROTOCOL, FIXED 2026-11-16 BEFORE ANY ADDRESS-BY-ANSWER TABLE WAS LOOKED AT

Inputs
  results/fingerprints.json   per model: `row` (the atlas answer) and `address` = [loops, brakes, running totals],
                              strict reading, present for models with 0 to 3 loops whose loops were all listed
  results/r31_dynamics.jsonl  per model: `state_variables` (model size, the control that could fake the result)

Scope
  primary    status ok, answer in the six atlas rows, address known, 1 to 3 loops (the table's 29 squares)
  secondary  the same with loop-free models added (element zero)

Predictors, nested
  sign      (has a brake, has a self-feeding loop): what the two theorems already say
  address   (loops, brakes, running totals): the square of the table
  size      sign plus a size bin: state variables cut into q quantile bins, q = ceil(distinct addresses in scope /
            occupied sign strata), so size gets about as many cells as the address has

Statistic
  leave-one-out accuracy of a majority vote: predict a model's answer as the most common answer among the OTHER
  models sharing its predictor value; a model alone at its value, or a tie, takes the vote of its sign stratum, then
  of the whole scope. Chance = the share of the most common answer (always guess it).

Null
  answers shuffled inside each sign stratum (what the theorems know is kept), 10,000 shuffles, seed 20261116;
  p = (1 + shuffles with address accuracy >= observed) / (1 + shuffles).

FAIL LINE (primary scope). The address FAILS as a predictor if any one holds:
  (a) p >= 0.05
  (b) address accuracy minus sign accuracy < 5 percentage points
  (c) size accuracy >= address accuracy
PASS only if none holds.
VOID if the join breaks the atlas's own rules in scope (a ticking model with no brake, a remembering model with no
self-feeding loop) or its six row totals differ from results/fingerprints.json `rows`.

Control that should fail: the same test with the answers shuffled once across the whole scope (seed 7). It must FAIL.

What each outcome changes in the essay
  PASS  chapter 07's square "02 predicts" for the loop table gains a number; a blank's stated behaviour, read from
        its neighbours, has support in models.
  FAIL  beyond the two sign rules the square tells nothing about what a published model does: the 29 squares index
        what is permitted, and a blank's behaviour cannot be read from its neighbours on this evidence.
Either way the result is about published models at their published rates, not about living cells.

FIRST RUN, 2026-11-16 09:47: VOID by the join check. Ten ticking models sit at an address with no brake (seven at
1 loop 0 brakes, three at 2 loops 0 brakes): calcium and glycolytic oscillators whose brake the loop filters remove
(the essay's known limit, "remove the brakes of 10 clocks"). The sign rules hold on the unfiltered sign graph
(`plain_negative`, `plain_positive`), which is where the atlas's own rule reads them (circuit_figures.py ATLAS_RULE);
the address is counted after the filters. The first run's numbers are kept in the output under `primary`.

AMENDMENT, declared 2026-11-16 after the void and before the amended run. One change: the sign bits are read from
the unfiltered graph, as the atlas reads them. Predictors stay nested: sign = (plain_negative, plain_positive);
address = sign plus (loops, brakes, running totals); size = sign plus a size bin. Same statistic, null, seed rule
(seed + 1), fail line and control. Added, a control that should PASS, to show the test can: the sign bits against
answers shuffled across the whole zero-to-three scope (p < 0.05 expected, since the theorems are known to hold).
"""

from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = ['ticks', 'remembers', 'returns exactly', 'returns partly', 'rings', 'follows']
N_SHUFFLES, SEED = 10000, 20261116


def load() -> tuple[dict[str, object], list[dict[str, object]]]:
    """The atlas file and one record per filed model with a known address (answer, address, sign bits, size)."""
    F = json.loads((ROOT / 'results' / 'fingerprints.json').read_text())
    size = {}
    for line in (ROOT / 'results' / 'r31_dynamics.jsonl').read_text().splitlines():
        r = json.loads(line)
        size[r['model']] = r.get('state_variables')
    plain = {}
    for line in (ROOT / 'results' / 'r31_structure_traj.jsonl').read_text().splitlines():
        r = json.loads(line)
        plain[r['model']] = (bool(r.get('plain_negative')), bool(r.get('plain_positive')))
    recs = []
    for m in F['models']:
        if m.get('status') != 'ok' or m.get('row') not in ROWS or not m.get('address'):
            continue
        c, k, j = m['address']
        sv = size.get(m['model'])
        sv = len(sv) if isinstance(sv, list) else sv
        recs.append(
            {
                'model': m['model'],
                'answer': m['row'],
                'address': (c, k, j),
                'sign': (k >= 1, c - k >= 1),
                'plain': plain[m['model']],
                'size': sv,
            }
        )
    return F, recs


def vote(pool: collections.Counter[str], exclude_answer: str) -> str | None:
    """Most common answer in a Counter after removing one instance; None on an empty pool or a tie."""
    c = pool.copy()
    c[exclude_answer] -= 1
    best = c.most_common(2)
    if not best or best[0][1] <= 0:
        return None
    if len(best) > 1 and best[1][1] == best[0][1]:
        return None
    return best[0][0]


def loo_accuracy(answers: list[str], keys: list[object], signs: list[object]) -> float:
    """Leave-one-out accuracy (0 to 1) of a majority vote of answers among models sharing a key."""
    by_key, by_sign, overall = (
        collections.defaultdict(collections.Counter),
        collections.defaultdict(collections.Counter),
        collections.Counter(),
    )
    for a, k, s in zip(answers, keys, signs):
        by_key[k][a] += 1
        by_sign[s][a] += 1
        overall[a] += 1
    hit = 0
    for a, k, s in zip(answers, keys, signs):
        guess = vote(by_key[k], a)
        if guess is None:
            guess = vote(by_sign[s], a)
        if guess is None:
            guess = vote(overall, a)
        hit += guess == a
    return hit / len(answers)


def cond_mi(answers: list[str], keys: list[object], signs: list[object]) -> float:
    """I(answer; key | sign) in bits, plug-in estimate (biased up when cells are sparse; the shuffles carry the same bias)."""
    n = len(answers)
    nsk, ns, nsa, nska = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for a, k, s in zip(answers, keys, signs):
        nsk[s, k] += 1
        ns[s] += 1
        nsa[s, a] += 1
        nska[s, k, a] += 1
    return sum(v / n * math.log2(v * ns[s] / (nsk[s, k] * nsa[s, a])) for (s, k, a), v in nska.items())


def size_bins(recs: list[dict[str, object]], q: int) -> list[int]:
    """Bin index (0 to q - 1) of each record by quantile of its state-variable count."""
    vals = sorted(r['size'] for r in recs)
    cuts = [vals[min(len(vals) - 1, (i * len(vals)) // q)] for i in range(1, q)]
    return [sum(r['size'] >= c for c in cuts) for r in recs]


def run(recs: list[dict[str, object]], label: str, rng: random.Random, sign_key: str = 'sign') -> dict[str, object]:
    """One scope's accuracies, shuffle null, fail-line checks, join check and verdict."""
    answers = [r['answer'] for r in recs]
    signs = [r[sign_key] for r in recs]
    addr = [(r[sign_key], r['address']) for r in recs] if sign_key == 'plain' else [r['address'] for r in recs]
    n_addr, n_sign = len({r['address'] for r in recs}), len(set(signs))
    q = math.ceil(n_addr / n_sign)
    sz = list(zip(signs, size_bins(recs, q)))
    chance = collections.Counter(answers).most_common(1)[0][1] / len(recs)
    acc = {
        'sign': loo_accuracy(answers, signs, signs),
        'address': loo_accuracy(answers, addr, signs),
        'size': loo_accuracy(answers, sz, signs),
    }
    mi = cond_mi(answers, addr, signs)
    idx_by_sign = collections.defaultdict(list)
    for i, s in enumerate(signs):
        idx_by_sign[s].append(i)
    ge, ge_mi, null = 0, 0, []
    for _ in range(N_SHUFFLES):
        sh = answers[:]
        for idx in idx_by_sign.values():
            vals = [answers[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                sh[i] = v
        t = loo_accuracy(sh, addr, signs)
        null.append(t)
        ge += t >= acc['address'] - 1e-12
        ge_mi += cond_mi(sh, addr, signs) >= mi - 1e-12
    null.sort()
    p = (1 + ge) / (1 + N_SHUFFLES)
    fails = {
        'a_p_at_least_0.05': p >= 0.05,
        'b_lead_over_sign_under_5_points': acc['address'] - acc['sign'] < 0.05,
        'c_size_does_as_well': acc['size'] >= acc['address'],
    }
    # the join check: the atlas's own rules, inside this scope
    broken = [
        r['model']
        for r in recs
        if (r['answer'] == 'ticks' and not r[sign_key][0]) or (r['answer'] == 'remembers' and not r[sign_key][1])
    ]
    table = collections.defaultdict(collections.Counter)
    for r in recs:
        table[r['address']][r['answer']] += 1
    return {
        'scope': label,
        'sign_bits': 'after the loop filters (the address)'
        if sign_key == 'sign'
        else 'unfiltered graph (the atlas rule)',
        'n': len(recs),
        'distinct_addresses': n_addr,
        'sign_strata': n_sign,
        'size_bins': q,
        'chance': round(chance, 4),
        'accuracy': {k: round(v, 4) for k, v in acc.items()},
        'null_address_accuracy': {
            'median': round(null[len(null) // 2], 4),
            'p95': round(null[int(0.95 * len(null))], 4),
        },
        'p': round(p, 4),
        'cond_mi_bits': round(mi, 4),
        'p_cond_mi': round((1 + ge_mi) / (1 + N_SHUFFLES), 4),
        'fails': fails,
        'verdict': 'FAIL' if any(fails.values()) else 'PASS',
        'rule_breakers': broken,
        'answers': dict(collections.Counter(answers)),
        'table': {
            f'{a[0]:d} loops, {a[1]:d} brakes, {a[2]:d} totals': {row: t[row] for row in ROWS if t[row]}
            for a, t in sorted(table.items())
        },
    }


def main() -> int:
    """Run the primary, secondary, amended and control tests; write results/address_predicts.json; exit status 0."""
    F, recs = load()
    rng = random.Random(SEED)
    filed = collections.Counter(m['row'] for m in F['models'] if m.get('status') == 'ok' and m.get('row') in ROWS)
    rows_ok = all(filed[r] == F['rows'][r] for r in ROWS)
    primary = [r for r in recs if 1 <= r['address'][0] <= 3]
    out = {
        'protocol_fixed': '2026-11-16, before any address-by-answer table was read',
        'shuffles': N_SHUFFLES,
        'seed': SEED,
        'row_totals_match_atlas': rows_ok,
        'filed_models': sum(filed.values()),
        'with_address': len(recs),
        'primary': run(primary, 'one to three loops', rng),
        'secondary': run(recs, 'zero to three loops', rng),
    }
    ctl = [dict(r) for r in primary]
    shuffled = [r['answer'] for r in ctl]
    random.Random(7).shuffle(shuffled)
    for r, a in zip(ctl, shuffled):
        r['answer'] = a
    c = run(ctl, 'control: answers shuffled across the scope', rng)
    c['rule_breakers'] = len(c['rule_breakers'])  # a shuffle breaks the rules by design; count only
    out['control_should_fail'] = c
    void = (not rows_ok) or bool(out['primary']['rule_breakers'])
    out['void'] = void
    rng2 = random.Random(SEED + 1)
    out['amended_primary'] = run(primary, 'amended: one to three loops', rng2, 'plain')
    out['amended_secondary'] = run(recs, 'amended: zero to three loops', rng2, 'plain')
    ctl2 = [dict(r, answer=a) for r, a in zip(primary, shuffled)]
    c2 = run(ctl2, 'amended control: answers shuffled', rng2, 'plain')
    c2['rule_breakers'] = len(c2['rule_breakers'])
    out['amended_control_should_fail'] = c2
    out['amended_void'] = (not rows_ok) or bool(out['amended_primary']['rule_breakers'])
    # control that should pass: the theorems' two bits against answers shuffled across the whole scope
    ans = [r['answer'] for r in recs]
    sg = [r['plain'] for r in recs]
    obs = loo_accuracy(ans, sg, sg)
    ge = 0
    for _ in range(N_SHUFFLES):
        sh = ans[:]
        rng2.shuffle(sh)
        ge += loo_accuracy(sh, sg, sg) >= obs - 1e-12
    chance = collections.Counter(ans).most_common(1)[0][1] / len(ans)
    out['control_should_pass'] = {
        'scope': 'sign bits, zero to three loops',
        'n': len(ans),
        'chance': round(chance, 4),
        'accuracy': round(obs, 4),
        'p': round((1 + ge) / (1 + N_SHUFFLES), 4),
        'verdict': 'PASS' if (1 + ge) / (1 + N_SHUFFLES) < 0.05 else 'FAIL',
    }
    (ROOT / 'results' / 'address_predicts.json').write_text(json.dumps(out, indent=1))
    for key in (
        'primary',
        'secondary',
        'control_should_fail',
        'amended_primary',
        'amended_secondary',
        'amended_control_should_fail',
    ):
        r = out[key]
        acc, null = r['accuracy'], r['null_address_accuracy']
        failed = [k for k, v in r['fails'].items() if v]
        print(
            f"{r['scope']:<44} n={r['n']:<4d} addresses={r['distinct_addresses']:<3d} chance={r['chance']:.3f}"
            f" sign={acc['sign']:.3f} address={acc['address']:.3f} size={acc['size']:.3f}"
            f"  null median={null['median']:.3f} p95={null['p95']:.3f}  p={r['p']:.4f}"
            f"  MI={r['cond_mi_bits']:.3f} bits (p={r['p_cond_mi']:.4f})  {r['verdict']} {failed}"
        )
    print(
        'first run: row totals match atlas:',
        rows_ok,
        '| rule breakers in primary scope:',
        len(out['primary']['rule_breakers']),
        '| VOID' if void else '| join ok',
    )
    print(
        'amended:   rule breakers in primary scope:',
        len(out['amended_primary']['rule_breakers']),
        '| VOID' if out['amended_void'] else '| join ok',
    )
    print('control that should pass:', out['control_should_pass'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
