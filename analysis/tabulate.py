"""Tabulate the counting experiment from the census (loops.py) and the dynamics (dynamics.py).

Usage: python analysis/tabulate.py STRUCT.jsonl DYN.jsonl OUT.json [INTEGRATORS.jsonl]

Loop definitions (from loops.py 'defs'):
  thomas     elementary circuits of the signed influence graph (the objects of Thomas's rules)
  ref24      circuits passing reference 24's filters (no reaction class twice, no reverse pair,
             not all species of a conservation law)
  ref24_rank ref24 minus circuits whose reactions have linearly dependent stoichiometry (reference 24's rank condition)
Rows: nu = c, the number of loops under the definition. Occupancy under four counting rules:
  essay   (k, j)                                   predicted (nu+1)^2
  pf      (k_pf, j), k by Sontag's distance on the filtered loops   predicted (nu+1)^2
  types4  multiset of per-loop types (+, +int, -, -int)    C(nu+3, 3)
  types3  multiset of (+, -, -int)                          C(nu+2, 2)
"""
import collections
import json
import math
import sys


def load(p):
    return {d['model']: d for d in (json.loads(l) for l in open(p) if l.strip())}


RULES = {
    'essay': (lambda m: (m['k'], m['j']), lambda n: (n + 1) ** 2),
    'pf': (lambda m: (m['k_pf'], m['j']), lambda n: (n + 1) ** 2),
    'types4': (lambda m: (m['types']['n_pos'], m['types']['n_pos_int'], m['types']['n_neg'], m['types']['n_neg_int']), lambda n: math.comb(n + 3, 3)),
    'types3': (lambda m: (m['types']['n_pos'] + m['types']['n_pos_int'], m['types']['n_neg'], m['types']['n_neg_int']), lambda n: math.comb(n + 2, 2)),
}


# Models where the right answer about running totals is known. expected: True = has one, False = has none.
CONTROLS = {
    'BIOMD0000000429': ('yeast osmoregulation (Schaber 2012)', True),        # Hog1 adapts exactly through integral feedback
    'BIOMD0000000603': ('yeast osmoadaptation (Petelenz-Kurdziel 2013)', True),
    'BIOMD0000000006': ('cell cycle, two variables (Tyson 1991)', True),     # total cyclin is a running total by construction
    'BIOMD0000000312': ('feed-forward adapter, no loop (Tyson 2003)', False),
    'BIOMD0000000200': ('chemotaxis, receptor complex only (Bray 1995)', False),   # no methylation states, cannot adapt
    'BIOMD0000000404': ('chemotaxis, phosphorylation steps only (Bray 1993)', False),
}
# Coarse behaviour classes for the essay's test (count the kinds of behaviour per row).
COARSE = {'multistable': 'switch', 'oscillating': 'clock', 'damped': 'settles', 'steady': 'settles', 'continuum': 'settles', 'unbounded': 'grows'}


