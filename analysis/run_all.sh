#!/bin/sh
# Rebuild every number in the essay from the raw downloads, then check the page against them.
#   caffeinate -i sh analysis/run_all.sh [JOBS]        (caffeinate keeps a Mac awake; drop it elsewhere)
# Stages: 1 data (BioModels release 31 and the hold-out, checksums verified), 2 the release 31 census, 3 tables, toys
# and the speed-order test, 4 the tests of the laws, their audit and the atlas, 5 the hold-out census and its score,
# 6 the essay's generated blocks, 7 the fact check, 8 the data audit and the read budgets. Outputs go to results/ and
# every-line-is-a-loop.html; run times are in README.md.
set -eu
cd "$(dirname "$0")/.."
JOBS="${1:-8}"
PY="${PY:-.venv/bin/python}"
# one thread per worker: parallel jobs, not parallel BLAS threads (avoids oversubscribing the CPU)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1
stamp() { echo "== $(date '+%H:%M:%S') $*"; }
mkdir -p results

stamp "1 data"
sh analysis/get_biomodels.sh
$PY analysis/get_holdout.py --download  # the list is results/holdout_ids.json (read 2026-11-16); --relist would redo it
$PY - <<'EOF'
import hashlib, json, pathlib, subprocess
# the committed manifest: get_holdout.py --download has just rewritten the working copy from the files it fetched
manifest = json.loads(subprocess.run(["git", "show", "HEAD:results/holdout_manifest.json"], capture_output=True, text=True, check=True).stdout)
files = {m: e for m, e in manifest.items() if "sha256" in e}
bad = [m for m, e in files.items() if hashlib.sha256(pathlib.Path(f"data/holdout_curated/{m}.xml").read_bytes()).hexdigest() != e["sha256"]]
print(f"hold-out files: {len(files)} with a checksum, {len(bad)} differ from the committed results/holdout_manifest.json", bad[:5])
assert not bad, "BioModels changed a hold-out file since 2026-11-16; the hold-out numbers may move"
EOF

stamp "2 census of release 31"
$PY analysis/loops.py --all data/r31_curated --out results/r31_structure_traj.jsonl --jobs "$JOBS" --signs trajectory
$PY analysis/loops.py --all data/r31_curated --out results/r31_structure_random.jsonl --jobs "$JOBS" --signs random
$PY -c "import json; print('\n'.join('data/r31_curated/%s.xml' % r['model'] for r in map(json.loads, open('results/r31_structure_traj.jsonl')) if r.get('status') == 'ok'))" > results/list_ok.txt
$PY analysis/dynamics.py --list results/list_ok.txt --out results/r31_dynamics.jsonl --jobs "$JOBS"
$PY analysis/integrators.py --list results/list_ok.txt --out results/r31_integrators.jsonl --jobs "$JOBS"

stamp "3 tables, toys, speed order"
$PY analysis/tabulate.py results/r31_structure_traj.jsonl results/r31_dynamics.jsonl results/tables_traj.json results/r31_integrators.jsonl > /dev/null
$PY analysis/tabulate.py results/r31_structure_random.jsonl results/r31_dynamics.jsonl results/tables_random.json results/r31_integrators.jsonl > /dev/null
$PY analysis/report_tables.py results/tables_traj.json results/tables_random.json > results/tables.md
$PY analysis/toys.py results/toys.json > /dev/null
$PY analysis/nesting.py > /dev/null

stamp "4 tests of the laws, the atlas, the address test, the four traced"
$PY analysis/truth_tests.py > /dev/null
$PY analysis/audit.py --check
$PY analysis/robust_return.py > /dev/null
$PY analysis/fingerprints.py > /dev/null
$PY analysis/address_predicts.py > /dev/null
$PY analysis/trace_four.py > /dev/null

stamp "5 hold-out census (435 models curated since release 31)"
sh analysis/run_holdout.sh "$JOBS"
$PY analysis/holdout_score.py > /dev/null
$PY analysis/holdout_handcheck.py > /dev/null

stamp "6 the essay's generated blocks"
$PY analysis/build_post.py > /dev/null
$PY analysis/circuit_figures.py > /dev/null
$PY analysis/fold_census.py

stamp "7 fact check"
$PY tools/check_facts.py

stamp "8 data audit and read budgets"
$PY analysis/data_audit.py --jobs "$JOBS" > /dev/null
$PY analysis/read_budgets.py
stamp "done: results/ and every-line-is-a-loop.html; git status shows what moved"
