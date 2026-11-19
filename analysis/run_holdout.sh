#!/bin/sh
# The hold-out census: the release 31 pipeline, byte for byte, on the BioModels models curated since release 31.
#   caffeinate -i sh analysis/run_holdout.sh [JOBS]
# No script is edited. The scripts name release 31's folders relative to their own root, so they run from a copy of
# analysis/ inside a scratch root (data/holdout_run/, gitignored) whose data/r31_curated holds the hold-out files.
# First a check that can fail: six release 31 models through the same mechanism must reproduce their published
# records. Outputs are copied to results/holdout_*; nothing under results/ that belongs to release 31 is touched.
# Skipped on purpose: the random-sign structure run, toys, nesting and every step that builds the essay.
set -eu
cd "$(dirname "$0")/.."
REPO="$(pwd)"
JOBS="${1:-8}"
PY="$REPO/.venv/bin/python"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1
stamp() { echo "== $(date '+%H:%M:%S') $*"; }

sandbox() {  # $1 scratch root, $2 folder of model files to census
  rm -rf "$1"; mkdir -p "$1/results" "$1/data/r31_curated"
  cp -R "$REPO/analysis" "$1/analysis"; rm -rf "$1/analysis/__pycache__"
  ln -s "$2" "$1/data/census_only"
  for f in "$2"/*.xml; do ln -s "$f" "$1/data/r31_curated/$(basename "$f")"; done
  # the two models fingerprints.py checks by name (Tyson's adapter, the yeast salt model) are read, never censused
  for m in BIOMD0000000312 BIOMD0000000603; do [ -e "$1/data/r31_curated/$m.xml" ] || ln -s "$REPO/data/r31_curated/$m.xml" "$1/data/r31_curated/$m.xml"; done
}
structure() {  # run from inside a scratch root
  "$PY" analysis/loops.py --all data/census_only --out results/r31_structure_traj.jsonl --jobs "$JOBS" --timeout 1200 --signs trajectory
  "$PY" -c "import json; print('\n'.join('data/r31_curated/%s.xml' % r['model'] for r in map(json.loads, open('results/r31_structure_traj.jsonl')) if r.get('status') == 'ok'))" > results/list_ok.txt
  "$PY" analysis/dynamics.py --list results/list_ok.txt --out results/r31_dynamics.jsonl --jobs "$JOBS" --timeout 900
}

# ---- 0. the check that can fail: release 31 reproduces through this mechanism
stamp "check: six release 31 models"
CHK="$REPO/data/r31_check_run"; SIX="$REPO/data/r31_check_six"
rm -rf "$SIX"; mkdir -p "$SIX"
for m in BIOMD0000000003 BIOMD0000000012 BIOMD0000000016 BIOMD0000000045 BIOMD0000000159 BIOMD0000000312; do ln -s "$REPO/data/r31_curated/$m.xml" "$SIX/$m.xml"; done
sandbox "$CHK" "$SIX"
( cd "$CHK" && structure > /dev/null 2>&1 )
"$PY" - "$REPO" "$CHK" <<'EOF'
import json, sys
repo, chk = sys.argv[1], sys.argv[2]
def load(p):
    return {json.loads(l)['model']: json.loads(l) for l in open(p)}
bad = 0
for name, keys in (('r31_structure_traj.jsonl', ['status', 'loops', 'negative', 'integrating', 'plain_negative', 'plain_positive', 'nodes']),
                   ('r31_dynamics.jsonl', ['status', 'forced', 'behaviours'])):
    old, new = load(f'{repo}/results/{name}'), load(f'{chk}/results/{name}')
    for m, r in sorted(new.items()):
        a, b = {k: old[m].get(k) for k in keys}, {k: r.get(k) for k in keys}
        if a != b:
            bad += 1; print('MISMATCH', name, m, a, b)
    print(name, len(new), 'models compared on', keys)
print('release 31 check:', 'FAILED' if bad else 'reproduced')
sys.exit(1 if bad else 0)
EOF

# ---- 1. the hold-out
SB="$REPO/data/holdout_run"
sandbox "$SB" "$REPO/data/holdout_curated"
if ! diff -rq "$REPO/analysis" "$SB/analysis" -x __pycache__ > /dev/null; then echo "scripts differ from the repo's"; exit 1; fi
shasum -a 256 "$SB/analysis/address_predicts.py"
cd "$SB"
stamp "structure and dynamics, $(ls data/census_only | wc -l | tr -d ' ') models"
structure
stamp "integrators"
"$PY" analysis/integrators.py --list results/list_ok.txt --out results/r31_integrators.jsonl --jobs "$JOBS"
stamp "tabulate"
"$PY" analysis/tabulate.py results/r31_structure_traj.jsonl results/r31_dynamics.jsonl results/tables_traj.json results/r31_integrators.jsonl > /dev/null
stamp "truth tests"
"$PY" analysis/truth_tests.py
stamp "robust return"
"$PY" analysis/robust_return.py
stamp "atlas"
"$PY" analysis/fingerprints.py
stamp "address predicts"
python3 analysis/address_predicts.py
for f in r31_structure_traj.jsonl r31_dynamics.jsonl r31_integrators.jsonl; do cp "results/$f" "$REPO/results/holdout_${f#r31_}"; done
for f in tables_traj.json truth_tests.json robust_return.json fingerprints.json address_predicts.json; do cp "results/$f" "$REPO/results/holdout_$f"; done
stamp "done: results/holdout_*"
