"""Two audits of the census, read from the results files alone (no model is rerun; about a second).

1. What a clean record is worth. The two proven rules (a switch needs a self-feeding loop, a clock needs a brake)
   are theorems, so a clean record checks the census. How hard a check it was depends on how many failures chance
   would have sent: if behaviour had nothing to do with loops, how many switches would the models with no
   self-feeding loop hold, and how many clocks would the models with no brake keep? Hypergeometric, on the 392
   autonomous models with a behaviour label, with the same loop flags as truth_tests.py. Run backwards, the rules
   give how often a loop forecasts its behaviour.
2. The loose reading's dial. integrators.py calls a molecule a near running total when its own level moves its net
   rate by less than a tenth of the flow through it, at the last state reached. Sweep that cut and count the
   filled elements of rows one to three (ref24_rank, as tabulate.py's essay_near), then list the models that fill
   the elements the strict reading leaves empty once the cut sits near zero. Ratios are stored rounded to four
   decimals, so "zero" means below 0.00005.

Usage: python3 analysis/audit.py            writes results/audit.json
       python3 analysis/audit.py --check    also fails if the essay's sentences no longer match the numbers
"""
import collections
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / 'results'
CUTS = [0.0, 1e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0]  # 0.0 means "reads as zero"; 1.0 takes every stored ratio
VOLTAGE = ('V', 'V_membrane')


def load(name):
    return {r['model']: r for r in map(json.loads, open(RES / name))}


def p_none(total, marked, hits):
    """Chance that none of `hits` behaviours land among the `total - marked` models without the loop, if behaviour
    ignored loops: draw `hits` of `total` without replacement and miss every model lacking the loop."""
    return math.comb(marked, hits) / math.comb(total, hits)


def rules(S, D):
    auto = [m for m, d in D.items() if d.get('status') == 'ok' and not d.get('forced') and d.get('behaviours')]
    pos = {m for m in auto if S.get(m, {}).get('plain_positive') or S.get(m, {}).get('refined_positive')}
    neg = {m for m in auto if S.get(m, {}).get('plain_negative')}
    mem = {m for m in auto if 'multistable' in D[m]['behaviours']}
    osc = {m for m in auto if 'oscillating' in D[m]['behaviours']}
    n = len(auto)
    out = {'autonomous': n,
           'switch': {'models_with_loop': len(pos), 'models_without': n - len(pos), 'behaving': len(mem),
                      'behaving_with_loop': len(mem & pos), 'behaving_without_loop': len(mem - pos),
                      'expected_without_by_chance': len(mem) * (n - len(pos)) / n,
                      'p_none_by_chance': p_none(n, len(pos), len(mem))},
           'clock': {'models_with_loop': len(neg), 'models_without': n - len(neg), 'behaving': len(osc),
                     'behaving_with_loop': len(osc & neg), 'behaving_without_loop': len(osc - neg),
                     'expected_without_by_chance': len(osc) * (n - len(neg)) / n,
                     'p_none_by_chance': p_none(n, len(neg), len(osc))}}
    return out


def rows(S):
    """Row-one-to-three models under ref24_rank with their loop lists (the population tabulate.py fills)."""
    for k, r in S.items():
        d = r.get('defs', {}).get('ref24_rank', {})
        if r.get('status') == 'ok' and d.get('complete') and 1 <= d['c'] <= 3 and r.get('loop_list') is not None:
            yield k, d['c'], r


def cell(r, marked):
    kk = sum(1 for l in r['loop_list'] if l['sign'] == '-')
    return kk, sum(1 for l in r['loop_list'] if marked(l))


