# analysis/

The code behind *Every line is a loop*: count the feedback loops in the 640 curated models of BioModels release 31,
following Baudier, Fages and Soliman (2018), run each model to see what it does, test the loop table against that
behaviour, and repeat the census on the 435 models curated since. The top [README](../README.md) holds the one
command, the hardware and run time, the data, the pipeline drawn as a flow with its counts, and what can move in a
rebuild (04 pipeline lists what each script reads and writes).

## Scripts

In the order `run_all.sh` runs them, by its eight stages.

**The one command**

- `run_all.sh`: stages 1 to 8, from the raw downloads to the essay's fact check (7, `tools/check_facts.py`), the data
  audit and the read budgets. `sh analysis/run_all.sh [JOBS]`.

**1 data**

- `get_biomodels.sh`: downloads release 31, checks its SHA-256 and extracts the 640 curated SBML files to
  `data/r31_curated/`.
- `get_holdout.py`: lists the curated models BioModels holds that release 31 does not (`results/holdout_ids.json`,
  read 2026-11-16) and fetches them through the BioModels API into `data/holdout_curated/`, writing a SHA-256 per
  file to `results/holdout_manifest.json`. Standard library only, one request at a time.

**2 the release 31 census**

- `loops.py`: one model in, one JSON line out. Builds the reaction-labelled influence multigraph and
  enumerates loops under three definitions: every circuit (`thomas`); circuits passing the three filters
  of Baudier et al., Cor. 2.3 to 2.5 (`ref24`); and those minus circuits whose reactions are linearly
  dependent (`ref24_rank`, used on the page). Per definition it reports the loop count c, braking loops k,
  Sontag's distance to positive feedback on the filtered loops k_pf, loops through a running total j,
  per-loop types, and whether loops share arrows.
- `elim.py`: Baudier et al.'s vertex-elimination procedure (their Algorithms 2 and 3), used to decide
  whether an amplifying loop survives the filters even when there are too many loops to list. `loops.py` imports it.
- `dynamics.py`: runs each model at its published rates from its own start and 11 others spread across
  its conservation class, and records steady, multistable, oscillating, damped, unbounded or continuum
  behaviour; flags models driven by events or time.
- `integrators.py`: two more running-total readings. Loose: a variable whose own level moves its net rate
  by less than a tenth of the flow through it at the last state reached. Paired: two variables whose
  weighted sum changes at a rate that depends on neither of them at every state read (Khammash's
  antithetic controller keeps its total this way), excluding sums that equal one variable plus a constant
  once conserved totals are used.

**3 tables, toys and the speed-order test**

- `tabulate.py`: occupancy of each row under four counting rules, the essay's test (kinds of behaviour
  per row), the proven-rule checks, the replication against Baudier et al.'s Table 1, the alternative
  split (amplifying loops after the filters, braking loops as drawn) and the running-total controls.
- `audit.py`: two audits read from `results/` alone, in about a second: how many failures chance would have sent
  the proven-rule checks (and how often each rule, run backwards, forecasts its behaviour), and a sweep of the loose
  running-total cut with the models that fill the elements it adds. Writes `results/audit.json`; `--check` fails
  if the essay's sentences no longer match.
- `report_tables.py`: `results/tables.md`, the same numbers as Markdown.
- `toys.py`: the enzyme and three-gene ring of Figure 1 and a toy antithetic controller, built as SBML and
  counted by `loops.py` and `integrators.py`; it fails if any reading gets a toy wrong.
- `nesting.py`: tests the essay's guess that the loop table's missing factor of two is nesting order, three ways: a
  count of what nesting order adds per row, a toy circuit run with its amplifying loop fast and then with its brake
  fast, and the 42 curated two-loop models that mix one amplifying loop and one brake, each loop timed in the model's
  own Jacobian at the census's five moments. Writes `results/nesting.json`; `fold_census.py` draws the essay's nesting figure from it.
  Seeded, single-threaded, about five minutes.

**4 the tests of the laws and the atlas**

- `truth_tests.py`: three tests. The sign rules (memory needs an amplifying loop, a sustained rhythm a braking loop)
  on every model that runs on its own, from the census's own sign graph. Gain: a one-loop clock can only lose its steady
  state when its loop gain passes the secant floor, and a one-loop memory needs a gain above 1. Capability: models of one system at
  different detail compared, and every settling model stepped 20% per parameter to find exact returns from behaviour.
- `audit.py`: two audits read from `results/` alone, in about a second: how many failures chance would have sent
  the proven-rule checks (and how often each rule, run backwards, forecasts its behaviour), and a sweep of the loose
  running-total cut with the models that fill the elements it adds. Writes `results/audit.json`; `--check` fails
  if the essay's sentences no longer match.
- `robust_return.py`: each exact return found by `truth_tests.py`, redrawn at 5 random sets of the other rates (each
  scaled by 10^U(-0.15, 0.15), seeded); robust if it returns within 0.5% in every draw that settles, at least 3.
- `fingerprints.py`: the atlas. Settles each model, pushes it four standard ways (step, ramp, frequency response,
  baseline) and files it by the shape of its answer in one row: ticks, remembers, returns exactly, returns partly,
  rings or follows.
- `address_predicts.py`: does a model's square in the table predict its atlas row beyond the two sign rules?
  Leave-one-out majority vote against 10,000 shuffles inside sign strata, on the protocol fixed 2026-11-16 before
  any address-by-answer table was looked at. Reads `results/` only; standard library only.
- `trace_four.py`: the four exact returns that survive redrawn rates in models with one to three loops, traced for a
  hidden running total.

**5 the hold-out**

