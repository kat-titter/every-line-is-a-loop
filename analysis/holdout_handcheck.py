"""Hand check of the hold-out's candidate exceptions to the sign rules (results/holdout_score.json).

Reads:  results/holdout_score.json, results/holdout_dynamics.jsonl, data/holdout_curated/*.xml
Writes: results/holdout_handcheck.json
Run:    .venv/bin/python analysis/holdout_handcheck.py

The fail line (frozen 2026-11-16): one exception on the unfiltered graph that survives a hand check of the model.
For each candidate this prints the model's own equations and three facts the census's quick reading can miss:
  time     does a rate law or rule use the clock (then the model is driven, and the rules do not apply)?
  arrows   signs of every arrow (the Jacobian, by finite differences on the census's own right-hand side) at 600
           points along the model's run, not the census's 5: arrows found, and arrows that change sign (the theorems
           need arrows that keep their sign)
  loops    on that fuller graph: is there a brake (a loop with an odd number of switch-offs) and a self-feeding loop?
Usage: .venv/bin/python analysis/holdout_handcheck.py     (writes results/holdout_handcheck.json)
"""

from __future__ import annotations

import itertools
import json
import pathlib
import sys

import libsbml
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import fingerprints as FP  # noqa: E402
import truth_tests as TT  # noqa: E402

TT.DATA = ROOT / 'data' / 'holdout_curated'


def jac(rr: object, DY: object, ids: list[str], spset: set[str], x: np.ndarray) -> np.ndarray:
    """Central-difference Jacobian of the census right-hand side at x."""
    n = len(ids)
    J = np.zeros((n, n))
    for j in range(n):
        h = 1e-5 * max(abs(x[j]), 1e-6)
        a, b = x.copy(), x.copy()
        a[j] += h
        b[j] -= h
        J[:, j] = (FP.rhs_at(rr, DY, ids, spset, a) - FP.rhs_at(rr, DY, ids, spset, b)) / (2 * h)
    return J


def circuits(sign: list[list[str | None]]) -> tuple[bool, bool]:
    """(has a brake, has a self-feeding loop) of a sign graph; sign[i][j] in '+', '-', 'mixed', None: effect of j on i."""
    n = len(sign)
    neg = pos = False
    for k in range(2, n + 1):
        for nodes in itertools.permutations(range(n), k):
            if nodes[0] != min(nodes):
                continue
            arcs = [sign[nodes[(t + 1) % k]][nodes[t]] for t in range(k)]
            if any(a is None for a in arcs):
                continue
            if 'mixed' in arcs:
                neg = pos = True
                continue
            if arcs.count('-') % 2:
                neg = True
            else:
                pos = True
    return neg, pos


def main() -> None:
    """Print and record the hand check of every candidate exception; write results/holdout_handcheck.json."""
    score = json.loads((ROOT / 'results' / 'holdout_score.json').read_text())
    out = []
    for c in score['sign rules']['candidate exceptions']:
        mid = c['model']
        doc = libsbml.readSBMLFromFile(str(TT.DATA / f'{mid}.xml'))
        m = doc.getModel()
        text = libsbml.writeSBMLToString(doc)
        uses_time = 'symbol/time' in text
        piecewise = '<piecewise' in text
        delay = 'symbol/delay' in text
        print('\n==', mid, c['rule'], '|', (m.getName() or '')[:70])
        print(
            '   uses the clock:',
            uses_time,
            '| piecewise:',
            piecewise,
            '| delay:',
            delay,
            '| events:',
            m.getNumEvents(),
            '| functions:',
            m.getNumFunctionDefinitions(),
        )
        for r in m.getListOfReactions():
            kl = r.getKineticLaw()
            reactants = '+'.join(x.getSpecies() for x in r.getListOfReactants())
            products = '+'.join(x.getSpecies() for x in r.getListOfProducts())
            rate_law = libsbml.formulaToL3String(kl.getMath())[:150] if kl else None
            print(f'   {r.getId()}: {reactants} -> {products}  v = {rate_law}')
        for ru in m.getListOfRules():
            print(
                '   rule',
                'RATE' if ru.isRate() else 'ASSIGN',
                ru.getVariable(),
                '=',
                libsbml.formulaToL3String(ru.getMath())[:170],
            )
        rec = {
            'model': mid,
            'rule': c['rule'],
            'name': m.getName(),
            'uses the clock': uses_time,
            'piecewise': piecewise,
            'delay': delay,
            'events': m.getNumEvents(),
        }
        try:
            DY, rr, ids, spset, x0, assigned, rate_vars = TT.setup(mid)
            pts = []
            for T in (30.0, 300.0, 3000.0):
                DY.put_state(rr, ids, spset, x0)
                try:
                    rr.simulate(0, T, 200)
                    for _ in range(200):
                        rr.simulate(0, T / 200, 2)
                        pts.append(np.array([rr.getValue(DY.sel(s, spset)) for s in ids], float))
                except Exception as e:
                    print('   run to', T, 'failed:', repr(e)[:60])
            n = len(ids)
            seen = [[set() for _ in range(n)] for _ in range(n)]
            for x in pts:
                J = jac(rr, DY, ids, spset, x)
                scale = np.max(np.abs(J)) or 1.0
                for i in range(n):
                    for j in range(n):
                        if i != j and abs(J[i, j]) > 1e-9 * scale:
                            seen[i][j].add('+' if J[i, j] > 0 else '-')
            sign = [
                [
                    None if not seen[i][j] else ('mixed' if len(seen[i][j]) == 2 else next(iter(seen[i][j])))
                    for j in range(n)
                ]
                for i in range(n)
            ]
            arcs = {f'{ids[j]} -> {ids[i]}': sign[i][j] for i in range(n) for j in range(n) if sign[i][j]}
            neg, pos = circuits(sign)
            span = [
                float(np.ptp([p[k] for p in pts[-200:]]) / (abs(np.mean([p[k] for p in pts[-200:]])) + 1e-12))
                for k in range(n)
            ]
            rec.update(
                {
                    'molecules': ids,
                    'points': len(pts),
                    'arrows': arcs,
                    'arrows that change sign': [k for k, v in arcs.items() if v == 'mixed'],
                    'has a brake': neg,
                    'has a self-feeding loop': pos,
                    'swing over the last run': dict(zip(ids, [round(s, 3) for s in span])),
                }
            )
            print('   molecules', ids, '| points', len(pts), '| arrows', arcs)
            print(
                '   has a brake:',
                neg,
                '| has a self-feeding loop:',
                pos,
                '| arrows that change sign:',
                rec['arrows that change sign'],
                '| swing (last run):',
                rec['swing over the last run'],
            )
        except Exception as e:
            rec['error'] = repr(e)[:200]
            print('   could not check:', rec['error'])
        out.append(rec)
    D = {
        rec['model']: rec
        for rec in (json.loads(line) for line in (ROOT / 'results' / 'holdout_dynamics.jsonl').read_text().splitlines())
    }
    d = D['BIOMD0000000933']
    print('\n933 fixed points:', json.dumps(d.get('fixed_points'))[:600])
    (ROOT / 'results' / 'holdout_handcheck.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