def dial(S, I, D):
    ratios = {k: (v.get('ratios') or {}) if v.get('status') == 'ok' else {} for k, v in I.items()}
    strict = collections.defaultdict(set)
    for k, nu, r in rows(S):
        strict[nu].add(cell(r, lambda l: l['integrates']))
    sweep = {}
    for cut in CUTS:
        occ = collections.defaultdict(set)
        for k, nu, r in rows(S):
            near = {n for n, v in ratios.get(k, {}).items() if (v == 0 if cut == 0.0 else v < cut)}
            occ[nu].add(cell(r, lambda l: bool(set(l['nodes']) & near)))
        sweep[str(cut)] = {'rows': {nu: len(occ[nu]) for nu in (1, 2, 3)}, 'filled': sum(len(occ[nu]) for nu in (1, 2, 3))}
    # who fills the elements that appear once the cut sits at zero
    new = collections.defaultdict(list)
    for k, nu, r in rows(S):
        zero = {n for n, v in ratios.get(k, {}).items() if v == 0}
        c = cell(r, lambda l: bool(set(l['nodes']) & zero))
        if c not in strict[nu]:
            on = sorted({n for l in r['loop_list'] for n in l['nodes']} & zero)
            new[(nu, c)].append({'model': k, 'name': r.get('name'), 'nodes': on,
                                 'behaviours': D.get(k, {}).get('behaviours'), 'voltage': all(n in VOLTAGE for n in on)})
    models = {m['model']: m for ms in new.values() for m in ms}
    volt = [m for m in models.values() if m['voltage']]
    allv = [r for v in I.values() if v.get('status') == 'ok' for r in (v.get('ratios') or {}).values()]
    half_decades = collections.Counter(math.floor(2 * math.log10(x)) / 2 for x in allv if x > 0)
    return {'strict': {'rows': {nu: len(strict[nu]) for nu in (1, 2, 3)}, 'filled': sum(len(strict[nu]) for nu in (1, 2, 3))},
            'sweep': sweep,
            'new_at_zero': {f'row {nu} {c}': ms for (nu, c), ms in sorted(new.items())},
            'new_cells_at_zero': len(new), 'models_at_zero': len(models), 'voltage_models': len(volt),
            'voltage_models_oscillate': sum(1 for m in volt if 'oscillating' in (m['behaviours'] or [])),
            'cells_on_voltage_alone': sum(1 for ms in new.values() if all(m['voltage'] for m in ms)),
            'readings_below_one': len(allv), 'readings_at_zero': sum(1 for x in allv if x == 0),
            'readings_by_half_decade': {str(b): half_decades[b] for b in sorted(half_decades)}}


def odds(p):
    """'one in N million' with N rounded, for the essay's prose."""
    return f'one in {round(1 / p / 1e6)} million'


def check(a):
    s = (ROOT / 'every-line-is-a-loop.html').read_text(encoding='utf-8')
    sw, cl, dl = a['rules']['switch'], a['rules']['clock'], a['dial']
    sweep = dl['sweep']
    want = [
        f"{sw['models_without']} have no self-feeding loop",
        f"{sw['expected_without_by_chance']:.1f} switches",
        f"{cl['models_without']} have no brake",
        f"tick {round(cl['expected_without_by_chance'])} times",
        odds(cl['p_none_by_chance']),
        f"about {round(math.log2(1 / cl['p_none_by_chance']))} tails in a row",
        f"{sw['models_with_loop']} of the {a['rules']['autonomous']} carry a self-feeding loop and {sw['behaving_with_loop']} switch",
        f"{cl['models_with_loop']} carry a brake and {cl['behaving_with_loop']} tick",
        f"Strict, {dl['strict']['filled']} of 29",
        f"reads as zero: {sweep['0.0']['filled']}, and still {sweep['0.01']['filled']} with the dial at a hundredth",
        f"the cut used above, {sweep['0.1']['filled']}; at one, {sweep['1.0']['filled']}",
        f"The {dl['new_cells_at_zero']} elements that arrive at zero rest on {dl['models_at_zero']} models",
        f"{dl['cells_on_voltage_alone']} of the {dl['new_cells_at_zero']} rest on voltages alone",
        f"{dl['readings_below_one']:,} readings below one",
        f"pile of {dl['readings_at_zero']} that read as zero",
    ]
    assert 0.4 < sw['p_none_by_chance'] < 0.6, 'the essay says "about half the time"'
    assert dl['voltage_models'] == 5 and dl['voltage_models_oscillate'] == 5, 'the essay says five voltages, all oscillating'
    assert sw['behaving_without_loop'] == 0 and cl['behaving_without_loop'] == 0, 'a proven rule broke'
    missing = [w for w in want if w not in s]
    assert not missing, f'essay no longer matches results/audit.json: {missing}'
    print('essay matches', len(want), 'audit sentences')


def main():
    S, D, I = load('r31_structure_traj.jsonl'), load('r31_dynamics.jsonl'), load('r31_integrators.jsonl')
    a = {'rules': rules(S, D), 'dial': dial(S, I, D)}
    (RES / 'audit.json').write_text(json.dumps(a, indent=1) + '\n')
    sw, cl, dl = a['rules']['switch'], a['rules']['clock'], a['dial']
    print(f"switch: {sw['behaving']} of {a['rules']['autonomous']}; {sw['models_with_loop']} with a self-feeding loop; "
          f"{sw['expected_without_by_chance']:.2f} expected without one, P(none) {sw['p_none_by_chance']:.3f}")
    print(f"clock: {cl['behaving']}; {cl['models_with_loop']} with a brake; "
          f"{cl['expected_without_by_chance']:.2f} expected without one, P(none) {cl['p_none_by_chance']:.2e}")
    print('dial:', 'strict', dl['strict']['filled'], {c: v['filled'] for c, v in dl['sweep'].items()},
          '| new at zero', dl['new_cells_at_zero'], 'on', dl['models_at_zero'], 'models,', dl['voltage_models'], 'voltages')
    if '--check' in sys.argv:
        check(a)


if __name__ == '__main__':
    main()