- `run_holdout.sh`: the release 31 pipeline, byte for byte, on the hold-out, from a copy of `analysis/` in a scratch
  root (`data/holdout_run/`). It first checks that six release 31 models reproduce their published records through
  the same mechanism. Outputs go to `results/holdout_*`.
- `holdout_score.py`: scores the hold-out against the fail lines frozen on 2026-11-16.
- `holdout_handcheck.py`: hand check of the hold-out's candidate exceptions to the sign rules: each model's
  equations and three facts the quick reading can miss.

**6 the essay's generated blocks**

- `build_post.py`: `build/count-the-elements.html`, the census chapter, built from `results/`. Hand-written labels
  and sentences are checked against the data by asserts, so the page fails to build rather than drift.
- `circuit_figures.py`: the essay's three deep circuit figures (the lac switch, the circadian clock, the chemotaxis
  adapter), each as cell, circuit and signal panes, written between the essay's `gen:` markers after the models are
  checked against what the page claims. `--check` writes nothing.
- `fold_census.py`: takes the census chapter's pieces from the build into the essay between its `gen:` markers,
  remaps their citations onto the essay's reference list and renumbers their figures.
- Imported by the three above, read nothing and write nothing:
  `table_figures.py` (the loop table itself: the two kinds of loop, element tiles, the orbital arithmetic, the
  30-element table), `loop_morph.py` (the punchline: both periodic tables wound from grid into loop),
  `story_figures.py` (the explainer figures: what a model is, a line closing into a loop, amplify and brake, cruise
  control, a two-way street versus a roundabout, a coastline measured with two rulers), `interactive.py` (the
  three-gene ring whose arrows flip, cruise control with a hill slider, the coastline with a ruler slider),
  `bio_figures.py` (three real circuits drawn the way cell biology draws them), `elements.py` (names, behaviour,
  examples and predictions for the 30 elements) and `post_math.py` (the methods' MathML).

**8 the data audit and the read budgets**

- `data_audit.py`: the funnel, class balance, duplicates, hold-out leakage, grouped recounts and the choices that
  shape the numbers, written to `results/data_audit.json` and `results/DATASHEET.md`. Seeded; 4 to 15 minutes by
  machine load.
- `read_budgets.py`: the essay's three read times (main read with folds closed, chapters with folds open, all with
  the supplement), counted by `fold_census.count_words()`, against Kat's targets of 15, 30 and 60 minutes. Prints
  them; `tools/check_facts.py` writes them into `results/fact_trace.md`.

**Apart from the one command**

- `budget.py`: imported by every per-model step, reads nothing and writes nothing. Counts CVODE's solver work after
  each simulate call (derivative evaluations, from CVODE's own counters) against a model's budget, and runs each
  model's subprocess under a wall-clock safety net that only stops a runaway.

## Choices that shape the numbers

- Signs of influences are read at each model's own states (t = 0, 1, 10, 100, 1000) at its curated
  parameters. The `random` mode reads them at random states, each variable drawn log-uniformly within the
  range it reaches on its own run; the page reports it and says whether the proven rules still hold there. Baudier
  et al. instead read signs symbolically, for every parameter setting at once.
- Decay, consumption and reverse-flux self-loops are dropped. A negative self-loop is kept only where a
  reaction producing the species slows as it rises without its rate law reaching zero (end-product
  inhibition, autorepression). Positive self-loops (autocatalysis) are kept.
- Reactions with net stoichiometry equal up to positive scaling count as one reaction for the filters;
  opposite stoichiometry counts as a reverse pair.
- The filters are proved for amplifying loops only. Braking loops are filtered the same way on the page,
  which leaves some substrate-depletion clocks with no braking loop; `tabulate.py` also reports the
  split that counts braking loops as drawn.
- Running totals, strict reading: a variable whose own value appears in none of the rate laws that
  change it.
- Loop searches stop after 5,000,000 steps or 20,000 loops; such models count as "search unfinished".
- Every per-model limit counts work, never seconds, so a rerun on a slower or busier machine files the same records.
  Solver work is counted in derivative evaluations (each CVODE right-hand-side call computes one rate per state
  variable), read from CVODE's counters after each simulate call (`budget.py`); a model that spends its budget gets
  the status `budget: solver work ...`. The budgets: 3e10 per model in `dynamics.py`, 4.1e10 in `fingerprints.py`,
  1.1e11 per test in `truth_tests.py` and per model in `robust_return.py`. Each was set from measurement so that every
  record that finished under the old wall-clock caps comes out the same. `dynamics.py` records carry timings, so its
  budget clears twice over the most work any committed model spends (1.17e10, BIOMD0000000137, measured alone on all
  28 models that took 88 s or more). The other records carry none, so their budget is the old cap times the fastest
  rate measured, 1.7e8 derivative evaluations per CPU second (240 s for the atlas, 600 s for the truth tests and the
  redrawn rates), which no model that finished under the cap can pass. libroadrunner restarts CVODE at every event and
  piecewise switch, resetting its counters, so for such models the count covers each call's last stretch only: still
  the same on any machine, but their runs are bounded by their fixed number and horizons rather than by the budget
  (BIOMD0000000408, a heartbeat pulse, takes 14 minutes alone), and so is the full Jacobian `dynamics.py` reads at
  each distinct fixed point (at most twelve; 325 s each for the 431-variable BIOMD0000000235). Each model runs in its
  own process under a 6-hour wall-clock safety net that no measured run comes near; if it fires it says so on stderr
  and the status names it.

`results/DATASHEET.md` (section 11) lists every such choice with the line that sets it and whether it was set before
or after the results were seen.
