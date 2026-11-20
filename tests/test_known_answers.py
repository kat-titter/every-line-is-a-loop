"""Known answers through the census's own code paths (under a minute).

    .venv/bin/python -m unittest tests/test_known_answers.py -v

Five circuits whose answer is known from theory or from the paper that built them, each run through the same
functions the census runs (loops.analyze, dynamics.classify, integrators.measure, tabulate.main, truth_tests.one_gain,
fingerprints.protocol_check), so a change that breaks sign reading, the filters, the running-total readings, the
behaviour labels or the gain test fails here in seconds rather than as a moved number after a two-hour rebuild.

  toggle        two genes repressing each other: one self-feeding loop (1 loop, 0 brakes), two resting states
  repressilator BIOMD0000000012 (Elowitz 2000): one loop through six molecules with three braking arrows; ticks
  gain ring     three genes in a braking ring with equal decay, gain set 5% above and 5% below sec(pi/3)^3 = 8;
                for this ring the secant floor is exact (eigenvalues -1 + g e^(i pi/3), g^3 = G), so the ring ticks
                just above it and settles just below it
  antithetic    Khammash's controller (toys.controller): one braking loop, no strict running total, the pair
                z1 - z2 as a paired running total, filed by tabulate.py at (1 loop, 1 brake, 1 total) when paired
  adapter       BIOMD0000000312 (Tyson 2003 sniffer): no loop, and under its own input step it returns exactly

The two BioModels cases skip when data/r31_curated is absent (analysis/get_biomodels.sh fetches it).
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import dynamics  # noqa: E402
import fingerprints  # noqa: E402
import integrators  # noqa: E402
import loops  # noqa: E402
import tabulate  # noqa: E402
import toys  # noqa: E402
import truth_tests  # noqa: E402

R31 = ROOT / 'data' / 'r31_curated'
HAVE_R31 = R31.is_dir()


def sbml(mid: str, x0: dict, p: dict, reactions: list[str]) -> str:
    """A level 2 SBML model in one compartment of size 1, built with toys.py's helpers."""
    return (
        toys.HEAD.format(id=mid)
        + toys.COMP
        + toys.species(**x0)
        + toys.params(**p)
        + '<listOfReactions>'
        + ''.join(reactions)
        + '</listOfReactions></model></sbml>'
    )


def repressed(rate: str, repressor: str, hill: str) -> str:
    return f'<apply><times/><ci>c</ci>{toys.hill_repression(rate, repressor, hill)}</apply>'


def toggle() -> str:
    """Gardner's toggle reduced to two genes: U made at a1 / (1 + V^n), V at a2 / (1 + U^n), both decay."""
    rx = [
        toys.reaction('makeU', [], ['U'], repressed('a1', 'V', 'n'), ['V']),
        toys.reaction('decayU', ['U'], [], toys.mml('c', 'd', 'U')),
        toys.reaction('makeV', [], ['V'], repressed('a2', 'U', 'n'), ['U']),
        toys.reaction('decayV', ['V'], [], toys.mml('c', 'd', 'V')),
    ]
    return sbml('toggle', {'U': 2, 'V': 0.5}, {'a1': 10, 'a2': 8, 'n': 3, 'd': 1}, rx)


def ring_rate_for_gain(G: float, h: float = 4.0) -> float:
    """Production rate a of the ring x' = a / (1 + y^h) - x whose symmetric steady state has loop gain G.
    At the steady state a = x (1 + x^h), and each arrow's strength is g = h x^h / (1 + x^h), so G = g^3."""
    s = G ** (1 / 3) / h
    x = (s / (1 - s)) ** (1 / h)
    return x * (1 + x**h)


def braking_ring(a: float) -> str:
    rx = []
    for g, rep in (('A', 'C'), ('B', 'A'), ('C', 'B')):
        rx.append(toys.reaction(f'make{g}', [], [g], repressed('a', rep, 'h'), [rep]))
        rx.append(toys.reaction(f'decay{g}', [g], [], toys.mml('c', 'd', g)))
    return sbml('ring', {'A': 1.1, 'B': 0.9, 'C': 1.0}, {'a': a, 'h': 4, 'd': 1}, rx)


