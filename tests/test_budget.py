"""Work budgets (analysis/budget.py) in a few seconds: a model that spends its budget gets the same status, at the same
count of work, every time and on any machine; solver-failure handlers cannot swallow it; the safety net says so loudly.

    .venv/bin/python -m unittest tests/test_budget.py -v

The census caps every model by work, not by the clock, so whether a record is 'ok' or 'budget' cannot depend on the
machine's speed or load. Here dynamics.py's budget is lowered so the Borghans 1997 calcium oscillator (BIOMD0000000045,
the slowest finisher of the committed run) spends it in its first start, and the record is checked field for field.
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import budget  # noqa: E402
import dynamics  # noqa: E402

MODEL = ROOT / 'data' / 'r31_curated' / 'BIOMD0000000045.xml'
LOW = 5e6  # derivative evaluations: its first start spends this within its first three horizons


@unittest.skipUnless(MODEL.exists(), 'needs data/r31_curated (analysis/get_biomodels.sh)')
class Budget(unittest.TestCase):
    def setUp(self) -> None:
        self.keep, dynamics.WORK_BUDGET = dynamics.WORK_BUDGET, LOW
        self.meters: list[budget.Meter] = []
        self.meter = budget.meter

        def spy(rr: object, limit: float) -> budget.Meter:
            m = self.meter(rr, limit)
            self.meters.append(m)
            return m

        budget.meter = spy

    def tearDown(self) -> None:
        dynamics.WORK_BUDGET, budget.meter = self.keep, self.meter

    def test_spent_budget_is_a_deterministic_status(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            first, second = dynamics.record(MODEL), dynamics.record(MODEL)
        want = {'model': 'BIOMD0000000045', 'status': 'budget: solver work past 5e+06 derivative evaluations'}
        self.assertEqual(first, want)
        self.assertEqual(second, want)
        used = [m.used for m in self.meters]
        self.assertEqual(used[0], used[1], 'the work counted up to the stop differs between two runs')
        self.assertGreater(used[0], LOW)

    def test_work_is_cvode_right_hand_side_calls_times_state(self) -> None:
        rr = dynamics.load(MODEL)
        m = self.meter(rr, float('inf'))
        rr.simulate(0, 10, 2001)
        self.assertEqual(budget.work(rr), m.used)
        self.assertEqual(m.used % 4, 0, 'four state variables: work comes in multiples of four')
        self.assertGreater(m.used, 0)


class SafetyNet(unittest.TestCase):
    def test_fires_loudly(self) -> None:
        keep, budget.SAFETY_NET_S = budget.SAFETY_NET_S, 0.2
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                p = budget.run(['sleep', '2'], 'a slow model')
        finally:
            budget.SAFETY_NET_S = keep
        self.assertIsNone(p)
        self.assertIn('SAFETY NET FIRED: a slow model', err.getvalue())


if __name__ == '__main__':
    unittest.main()
