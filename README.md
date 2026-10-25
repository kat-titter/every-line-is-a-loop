# Every line is a loop

Two essays proposing and testing a periodic table for the feedback circuits inside cells, with the code and data
that rebuild every number in them.

- **Every line is a loop: a periodic table for biology** (`every-line-is-a-loop.html`): the proposal. Count a
  circuit's feedback loops, how many of them brake, and how many keep a running total, and a table of 4, 9 and
  16 elements appears for one, two and three loops.
- **Every line is a loop. Let's count them.** (`count-the-elements.html`): the test. A census of the 640 curated
  models in BioModels release 31, placed on the table; what fills and what stays empty, and what the empty band
  says about the hypothesis.

Read them at https://kat-titter.github.io/every-line-is-a-loop/every-line-is-a-loop.html and
https://kat-titter.github.io/every-line-is-a-loop/count-the-elements.html. Each page is a single self-contained
HTML file with no external requests.

## Reproduce the census

```sh
python3.9 -m venv .venv && .venv/bin/pip install -r requirements.txt
sh analysis/run_all.sh 8
```

The last argument is the number of parallel jobs. The script downloads BioModels release 31 (193 MB, checksum
verified), runs the census in both sign modes, classifies dynamics, finds running totals, writes the tables to
`results/`, checks the toy models with known answers, and rebuilds `count-the-elements.html`. It takes about two
hours on a 10-core laptop. Every random draw is seeded and every loop search is step-budgeted, so a rerun gives
identical files apart from the timing field. `analysis/README.md` describes each script and the choices that
shape the numbers; `results/tables.md` holds the tables as Markdown.

## Layout

- `analysis/`: the census (`loops.py`, `elim.py`, `dynamics.py`, `integrators.py`, `tabulate.py`), the figures
  (`table_figures.py`, `story_figures.py`, `bio_figures.py`, `interactive.py`), the element names and predictions
  (`elements.py`) and the page builder (`build_post.py`).
- `results/`: the census output for release 31 (JSON Lines per model, summary tables).
- `tools/`: checks run on every build (tag balance and screenshots, reference numbering, figure overlaps).

## Licence

Code (`analysis/`, `tools/`) is MIT, see `LICENSE`. The essays, their text and figures, are CC BY 4.0, see
`LICENSE-TEXT.md`.
