"""Fast checks that the code still produces the committed results (about two minutes).

    .venv/bin/python -m unittest tests/test_reproduce.py -v

Each test reruns one stage on a small input and compares with results/: the census on six release 31 models, the
tables from the committed census records, the toy models, the essay's model asserts, and the page's facts. The full
rebuild is analysis/run_all.sh; these catch a behaviour change in minutes rather than hours.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
# Quick models covering ticks (3, 12, 16), two states (26), exact return (159, 312). Model 45 is left out for time
# (about 160 s alone); its record no longer depends on load (tests/test_budget.py).
SIX = ["BIOMD0000000003", "BIOMD0000000012", "BIOMD0000000016", "BIOMD0000000026", "BIOMD0000000159", "BIOMD0000000312"]
ENV = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=ROOT, env=ENV, capture_output=True, text=True, check=True)


def records(path: pathlib.Path) -> dict[str, dict]:
    """JSON Lines by model, without the timing field."""
    out = {}
    for line in path.read_text().splitlines():
        r = json.loads(line)
        r.pop("seconds", None)
        out[r["model"]] = r
    return out


class Census(unittest.TestCase):
    """loops.py, dynamics.py and integrators.py on six models give the committed records, field for field."""

    @unittest.skipUnless((ROOT / "data" / "r31_curated").is_dir(), "needs data/r31_curated (analysis/get_biomodels.sh)")
    def test_six_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            models = tmp / "models"
            models.mkdir()
            for m in SIX:
                (models / f"{m}.xml").symlink_to(ROOT / "data" / "r31_curated" / f"{m}.xml")
            listing = tmp / "list.txt"
            listing.write_text("".join(f"{models / m}.xml\n" for m in SIX))
            run(
                "analysis/loops.py",
                "--all",
                str(models),
                "--out",
                str(tmp / "s.jsonl"),
                "--jobs",
                "6",
                "--signs",
                "trajectory",
            )
            run(
                "analysis/dynamics.py",
                "--list",
                str(listing),
                "--out",
                str(tmp / "d.jsonl"),
                "--jobs",
                "6",
            )
            run("analysis/integrators.py", "--list", str(listing), "--out", str(tmp / "i.jsonl"), "--jobs", "6")
            for new, old in (("s", "r31_structure_traj"), ("d", "r31_dynamics"), ("i", "r31_integrators")):
                fresh, kept = records(tmp / f"{new}.jsonl"), records(ROOT / "results" / f"{old}.jsonl")
                for m in SIX:
                    self.assertEqual(fresh[m], kept[m], f"{old}.jsonl, {m}")


class Downstream(unittest.TestCase):
    def test_tables_from_committed_census(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "tables_traj.json"
            r = "results/"
            run(
                "analysis/tabulate.py",
                r + "r31_structure_traj.jsonl",
                r + "r31_dynamics.jsonl",
                str(out),
                r + "r31_integrators.jsonl",
            )
            self.assertEqual(out.read_bytes(), (ROOT / "results" / "tables_traj.json").read_bytes())
            md = run("analysis/report_tables.py", r + "tables_traj.json", r + "tables_random.json").stdout
            self.assertEqual(md, (ROOT / "results" / "tables.md").read_text())

    def test_toys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "toys.json"
            run("analysis/toys.py", str(out))
            self.assertEqual(out.read_bytes(), (ROOT / "results" / "toys.json").read_bytes())

    def test_essay_models(self) -> None:
        run("analysis/circuit_figures.py", "--check")  # asserts the switch, clock, adapter, Sw∫ and Figure 1 models

    def test_page_facts(self) -> None:
        out = subprocess.run(
            [PY, "tools/check_facts.py", "--out", os.devnull], cwd=ROOT, capture_output=True, text=True
        ).stdout
        self.assertIn(" 0 missing", out, out)


if __name__ == "__main__":
    unittest.main()
