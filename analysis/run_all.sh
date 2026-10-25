#!/bin/sh
# Rebuild every number in the essay's census, and the essay itself, from the raw SBML.
#   sh analysis/run_all.sh [JOBS]
# Takes about two hours on a 10-core laptop. Outputs go to results/.
set -eu
cd "$(dirname "$0")/.."
JOBS="${1:-8}"
PY="${PY:-.venv/bin/python}"
# one thread per worker: parallel jobs, not parallel BLAS threads (avoids oversubscribing the CPU)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1
sh analysis/get_biomodels.sh
mkdir -p results
$PY analysis/loops.py --all data/r31_curated --out results/r31_structure_traj.jsonl --jobs "$JOBS" --timeout 1200 --signs trajectory
$PY analysis/loops.py --all data/r31_curated --out results/r31_structure_random.jsonl --jobs "$JOBS" --timeout 1200 --signs random
$PY -c "import json; print('\n'.join('data/r31_curated/%s.xml' % r['model'] for r in map(json.loads, open('results/r31_structure_traj.jsonl')) if r.get('status') == 'ok'))" > results/list_ok.txt
$PY analysis/dynamics.py --list results/list_ok.txt --out results/r31_dynamics.jsonl --jobs "$JOBS" --timeout 900
$PY analysis/integrators.py --list results/list_ok.txt --out results/r31_integrators.jsonl --jobs "$JOBS"
$PY analysis/tabulate.py results/r31_structure_traj.jsonl results/r31_dynamics.jsonl results/tables_traj.json results/r31_integrators.jsonl > /dev/null
$PY analysis/tabulate.py results/r31_structure_random.jsonl results/r31_dynamics.jsonl results/tables_random.json results/r31_integrators.jsonl > /dev/null
$PY analysis/report_tables.py results/tables_traj.json results/tables_random.json > results/tables.md
$PY analysis/toys.py results/toys.json > /dev/null
$PY analysis/nesting.py > /dev/null
$PY analysis/build_post.py
$PY analysis/circuit_figures.py > /dev/null
$PY analysis/fold_census.py
echo "done: results/tables.md and every-line-is-a-loop.html"
