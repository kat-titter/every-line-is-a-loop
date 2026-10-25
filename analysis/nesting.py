"""Is nesting order the loop table's missing factor of two? Three tests, one script.

The essay's table has (nu + 1)^2 elements in the row of nu loops: 4, 9, 16, the numbers of orbitals in an atom's
second, third and fourth shells. Chemistry's shells hold twice that, 2 n^2, because each orbital takes two electrons
of opposite spin. The essay guessed that the loop table's missing binary is the order in which loops nest, which loop
is the faster, inner one.

1. Count.  Spin doubles every row, the first included. List what nesting order adds, row by row, and compare with
           2 (nu + 1)^2 = 8, 18, 32.
2. Toy.    A three-gene circuit with one amplifying loop and one brake through the same output gene. Draw rates at
           random, run every draw twice, once with the amplifying loop fast and the brake slow and once the other way
           round, and record what each run does. If order matters, the two halves behave differently.
3. Census. The 42 curated BioModels models whose two loops are one amplifying and one braking. Measure each loop's
           speed in the model's own equations and ask whether the models that keep time are the ones whose
           amplifying loop is the faster.

A loop's speed is the geometric mean of the strengths of its arrows, |dx_b/dt / dx_a| for each arrow a -> b, read
from the model's Jacobian at the census's own five moments of its run (t = 0, 1, 10, 100, 1000). Around a closed loop
the units of the concentrations cancel, so the result is a rate per unit time and two loops of one model can be
compared directly.

Usage: .venv/bin/python analysis/nesting.py          writes results/nesting.json and prints a summary
"""
import itertools
import json
import math
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
OUT = ROOT / 'results' / 'nesting.json'
SEED = 7


# ---------------------------------------------------------------- 1. count
def count_test():
    """Configurations per row under each reading of 'nesting order', against chemistry's 2 n^2."""
    rows = []
    for nu in (0, 1, 2, 3):
        table = (nu + 1) ** 2
        # a loop's type: amplifies or brakes, with or without a running total
        types = [(s, i) for s in '+-' for i in (0, 1)]
        multisets = math.comb(nu + 3, 3) if nu else 1                 # loops unordered, each with its own type
        ordered = 4 ** nu if nu else 1                                # loops ordered fastest to slowest
        # the table's own elements, each split in two by which loop is fastest, where the loops differ in sign
        split = 0
        for k in range(nu + 1):
            for j in range(nu + 1):
                split += 2 if 0 < k < nu else 1
        rows.append({'loops': nu, 'table': table, 'chemistry_2n2': 2 * table, 'nesting_binary_where_defined': split,
                     'types_unordered': multisets, 'types_ordered': ordered})
    # the binary reading cannot touch a row whose elements have fewer than two loops
    assert rows[0]['nesting_binary_where_defined'] == 1 and rows[1]['nesting_binary_where_defined'] == 4
    return rows


# ---------------------------------------------------------------- 2. toy
TOY = {'draws': 800, 'tx': 0.05, 'fast': 0.5, 'slow': 10.0, 'T': 600.0, 'dt': 0.002, 'every': 100}


