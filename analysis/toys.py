"""Rebuild Figure 1's counts from two toy models, with the same code as the census.

Usage: python analysis/toys.py [OUT.json]   (default results/toys.json)
The enzyme is E + S <-> ES -> E + P with mass action; the ring is three genes, each repressing the next.
The controller is Khammash's antithetic motif: z1 made at a constant rate, z2 made in proportion to the
output x, z1 and z2 destroying each other, and z1 making x. Writes the loop counts of each under every loop
definition and the running totals each reading finds, and fails if a figure or sentence would be wrong.
"""
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import loops  # noqa: E402
import integrators  # noqa: E402

HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<sbml xmlns="http://www.sbml.org/sbml/level2/version4" level="2" version="4"><model id="{id}">'
COMP = '<listOfCompartments><compartment id="c" size="1"/></listOfCompartments>'


def species(**x0):
    return '<listOfSpecies>' + ''.join(f'<species id="{s}" compartment="c" initialConcentration="{v}"/>' for s, v in x0.items()) + '</listOfSpecies>'


def params(**p):
    return '<listOfParameters>' + ''.join(f'<parameter id="{k}" value="{v}"/>' for k, v in p.items()) + '</listOfParameters>'


def reaction(rid, reactants, products, law, modifiers=()):
    ref = lambda tag, xs: f'<{tag}>' + ''.join(f'<speciesReference species="{s}"/>' for s in xs) + f'</{tag}>' if xs else ''
    mods = '<listOfModifiers>' + ''.join(f'<modifierSpeciesReference species="{s}"/>' for s in modifiers) + '</listOfModifiers>' if modifiers else ''
    return (f'<reaction id="{rid}" reversible="false">{ref("listOfReactants", reactants)}{ref("listOfProducts", products)}{mods}'
            f'<kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">{law}</math></kineticLaw></reaction>')


def mml(*terms):
    """Product of identifiers as MathML."""
    return '<apply><times/>' + ''.join(f'<ci>{t}</ci>' for t in terms) + '</apply>'


def hill_repression(a, rep, n):
    return (f'<apply><divide/><ci>{a}</ci><apply><plus/><cn>1</cn><apply><power/><ci>{rep}</ci><ci>{n}</ci></apply></apply></apply>')


def enzyme():
    rx = [reaction('bind', ['E', 'S'], ['ES'], mml('c', 'k1', 'E', 'S')),
          reaction('unbind', ['ES'], ['E', 'S'], mml('c', 'k2', 'ES')),
          reaction('release', ['ES'], ['E', 'P'], mml('c', 'k3', 'ES'))]
    return (HEAD.format(id='enzyme') + COMP + species(E=1, S=10, ES=0, P=0) + params(k1=1, k2=0.5, k3=0.3)
            + '<listOfReactions>' + ''.join(rx) + '</listOfReactions></model></sbml>')


def ring():
    rx = []
    for g, rep in (('A', 'C'), ('B', 'A'), ('C', 'B')):
        rx.append(reaction(f'make{g}', [], [g], f'<apply><times/><ci>c</ci>{hill_repression("a", rep, "n")}</apply>', [rep]))
        rx.append(reaction(f'decay{g}', [g], [], mml('c', 'd', g)))
    return (HEAD.format(id='ring') + COMP + species(A=1, B=2, C=3) + params(a=10, n=3, d=1)
            + '<listOfReactions>' + ''.join(rx) + '</listOfReactions></model></sbml>')


def controller():
    rx = [reaction('makeZ1', [], ['z1'], '<apply><times/><ci>c</ci><ci>mu</ci></apply>'),
          reaction('makeZ2', [], ['z2'], mml('c', 'theta', 'x'), ['x']),
          reaction('annihilate', ['z1', 'z2'], [], mml('c', 'eta', 'z1', 'z2')),
          reaction('makeX', [], ['x'], mml('c', 'k', 'z1'), ['z1']),
          reaction('decayX', ['x'], [], mml('c', 'gamma', 'x'))]
    return (HEAD.format(id='controller') + COMP + species(x=0.5, z1=1, z2=0.2) + params(mu=1, theta=1, eta=10, k=1, gamma=1)
            + '<listOfReactions>' + ''.join(rx) + '</listOfReactions></model></sbml>')


def main(out):
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, sbml in (('enzyme', enzyme()), ('ring', ring()), ('controller', controller())):
            p = pathlib.Path(tmp) / f'{name}.xml'
            p.write_text(sbml)
            r = loops.analyze(str(p))
            assert r.get('status') == 'ok', r
            res[name] = {d: {k: r['defs'][d][k] for k in ('complete', 'c', 'k', 'j')} for d in r['defs']}
            q = integrators.measure(str(p))
            res[name]['running_totals'] = {'strict': r['integrator_nodes'], 'loose': q['near_integrators'], 'paired': q['pair_integrators'],
                                           'loops': r.get('loop_list')}
    e, g, z = res['enzyme'], res['ring'], res['controller']
    assert z['running_totals']['paired'] == [['z1', 'z2', 1.0, -1.0]] and z['running_totals']['strict'] == 0, z  # z1 - z2 integrates
    assert z['ref24_rank']['c'] == 1 and z['ref24_rank']['k'] == 1, z                                            # one braking loop
    assert not e['running_totals']['paired'] and not g['running_totals']['paired'], (e, g)
    assert e['thomas']['c'] == 5 and e['thomas']['k'] == 2 and e['ref24_rank']['c'] == 0, e   # Figure 1: 5 loops, none left
    assert g['thomas'] == g['ref24_rank'] and g['ref24_rank']['c'] == 1 and g['ref24_rank']['k'] == 1, g  # 1 braking loop
    json.dump(res, open(out, 'w'), indent=1)
    print(json.dumps(res))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parent.parent / 'results' / 'toys.json'))
