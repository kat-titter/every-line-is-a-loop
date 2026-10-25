# Counting loops in BioModels

Code for the counting experiment of *Every line is a loop* (the essay's "Count the elements"), written up as *Every line is a loop. Let's count them.*: count the feedback
loops in the 640 curated models of BioModels release 31, following Baudier, Fages and Soliman (2018),
and compare rows nu = 1, 2 and 3 with the table's 4, 9 and 16 kinds. The results are written up in
`count-the-elements.html`, which is generated from `results/` by `build_post.py`.

## Reproduce

```sh
python3.9 -m venv .venv && .venv/bin/pip install -r requirements.txt
sh analysis/run_all.sh 8
```

The last argument is the number of parallel jobs. `run_all.sh` downloads the release (193 MB,
checksum verified), runs the census in both sign modes, classifies dynamics, finds running totals,
writes the tables to `results/`, checks Figure 1 on two toy models, and rebuilds the page. It takes
about two hours on a 10-core laptop. Every random draw is seeded, loop searches stop after a fixed number
of steps rather than a fixed time, BLAS runs single-threaded, and parallel jobs write in model order,
so a rerun gives identical files apart from the timing field `seconds`.

## Scripts

- `get_biomodels.sh`: downloads and verifies release 31 and extracts the curated SBML files.
- `loops.py`: one model in, one JSON line out. Builds the reaction-labelled influence multigraph and
  enumerates loops under three definitions: every circuit (`thomas`); circuits passing the three filters
  of Baudier et al., Cor. 2.3 to 2.5 (`ref24`); and those minus circuits whose reactions are linearly
  dependent (`ref24_rank`, used on the page). Per definition it reports the loop count c, braking loops k,
  Sontag's distance to positive feedback on the filtered loops k_pf, loops through a running total j,
  per-loop types, and whether loops share arrows.
- `elim.py`: Baudier et al.'s vertex-elimination procedure (their Algorithms 2 and 3), used to decide
  whether an amplifying loop survives the filters even when there are too many loops to list.
- `dynamics.py`: runs each model at its published rates from its own start and 11 others spread across
  its conservation class, and records steady, multistable, oscillating, damped, unbounded or continuum
  behaviour; flags models driven by events or time.
- `integrators.py`: two more running-total readings. Loose: a variable whose own level moves its net rate
  by less than a tenth of the flow through it at the last state reached. Paired: two variables whose
  weighted sum changes at a rate that depends on neither of them at every state read (Khammash's
  antithetic controller keeps its total this way), excluding sums that equal one variable plus a constant
  once conserved totals are used.
- `tabulate.py`: occupancy of each row under four counting rules, the essay's test (kinds of behaviour
  per row), the proven-rule checks, the replication against Baudier et al.'s Table 1, the alternative
  split (amplifying loops after the filters, braking loops as drawn) and the running-total controls.
- `report_tables.py`: `results/tables.md`, the same numbers as Markdown.
- `toys.py`: the enzyme and three-gene ring of Figure 1 and a toy antithetic controller, built as SBML and
  counted by `loops.py` and `integrators.py`; it fails if any reading gets a toy wrong.
- `table_figures.py`: figures of the loop table itself (the two kinds of loop, element tiles, the orbital
  arithmetic, the full 30-element table, and both periodic tables drawn as spirals). `post_math.py`: the
  MathML equations of the methods. `story_figures.py`: the explainer figures (what a model is, a line
  closing into a loop, amplify and brake, count the brakes, cruise control simulated, a two-way street
  versus a roundabout, a coastline measured with two rulers).
- `interactive.py`: the interactive figures (a three-gene ring whose arrows you flip, simulated live and
  checked in Python for all eight sign patterns; cruise control with a hill slider; a coastline with a
  ruler slider).
- `build_post.py`: `count-the-elements.html`. Hand-written labels and sentences are checked against
  the data by asserts, so the page fails to build rather than drift.

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

## nesting.py

Tests the essay's guess that the loop table's missing factor of two is nesting order, three ways: a count of what nesting order adds per row, a toy circuit run with its amplifying loop fast and then with its brake fast, and the 42 curated two-loop models that mix one amplifying loop and one brake, each loop timed in the model's own Jacobian at the census's five moments. Writes `results/nesting.json`; `fold_census.py` draws Figure 13 from it. Seeded, single-threaded, about five minutes.