def main(struct_p, dyn_p, out_p, integ_p=None):
    S, D = load(struct_p), load(dyn_p)
    INTEG = {k: v for k, v in load(integ_p).items() if v.get('status') == 'ok'} if integ_p else {}
    NEAR = {k: set(v.get('near_integrators') or []) for k, v in INTEG.items()}
    PAIR = {k: set(v.get('pair_nodes') or []) for k, v in INTEG.items()}
    ok = {k: v for k, v in S.items() if v.get('status') == 'ok'}
    T = {'census': dict(collections.Counter(v.get('status') for v in S.values())), 'usable': len(ok)}
    rn = {k: v for k, v in ok.items() if v.get('reactions', 0) > 0}
    def rep(rs):
        n = len(rs)
        c = lambda f: sum(1 for r in rs.values() if f(r))
        return {'models': n, 'no negative circuit': c(lambda r: r['plain_negative'] is False),
                'no positive circuit': c(lambda r: r['plain_positive'] is False),
                'no refined positive circuit': c(lambda r: r['refined_positive'] is False),
                'undecided': c(lambda r: r['plain_positive'] is None or r['refined_positive'] is None)}
    # Baudier, Fages and Soliman 2018, Table 1 (506 sanitized reaction models of BioModels release 31): no negative circuit 70,
    # no positive circuit 48, Cor. 2.3 to 2.5 (the three filters run here) 105. Their headline 160 adds Cor. 2.6, not run here.
    T['replication'] = {'reference 24': {'models': 506, 'no negative circuit': 70, 'no positive circuit': 48, 'no refined positive circuit': 105},
                        'all usable': rep(ok), 'with reactions': rep(rn), 'with reactions, no events': rep({k: v for k, v in rn.items() if not v.get('events')})}
    T['defs'] = {}
    for dname in ('thomas', 'ref24', 'ref24_rank'):
        dist = collections.Counter()
        for r in ok.values():
            m = r['defs'][dname]
            c = m.get('c') if m.get('complete') else None
            dist['over budget' if c is None else str(c) if c <= 3 else '4 to 10' if c <= 10 else 'over 10'] += 1
        Dd = {'distribution': dict(dist), 'rows': {}}
        for nu in (1, 2, 3):
            sel = [(k, r['defs'][dname]) for k, r in ok.items() if r['defs'][dname].get('complete') and r['defs'][dname]['c'] == nu]
            R = {'models': len(sel), 'cactus': sum(1 for _, m in sel if m['cactus'])}
            for rname, (f, pred) in RULES.items():
                usable = [(k, m) for k, m in sel if f(m)[0] is not None]
                occ = collections.Counter(f(m) for _, m in usable)
                occc = collections.Counter(f(m) for _, m in usable if m['cactus'])
                R[rname] = {'predicted': pred(nu), 'occupied': len(occ), 'occupied_cactus': len(occc),
                            'cells': {str(k): v for k, v in sorted(occ.items())}}
            beh = collections.defaultdict(collections.Counter)
            sigs = collections.Counter()
            for k, m in sel:
                d = D.get(k)
                if not d or d.get('status') != 'ok':
                    sig = 'no result'
                elif d.get('forced'):
                    sig = 'forced'
                else:
                    sig = '+'.join(x for x in d['behaviours'] if x != 'steady' or len(d['behaviours']) == 1) or 'unsettled'
                beh[str(RULES['essay'][0](m))][sig] += 1
                sigs[sig] += 1
            R['behaviours'] = dict(sigs)
            R['distinct_autonomous_behaviours'] = len([s for s in sigs if s not in ('no result', 'forced', 'unsettled')])
            coarse = collections.Counter()
            for s_ in sigs:
                if s_ in ('no result', 'forced', 'unsettled'):
                    continue
                cs = {COARSE[b] for b in s_.split('+')}
                if len(cs) > 1:
                    cs.discard('settles')
                coarse['+'.join(sorted(cs))] += sigs[s_]
            R['coarse_behaviours'] = dict(coarse)
            R['k_pf_differs'] = sum(1 for _, m in sel if m['k_pf'] is not None and m['k_pf'] != m['k'])
            R['nu_differs'] = sum(1 for _, m in sel if m.get('nu_core') is not None and m['nu_core'] != m['c'])
            R['behaviour_by_cell'] = {k: dict(v) for k, v in sorted(beh.items())}
            R['models_list'] = sorted(k for k, _ in sel)
            Dd['rows'][nu] = R
        if dname == 'ref24_rank' and NEAR:
            for nu in (1, 2, 3):
                sel = [(k, r) for k, r in ok.items() if r['defs'][dname].get('complete') and r['defs'][dname]['c'] == nu and r.get('loop_list') is not None]
                cells = collections.Counter()
                for k, r in sel:
                    near = NEAR.get(k, set())
                    kk = sum(1 for l in r['loop_list'] if l['sign'] == '-')
                    jj = sum(1 for l in r['loop_list'] if set(l['nodes']) & near)
                    cells[(kk, jj)] += 1
                Dd['rows'][nu]['essay_near'] = {'predicted': (nu + 1) ** 2, 'occupied': len(cells), 'cells': {str(k): v for k, v in sorted(cells.items())}}
                # paired reading: a loop keeps a running total if it passes a strict integrator or either member of a paired total
                cells_p, hits = collections.Counter(), []
                for k, r in sel:
                    pair = PAIR.get(k, set())
                    kk = sum(1 for l in r['loop_list'] if l['sign'] == '-')
                    jj = sum(1 for l in r['loop_list'] if l['integrates'] or set(l['nodes']) & pair)
                    cells_p[(kk, jj)] += 1
                    if any(set(l['nodes']) & pair for l in r['loop_list']):
                        hits.append(k)
                Dd['rows'][nu]['essay_pair'] = {'predicted': (nu + 1) ** 2, 'occupied': len(cells_p), 'cells': {str(k): v for k, v in sorted(cells_p.items())},
                                                'models with a loop through a paired total': hits}
        T['defs'][dname] = Dd
    bad_m, bad_o, n_m, n_o, forced = [], [], 0, 0, 0
    for k, d in D.items():
        r = ok.get(k)
        if not r or d.get('status') != 'ok':
            continue
        if d.get('forced'):
            forced += 1
            continue
        if 'multistable' in d['behaviours']:
            n_m += 1
            if r['refined_positive'] is False:
                bad_m.append(k)
        if 'oscillating' in d['behaviours']:
            n_o += 1
            if r['plain_negative'] is False:
                bad_o.append(k)
    T['theorem_checks'] = {'forced models excluded': forced, 'multistable': n_m, 'multistable without refined positive circuit': bad_m,
                           'oscillating': n_o, 'oscillating without negative circuit': bad_o}
    T['paired_totals'] = {'models with one': sorted(k for k, v in PAIR.items() if v),
                          'small models with a loop through one': sorted(k for nu in (1, 2, 3) for k in T['defs']['ref24_rank']['rows'][nu].get('essay_pair', {}).get('models with a loop through a paired total', []))}
    T['integrators'] = {'models with any integrating loop (ref24_rank, complete)': sum(1 for r in ok.values() if r['defs']['ref24_rank'].get('complete') and r['defs']['ref24_rank']['j'] > 0),
                        'models with complete ref24_rank enumeration': sum(1 for r in ok.values() if r['defs']['ref24_rank'].get('complete'))}
    # The split the theorems support: amplifying loops after the filters, braking loops as drawn.
    split, moved, osc_no_brake = collections.Counter(), 0, []
    small = {k for k, r in ok.items() if r['defs']['ref24_rank'].get('complete') and r['defs']['ref24_rank']['c'] in (1, 2, 3)}
    placed = set()
    for k, r in ok.items():
        a, b = r['defs']['ref24_rank'], r['defs']['thomas']
        if not (a.get('complete') and b.get('complete')):
            continue
        amp = a['types']['n_pos'] + a['types']['n_pos_int']
        brk = b['types']['n_neg'] + b['types']['n_neg_int']
        nu = amp + brk
        if nu not in (1, 2, 3):
            continue
        placed.add(k)
        split[(nu, brk)] += 1
        if k not in small or (a['c'], a['k']) != (nu, brk):
            moved += 1
        d = D.get(k)
        if d and d.get('status') == 'ok' and not d.get('forced') and 'oscillating' in d['behaviours'] and brk == 0:
            osc_no_brake.append(k)
    moved += len(small - placed)
    T['split'] = {'rows': {nu: sum(v for (n, _), v in split.items() if n == nu) for nu in (1, 2, 3)},
                  'patterns': {nu: sum(1 for (n, _) in split if n == nu) for nu in (1, 2, 3)},
                  'moved': moved, 'clocks without a brake': osc_no_brake, 'cells': {str(k): v for k, v in sorted(split.items())}}
    T['controls'] = {}
    for mid, (label, expected) in CONTROLS.items():
        r = S.get(mid, {})
        m = (r.get('defs') or {}).get('ref24_rank', {})
        T['controls'][mid] = {'label': label, 'expected': expected, 'status': r.get('status'), 'loops': m.get('c') if m.get('complete') else ('over ' + str(m.get('c_at_least'))),
                              'strict_integrators_on_loops': r.get('integrator_nodes'), 'near_integrators': sorted(NEAR.get(mid, [])),
                              'pair_integrators': INTEG.get(mid, {}).get('pair_integrators', [])}
    json.dump(T, open(out_p, 'w'), indent=1)
    show = {k: v for k, v in T.items() if k != 'defs'}
    print(json.dumps(show, indent=1))
    for dname, Dd in T['defs'].items():
        print(f"== {dname}: distribution {Dd['distribution']}")
        for nu, R in Dd['rows'].items():
            print(f"   nu={nu}: models {R['models']} (cactus {R['cactus']}) | " + ' | '.join(f"{rn} {R[rn]['occupied']}/{R[rn]['predicted']}" for rn in RULES) + f" | behaviours {R['behaviours']}")


if __name__ == '__main__':
    main(*sys.argv[1:])