def toy_test(draws=TOY['draws'], seed=SEED):
    """x is made at a rate that p raises and n lowers; p and n follow x. x -> p -> x amplifies; x -> n -| x brakes.
    'amplify fast' sets p quick and n slow; 'brake fast' swaps the two time constants and nothing else. Each draw runs
    from three starts for 600 time units (60 times the slow loop's time constant). A run keeps time when, over its last
    third, x swings by more than 5% of its mean, peaks at least three times, and holds its amplitude (the last sixth's
    swing is at least 0.8 of the sixth before); a short run once counted slow transients as clocks."""
    rng = np.random.default_rng(seed)
    b0 = rng.uniform(0.01, 0.2, draws)
    b1 = np.exp(rng.uniform(np.log(1.0), np.log(10.0), draws))
    K1 = np.exp(rng.uniform(np.log(0.1), np.log(5.0), draws))
    K2 = np.exp(rng.uniform(np.log(0.1), np.log(5.0), draws))
    h1 = rng.uniform(2.0, 4.0, draws)
    h2 = rng.uniform(2.0, 4.0, draws)
    starts = (0.01, 0.5, 5.0)

    def run(tp, tn):
        P = np.repeat(np.arange(draws), len(starts))
        x = np.tile(np.array(starts), draws)
        p, n = x.copy(), x.copy()
        rec = []
        for i in range(int(TOY['T'] / TOY['dt'])):
            a = p ** h1[P] / (K1[P] ** h1[P] + p ** h1[P])
            r = 1.0 / (1.0 + (n / K2[P]) ** h2[P])
            dx = ((b0[P] + b1[P] * a) * r - x) / TOY['tx']
            x, p, n = x + TOY['dt'] * dx, p + TOY['dt'] * (x - p) / tp, n + TOY['dt'] * (x - n) / tn
            if i % TOY['every'] == 0:
                rec.append(x.copy())
        rec = np.array(rec)
        L = len(rec)
        tail = rec[L * 2 // 3:]
        sw, m = tail.max(0) - tail.min(0), np.abs(tail.mean(0))
        a, b = rec[L * 2 // 3:L * 5 // 6], rec[L * 5 // 6:]
        held = (b.max(0) - b.min(0)) / np.maximum(a.max(0) - a.min(0), 1e-12)
        d1 = np.diff(tail, axis=0)
        peaks = ((d1[:-1] > 0) & (d1[1:] <= 0) & (tail[1:-1] > tail.min(0) + 0.5 * sw)).sum(0)
        ticks = (sw > 0.05 * (m + 0.01)) & (held > 0.8) & (peaks >= 3)
        out = []
        for d in range(draws):
            sl = slice(d * len(starts), (d + 1) * len(starts))
            if ticks[sl].any():
                out.append('keeps time')
            else:
                ends = np.sort(rec[-1, sl])
                out.append('holds two states' if ends[-1] - ends[0] > 0.05 * (ends[-1] + 0.01) else 'settles')
        return out
    amp_fast = run(TOY['fast'], TOY['slow'])
    brake_fast = run(TOY['slow'], TOY['fast'])
    tally = lambda xs: {k: xs.count(k) for k in ('keeps time', 'holds two states', 'settles')}
    pairs = {}
    for a, b in zip(amp_fast, brake_fast):
        pairs[f'{a} | {b}'] = pairs.get(f'{a} | {b}', 0) + 1
    return {'settings': TOY, 'seed': seed, 'amplify fast': tally(amp_fast), 'brake fast': tally(brake_fast), 'pairs': pairs}


# ---------------------------------------------------------------- 3. census
def loop_speed(J, idx, loop, Jpos=None, Jneg=None):
    """Geometric mean of |J[b, a]| over the loop's arrows a -> b, in the stored direction of travel. A one-arrow loop
    (a molecule acting on its own rate) counts only the part with the loop's sign, since the diagonal of the Jacobian
    also carries the molecule's own decay."""
    nd = loop['nodes']
    vals = []
    for i in range(len(nd)):
        a, b = idx.get(nd[i]), idx.get(nd[(i + 1) % len(nd)])
        if a is None or b is None:
            return None
        if len(nd) == 1 and Jpos is not None:
            v = abs((Jpos if loop['sign'] == '+' else Jneg)[b, a])
        else:
            v = abs(J[b, a])
        if not np.isfinite(v) or v == 0:
            return None
        vals.append(math.log(v))
    return math.exp(sum(vals) / len(vals))


def loop_transit(Jneg, idx, loop, shared=frozenset()):
    """How long a signal takes to get round the loop's own molecules, those it does not share with the other loop:
    the sum of each one's relaxation time, 1 / its decay and consumption rate (the negative part of its own diagonal
    entry). Shared molecules add the same time to both loops, so they are left out. A molecule with no decay of its own
    (a running total) takes for ever. This is the quantity the toy varies."""
    t = 0.0
    for nd in loop['nodes']:
        if nd in shared:
            continue
        i = idx.get(nd)
        if i is None:
            return None
        r = abs(Jneg[i, i])
        if not np.isfinite(r):
            return None
        t += 1.0 / r if r > 0 else math.inf
    return t


def census_test():
    import loops as L
    struct = [json.loads(l) for l in open(ROOT / 'results' / 'r31_structure_traj.jsonl')]
    dyn = {}
    for l in open(ROOT / 'results' / 'r31_dynamics.jsonl'):
        d = json.loads(l)
        dyn[d['model']] = d
    mixed = [d for d in struct if d.get('status') == 'ok' and d.get('loops') == 2 and d.get('loop_list')
             and sorted(l['sign'] for l in d['loop_list']) == ['+', '-']]
    rows = []
    for d in mixed:
        y = dyn.get(d['model'], {})
        row = {'model': d['model'], 'name': d['name'], 'forced': bool(y.get('forced')),
               'behaviours': y.get('behaviours') or [], 'keeps_time': 'oscillating' in (y.get('behaviours') or []),
               'loops': [{'sign': l['sign'], 'integrates': l['integrates'], 'length': len(l['nodes'])} for l in d['loop_list']]}
        try:
            rr, flags = L.load(ROOT / 'data' / 'r31_curated' / f"{d['model']}.xml")
            nodes, kinds, rule_syms = L.state_nodes(rr, flags)
            try:
                S = rr.getFullStoichiometryMatrix()
                rids_S, srows = list(S.colnames), {s: i for i, s in enumerate(S.rownames)}
            except Exception:     # a model written as rate rules has no reactions; its rows come from the rules
                S, rids_S, srows = None, [], {}
            rids, rsign, gsign, jac = L.derivative_signs(rr, nodes, kinds, rule_syms)
            N = np.zeros((len(nodes), len(rids)))
            for c, r in enumerate(rids):
                if r in rids_S:
                    for k, s in enumerate(nodes):
                        if s in srows:
                            N[k, c] = S[srows[s], rids_S.index(r)]
            rr.resetToOrigin()
            vol = np.ones(len(nodes))
            for k, s in enumerate(nodes):
                if kinds.get(s) == 'species':
                    try:
                        c_ = rr.getValue('[' + s + ']')
                        if c_ > 0:
                            vol[k] = rr.getValue(s) / c_
                    except Exception:
                        pass
            idx = {s: i for i, s in enumerate(nodes)}
            speeds = {'+': [], '-': []}
            transits = {'+': [], '-': []}
            for dv, dg, x in jac:
                contrib = N[:, :, None] * dv[None, :, :] if dv.size else np.zeros((len(nodes), 0, len(nodes)))
                Jpos = np.clip(contrib, 0, None).sum(1) / vol[:, None]
                Jneg = np.clip(contrib, None, 0).sum(1) / vol[:, None]
                J = Jpos + Jneg
                for q, y_ in enumerate(rule_syms):
                    if y_ in idx and dg.shape[0] > q:
                        J[idx[y_]] = dg[q]
                        Jpos[idx[y_]] = np.clip(dg[q], 0, None)
                        Jneg[idx[y_]] = np.clip(dg[q], None, 0)
                got = {l['sign']: loop_speed(J, idx, l, Jpos, Jneg) for l in d['loop_list']}
                if got['+'] and got['-']:
                    speeds['+'].append(got['+'])
                    speeds['-'].append(got['-'])
                shared = set(d['loop_list'][0]['nodes']) & set(d['loop_list'][1]['nodes'])
                tr = {l['sign']: loop_transit(Jneg, idx, l, shared) for l in d['loop_list']}
                if tr['+'] is not None and tr['-'] is not None:
                    transits['+'].append(tr['+'])
                    transits['-'].append(tr['-'])
            if speeds['+']:
                ratio = float(np.median(np.log10(np.array(speeds['+']) / np.array(speeds['-']))))
                row.update(states=len(speeds['+']), log10_amplify_over_brake=round(ratio, 3),
                           faster='amplifying' if ratio > 0 else 'braking')
            else:
                row['faster'] = None
            if transits['+']:
                # per moment: +1 if the amplifying loop's own molecules are quicker, -1 if the brake's are, 0 if tied
                votes = [(1 if tp < tn else -1 if tn < tp else 0) for tp, tn in zip(transits['+'], transits['-'])]
                v = sum(votes)
                row.update(transit_votes=votes, faster_transit='amplifying' if v > 0 else 'braking' if v < 0 else 'tie')
            else:
                row['faster_transit'] = None
        except Exception as e:
            row['faster'] = None
            row['error'] = str(e)[:120]
        rows.append(row)
    from scipy.stats import fisher_exact

    def tabulate(key):
        usable = [r for r in rows if r.get(key) and not r['forced'] and r['behaviours']]
        table = {f: {'keeps time': sum(1 for r in usable if r[key] == f and r['keeps_time']),
                     'does not': sum(1 for r in usable if r[key] == f and not r['keeps_time'])}
                 for f in ('amplifying', 'braking')}
        a, b = table['amplifying']['keeps time'], table['amplifying']['does not']
        c, d_ = table['braking']['keeps time'], table['braking']['does not']
        odds, p = fisher_exact([[a, b], [c, d_]], alternative='greater')
        return {'usable': len(usable), 'table': table, 'fisher_one_sided_p': round(float(p), 4),
                'odds_ratio': (round(float(odds), 2) if np.isfinite(odds) else 'inf')}
    ties = sum(1 for r in rows if r.get('faster_transit') == 'tie' and not r['forced'] and r['behaviours'])
    return {'mixed_two_loop_models': len(mixed), 'arrow_strength': tabulate('faster'),
            'transit_time': dict(tabulate('faster_transit'), ties_left_out=ties), 'models': rows}


def main():
    res = {'count': count_test()}
    print('count')
    for r in res['count']:
        print('  ', r)
    res['toy'] = toy_test()
    print('toy', json.dumps({k: res['toy'][k] for k in ('amplify fast', 'brake fast')}))
    print('   pairs (amplify fast | brake fast):', res['toy']['pairs'])
    res['census'] = census_test()
    c = res['census']
    print('census: mixed', c['mixed_two_loop_models'])
    for k in ('arrow_strength', 'transit_time'):
        print('  ', k, c[k])
    OUT.write_text(json.dumps(res, indent=1))
    print('wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