def loop_arc_signs(path: pathlib.Path, loop_nodes: list[str]) -> list[int]:
    """Signs of the census's arrows along one listed loop, read the way loops.analyze reads them."""
    rr, flags = loops.load(path)
    nodes, kinds, rule_syms = loops.state_nodes(rr, flags)
    S = rr.getFullStoichiometryMatrix()
    rows, cols = {s: i for i, s in enumerate(S.rownames)}, list(S.colnames)
    rids, rsign, gsign, _ = loops.derivative_signs(rr, nodes, kinds, rule_syms)
    N = np.zeros((len(nodes), len(rids)))
    for k, s in enumerate(nodes):
        if s in rows:
            for c, r in enumerate(rids):
                N[k, c] = S[rows[s], cols.index(r)]
    arcs = loops.influence_arcs(nodes, rids, N, rsign, rule_syms, gsign)
    idx = {s: i for i, s in enumerate(nodes)}
    signs = []
    for a, b in zip(loop_nodes, loop_nodes[1:] + loop_nodes[:1]):
        on = {s for (i, k, _, s) in arcs if i == idx[a] and k == idx[b]}
        assert len(on) == 1, (a, b, on)
        signs.append(on.pop())
    return signs


class KnownAnswers(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory
    dir: pathlib.Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = pathlib.Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def write(self, name: str, text: str) -> pathlib.Path:
        p = self.dir / f'{name}.xml'
        p.write_text(text)
        return p

    # ------------------------------------------------------------ 1. toggle: one self-feeding loop, two states
    def test_toggle_one_self_feeding_loop_two_states(self) -> None:
        p = self.write('toggle', toggle())
        r = loops.analyze(str(p))
        self.assertEqual(r['status'], 'ok', r)
        m = r['defs']['ref24_rank']
        self.assertEqual((m['complete'], m['c'], m['k'], m['j']), (True, 1, 0, 0), m)
        self.assertEqual([lp['sign'] for lp in r['loop_list']], ['+'])
        self.assertTrue(r['plain_positive'] and r['refined_positive'], r)
        self.assertEqual(loop_arc_signs(p, r['loop_list'][0]['nodes']), [-1, -1])  # two repressions make one + loop
        d = dynamics.classify(str(p))
        self.assertEqual(d['status'], 'ok', d)
        self.assertFalse(d['forced'])
        self.assertIn('multistable', d['behaviours'], d)
        self.assertEqual(d['fixed_points'], 2, d)
        self.assertNotIn('oscillating', d['behaviours'])

    # ------------------------------------------------------------ 2. repressilator: one loop, three brakes, ticks
    @unittest.skipUnless(HAVE_R31, 'needs data/r31_curated (analysis/get_biomodels.sh)')
    def test_repressilator_one_loop_three_brakes_ticks(self) -> None:
        p = R31 / 'BIOMD0000000012.xml'
        r = loops.analyze(str(p))
        self.assertEqual(r['status'], 'ok', r)
        for d in ('thomas', 'ref24', 'ref24_rank'):
            m = r['defs'][d]
            self.assertEqual((m['complete'], m['c'], m['k'], m['j']), (True, 1, 1, 0), (d, m))
        (loop,) = r['loop_list']
        self.assertEqual((len(loop['nodes']), loop['sign'], loop['integrates']), (6, '-', False), loop)
        signs = loop_arc_signs(p, loop['nodes'])
        self.assertEqual(sorted(signs), [-1, -1, -1, 1, 1, 1], signs)  # each protein brakes the next gene
        d = dynamics.classify(str(p))
        self.assertEqual(d['status'], 'ok', d)
        self.assertEqual(d['behaviours'], ['oscillating'], d)
        self.assertEqual(d['runs'], ['oscillating'] * dynamics.STARTS, d)

    # ------------------------------------------------------------ 3. braking ring around the secant floor
    def test_braking_ring_ticks_only_above_secant_floor(self) -> None:
        floor = truth_tests.secant(3)
        self.assertAlmostEqual(floor, 8.0, places=9)
        keep = truth_tests.DATA
        try:
            truth_tests.DATA = self.dir  # one_gain reads DATA / f'{mid}.xml', as trace_four.py does
            for factor in (1.05, 0.95):
                with self.subTest(gain=f'{factor} x floor'):
                    target = 8.0 * factor
                    mid = f'ring_{factor}'
                    p = self.write(mid, braking_ring(ring_rate_for_gain(target)))
                    r = loops.analyze(str(p))
                    m = r['defs']['ref24_rank']
                    self.assertEqual((m['c'], m['k'], m['j']), (1, 1, 0), m)
                    g = truth_tests.one_gain(mid, r['loop_list'][0])
                    self.assertEqual(g['status'], 'ok', g)
                    self.assertEqual(g['n'], 3)
                    self.assertAlmostEqual(g['G'] / target, 1.0, delta=1e-3, msg=g)
                    above = g['G'] > g['threshold']
                    self.assertEqual(above, factor > 1, g)
                    self.assertEqual(g['unstable'], above, g)  # the floor is exact for this ring
                    d = dynamics.classify(str(p))
                    self.assertEqual('oscillating' in d['behaviours'], above, d)
                    if not above:
                        # a braking ring below its floor rings, then settles
                        self.assertIn('damped', d['behaviours'], d)
        finally:
            truth_tests.DATA = keep

    # ------------------------------------------------------------ 4. antithetic controller: a paired running total
    def test_antithetic_controller_paired_running_total(self) -> None:
        p = self.write('controller', toys.controller())
        s = loops.analyze(str(p))
        m = s['defs']['ref24_rank']
        # the z1-z2 annihilation pair is filtered
        self.assertEqual((m['complete'], m['c'], m['k'], m['j']), (True, 1, 1, 0), m)
        self.assertEqual(s['integrator_nodes'], 0, s)  # no strict running total
        self.assertEqual(set(s['loop_list'][0]['nodes']), {'x', 'z1', 'z2'})
        q = integrators.measure(str(p))
        self.assertEqual(q['pair_integrators'], [['z1', 'z2', 1, -1]], q)  # z1 - z2 integrates the error
        self.assertEqual(q['pair_unchecked'], 0, q)
        d = dynamics.classify(str(p))
        self.assertEqual(d['fixed_points'], 1, d)  # one set point from every start (integral control may overshoot it)
        self.assertIn('steady', d['behaviours'], d)
        self.assertFalse({'multistable', 'oscillating', 'unbounded'} & set(d['behaviours']), d)
        # tabulate.py files it at (1 brake, 0 totals) on the strict reading and (1 brake, 1 total) on the paired one
        files = {}
        for key, rec in (('s', s), ('d', d), ('i', q)):
            files[key] = self.dir / f'controller_{key}.jsonl'
            files[key].write_text(json.dumps(rec) + '\n')
        out = self.dir / 'controller_tables.json'
        with contextlib.redirect_stdout(io.StringIO()):
            tabulate.main(str(files['s']), str(files['d']), str(out), str(files['i']))
        row = json.loads(out.read_text())['defs']['ref24_rank']['rows']['1']
        self.assertEqual(row['essay']['cells'], {'(1, 0)': 1}, row['essay'])
        self.assertEqual(row['essay_pair']['cells'], {'(1, 1)': 1}, row['essay_pair'])
        self.assertEqual(row['essay_pair']['models with a loop through a paired total'], ['controller'])

    # ------------------------------------------------------------ 5. Tyson's adapter: no loop, returns exactly
    @unittest.skipUnless(HAVE_R31, 'needs data/r31_curated (analysis/get_biomodels.sh)')
    def test_tyson_adapter_no_loop_returns_exactly(self) -> None:
        p = R31 / 'BIOMD0000000312.xml'
        r = loops.analyze(str(p))
        self.assertEqual(r['status'], 'ok', r)
        for d in ('thomas', 'ref24', 'ref24_rank'):
            m = r['defs'][d]
            self.assertEqual((m['complete'], m['c']), (True, 0), (d, m))
        self.assertTrue(dynamics.forced(p))  # its signal is a step in time: set aside by the census as driven
        mid, out, t_pre, t_end, set_values, _ = fingerprints.CHECKS[0]
        self.assertEqual(mid, 'BIOMD0000000312')
        c = fingerprints.protocol_check(mid, out, t_pre, t_end, set_values)
        self.assertIsNone(c['solver_stopped_at'], c)
        self.assertGreater(c['peak'], fingerprints.MOVE, c)  # it answers the step
        self.assertLess(c['final'], 1e-3, c)  # and comes back: exact within the integrator's tolerance
        self.assertEqual(c['row'], 'returns exactly', c)


if __name__ == '__main__':
    unittest.main()
