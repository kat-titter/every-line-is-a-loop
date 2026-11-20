"""Markdown tables for the counting report from tabulate.py's JSON (one or two sign modes).

Reads:  results/tables_traj.json and, optionally, results/tables_random.json (written by tabulate.py).
Writes: Markdown to stdout, redirected to results/tables.md.
Run:    python analysis/report_tables.py results/tables_traj.json results/tables_random.json > results/tables.md

Usage: python analysis/report_tables.py TRAJ.json [RANDOM.json] > results/tables.md
"""

from __future__ import annotations

import json
import sys
from typing import Any

RULE_NAMES = {
    'essay': "essay's (k, j)",
    'pf': "Sontag's k with j",
    'types4': 'per-loop types',
    'types3': 'only negative loops integrate',
}
DEF_NAMES = {
    'thomas': 'Thomas circuits',
    'ref24': 'reference 24 filters',
    'ref24_rank': 'reference 24 filters plus rank condition',
}


def _pct(x: int, n: int) -> str:
    """'x (share of n in percent)', or just x when n is 0."""
    return f"{x} ({100 * x / n:.0f}%)" if n else str(x)


def tables(T: dict[str, Any], label: str) -> list[str]:
    """Markdown lines for one sign mode's tables (tabulate.py's JSON), under a heading with the given label."""
    out = [f'### {label}', '']
    r = T['replication']
    out += [
        '| | Models | No negative circuit | No positive circuit | No filtered positive circuit |',
        '|---|---|---|---|---|',
    ]
    for k, v in r.items():
        n = v['models']
        out.append(
            f"| {k} | {n} | {_pct(v['no negative circuit'], n)} | {_pct(v['no positive circuit'], n)} | {_pct(v['no refined positive circuit'], n)} |"
        )
    out += [
        '',
        '| Definition | 0 loops | 1 | 2 | 3 | 4 to 10 | over 10 | over budget |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for d, Dd in T['defs'].items():
        x = Dd['distribution']
        out.append(
            f"| {DEF_NAMES[d]} | "
            + ' | '.join(str(x.get(k, 0)) for k in ('0', '1', '2', '3', '4 to 10', 'over 10', 'over budget'))
            + ' |'
        )
    out += [
        '',
        '| Definition | Row | Models | Loops share no arrow | ' + ' | '.join(RULE_NAMES[k] for k in RULE_NAMES) + ' |',
        '|---|---|---|---|' + '---|' * len(RULE_NAMES),
    ]
    for d, Dd in T['defs'].items():
        for nu, R in Dd['rows'].items():
            out.append(
                f"| {DEF_NAMES[d]} | {nu} | {R['models']} | {R['cactus']} | "
                + ' | '.join(f"{R[k]['occupied']} of {R[k]['predicted']}" for k in RULE_NAMES)
                + ' |'
            )
    out += [
        '',
        f"Theorem checks: {json.dumps(T['theorem_checks'])}",
        '',
        f"Integrators: {json.dumps(T['integrators'])}",
        '',
    ]
    rows = T['defs']['ref24_rank']['rows']
    out += [
        "The essay's test, kinds of behaviour per row (reference 24 filters plus rank condition):",
        '',
        '| Row | Predicted | Behaviours and mixtures | Merged into four | Not settled |',
        '|---|---|---|---|---|',
    ]
    for nu, R in rows.items():
        out.append(
            f"| {nu} | {(int(nu) + 1) ** 2} | {R['distinct_autonomous_behaviours']} | {len(R['coarse_behaviours'])} | {R['behaviours'].get('unsettled', 0)} |"
        )
    out += [
        '',
        'Running-total readings on the main definition (occupancy of (k, j) cells):',
        '',
        '| Row | Predicted | Strict | Loose | Paired |',
        '|---|---|---|---|---|',
    ]
    for nu, R in rows.items():
        out.append(
            f"| {nu} | {(int(nu) + 1) ** 2} | {R['essay']['occupied']} | {R.get('essay_near', {}).get('occupied', '')} | {R.get('essay_pair', {}).get('occupied', '')} |"
        )
    if 'paired_totals' in T:
        pt = T['paired_totals']
        out += [
            '',
            f"Paired running totals: {len(pt['models with one'])} models have one; small models with a loop through one: {pt['small models with a loop through one']}",
            '',
        ]
    if 'split' in T:
        out += ['', f"Amplifying loops after the filters, braking loops as drawn: {json.dumps(T['split'])}", '']
    return out


def main(*paths: str) -> None:
    """Print the tables of each JSON file in paths (trajectory signs first, then random signs) as Markdown."""
    lines = []
    for p, lab in zip(paths, ('trajectory signs', 'random signs')):
        with open(p) as fh:
            lines += tables(json.load(fh), lab)
    print('\n'.join(lines))


if __name__ == '__main__':
    main(*sys.argv[1:])
