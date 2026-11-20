"""Check every data fact on the essay against the results files that produce it.

Reads every-line-is-a-loop.html, results/*.json(l) and the essay's model code (analysis/circuit_figures.py).
Writes results/fact_trace.md: one row per fact (what the page should say, where, the source file and key, match),
then the three read budgets (analysis/read_budgets.py) against their targets, then every other sentence on the page
that carries a number, classed as cited (a reference marker) or unclassified.
Exits 1 if any fact is missing from the page, a known slip is back, or the masthead's read time is not the main read's
(a budget over its target is reported, not failed), so it can run before every publish:

    .venv/bin/python tools/check_facts.py [--page PATH]

A fact is a phrase built from computed values. It matches when the phrase appears, after whitespace is collapsed,
in the text of its section. Generated blocks (between gen: markers) are checked here too; the same numbers are
asserted again where build_post.py, fold_census.py and circuit_figures.py write them.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT / "analysis"))

WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]


TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def word(n: int, cap: bool = False) -> str:
    """A count as the page writes it in words ("five", "twenty-four"), capitalised at the start of a sentence."""
    w = WORDS[n] if n < len(WORDS) else TENS[n // 10] + (f"-{WORDS[n % 10]}" if n % 10 else "")
    return w.capitalize() if cap else w


def pct(x: float, places: int = 1) -> str:
    """A fraction as a percentage string without the sign: 0.6591 -> '65.9'."""
    return f"{100 * x:.{places}f}"


def load(name: str):
    return json.loads((RESULTS / name).read_text())


def load_jsonl(name: str) -> dict[str, dict]:
    return {r["model"]: r for r in map(json.loads, (RESULTS / name).open()) if r}


# ------------------------------------------------------------------ the page as text, by section and kind


@dataclass
class Block:
    section: str
    kind: str  # main, fold, caption, table, card, figure (Figure 8's pipeline drawing), supplement, refs
    text: str
    gen: str  # the gen: block that writes it, or ""
    label: bool  # a heading, kicker, control or readout rather than prose
    row: int  # the table row it sits in, or 0


class _PageText(HTMLParser):
    SKIP = {"script", "style", "svg", "math"}
    BLOCK = {
        "p",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "td",
        "th",
        "figcaption",
        "summary",
        "caption",
        "pre",
        "div",
        "tr",
        "blockquote",
        "dt",
        "dd",
    }
    LABEL = {"h1", "h2", "h3", "h4", "summary", "nav", "label", "output", "button", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.section = "top"
        self.folds = self.captions = self.tables = self.labels = 0
        self.rows = self.row = 0
        self.pf = False  # inside Figure 8's pipeline drawing, whose step labels are page text
        self.gen: list[str] = []
        self.buf: list[str] = []
        self.blocks: list[Block] = []

    def kind(self) -> str:
        if self.section in ("supplement", "refs"):
            return self.section
        if self.pf:
            return "figure"
        return "caption" if self.captions else "table" if self.tables else "fold" if self.folds else "main"

    def flush(self) -> None:
        text = " ".join("".join(self.buf).split())
        if text:
            self.blocks.append(
                Block(self.section, self.kind(), text, self.gen[-1] if self.gen else "", self.labels > 0, self.row)
            )
        self.buf = []

    def handle_comment(self, data):
        mark = data.strip()
        if mark.startswith("gen:"):
            self.flush()
            self.gen.append(mark)
        elif mark.startswith("/gen:") and self.gen:
            self.flush()
            self.gen.pop()

    def handle_starttag(self, tag, attrs):
        if tag == "svg" and dict(attrs).get("id") == "pf" and not self.skip:
            self.flush()
            self.pf = True
            return
        if self.pf:
            if tag == "g" and "pf-node" in (dict(attrs).get("class") or ""):
                self.flush()
            elif tag == "text":
                self.buf.append(" ")
            return
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in self.BLOCK or tag == "section":
            self.flush()
        if tag == "section" and dict(attrs).get("id"):
            self.section = dict(attrs)["id"]
        self.folds += tag == "details"
        self.captions += tag == "figcaption"
        self.tables += tag == "table"
        self.labels += tag in self.LABEL
        a = dict(attrs)
        if a.get("data-d"):  # a hover card (Figure 15): its text and its sources
            self.blocks.append(
                Block(
                    self.section,
                    "card",
                    " ".join(
                        f"{a.get('data-t', '')}, {a.get('data-k', '')}: {a['data-d']} {a.get('data-s', '')}".split()
                    ),
                    "",
                    False,
                    0,
                )
            )
        if tag == "tr":
            self.rows += 1
            self.row = self.rows

    def handle_endtag(self, tag):
        if self.pf:
            if tag in ("svg", "g"):
                self.flush()
            self.pf = tag != "svg"
            return
        if tag in self.SKIP:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag in self.BLOCK:
            self.flush()
        self.folds -= tag == "details"
        self.captions -= tag == "figcaption"
        self.tables -= tag == "table"
        self.labels -= tag in self.LABEL
        if tag == "tr":
            self.row = 0

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


def page_blocks(path: pathlib.Path) -> list[Block]:
    """Visible text of the page (no scripts, styles, drawings or MathML), one block per paragraph, cell or caption."""
    parser = _PageText()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.flush()
    return parser.blocks


# ------------------------------------------------------------------ values, each computed from its source


def values() -> tuple[dict[str, object], dict[str, str]]:
    """Every number the facts quote, with the file and key it comes from."""
    import build_post
    import circuit_figures as cf
    from fold_census import truth_numbers

    v: dict[str, object] = {}
    src: dict[str, str] = {}

    def put(name: str, value: object, source: str) -> None:
        v[name], src[name] = value, source

    tables = load("tables_traj.json")
    rank = tables["defs"]["ref24_rank"]
    rows = {n: rank["rows"][str(n)] for n in (1, 2, 3)}
    struct = load_jsonl("r31_structure_traj.jsonl")
    dyn = load_jsonl("r31_dynamics.jsonl")
    tt = "tables_traj.json"

    put("census", sum(tables["census"].values()), f"{tt} census (sum)")
    put("usable", tables["usable"], f"{tt} usable")
    put("excluded", v["census"] - v["usable"], f"{tt} census - usable")
    put(
        "complete",
        tables["integrators"]["models with complete ref24_rank enumeration"],
        f"{tt} integrators.models with complete ref24_rank enumeration",
    )
    put("small", sum(rows[n]["models"] for n in (1, 2, 3)), f"{tt} defs.ref24_rank.rows[1..3].models")
    put("le3", sum(rank["distribution"].get(c, 0) for c in "0123"), f"{tt} defs.ref24_rank.distribution[0..3]")
    put("unfinished", rank["distribution"]["over budget"], f"{tt} defs.ref24_rank.distribution['over budget']")
    put("forced", tables["theorem_checks"]["forced models excluded"], f"{tt} theorem_checks.forced models excluded")
    run_alone = sum(
        1
        for m, d in dyn.items()
        if d.get("status") == "ok" and not d.get("forced") and struct.get(m, {}).get("status") == "ok"
    )
    put("run_alone", run_alone, "r31_dynamics.jsonl: status ok, not forced (as build_post.build)")
    put(
        "spent",
        sum(1 for d in dyn.values() if str(d.get("status", "")).startswith("budget")),
        "r31_dynamics.jsonl status starts with 'budget' (dynamics.WORK_BUDGET spent)",
    )
    why = Counter(build_post.why_excluded(r) for r in struct.values() if r.get("status") != "ok")
    for key, label in (
        ("delays", "use built-in delays"),
        ("onoff", "use on-off rules"),
        ("unset", "have values the solver cannot set"),
        ("no_arrows", "gave no arrows at the states read"),
    ):
        put(key, why[label], f"r31_structure_traj.jsonl status != ok, classed by build_post.why_excluded: {label}")

    # occupancy of rows one to three, strict reading; a cell key is "(k, j)"
    cells = {n: rows[n]["essay"]["cells"] for n in (1, 2, 3)}
    nort_total = sum(n + 1 for n in (1, 2, 3))
    rt_total = sum((n + 1) ** 2 - (n + 1) for n in (1, 2, 3))
    nort = sum(1 for n in (1, 2, 3) for c in cells[n] if c.endswith(", 0)"))
    rt = sum(1 for n in (1, 2, 3) for c in cells[n] if not c.endswith(", 0)"))
    put("nort_total", nort_total, "rows one to three: elements with j = 0")
    put("nort", nort, f"{tt} defs.ref24_rank.rows[1..3].essay.cells with j = 0")
    put("rt_total", rt_total, "rows one to three: elements with j > 0")
    put("rt", rt, f"{tt} defs.ref24_rank.rows[1..3].essay.cells with j > 0")
    put("rt_blank", rt_total - rt, "rt_total - rt")
    put("rt_blank_word", word(rt_total - rt), "rt_total - rt, in words")
    put("rt_total_word", word(rt_total), "rt_total, in words")
    put("squares", nort_total + rt_total, "4 + 9 + 16")
    put(
        "rt_found_models",
        cells[2].get("(1, 1)", 0) + cells[2].get("(1, 2)", 0) + cells[3].get("(2, 1)", 0),
        f"{tt} cells (2,1,1) + (2,1,2) + (3,2,1)",
    )
    put("ad_models", cells[1].get("(1, 1)", 0), f"{tt} defs.ref24_rank.rows[1].essay.cells['(1, 1)']")
    put(
        "ro_models",
        cells[2].get("(1, 0)", 0),
        f"{tt} defs.ref24_rank.rows[2].essay.cells['(1, 0)'] (Ro, Figure 6's sample)",
    )
    loose = {n: rows[n]["essay_near"]["occupied"] for n in (1, 2, 3)}
    put("loose_full_12", loose[1] == 4 and loose[2] == 9, f"{tt} rows[1,2].essay_near.occupied == 4, 9")
    put("loose_blank3", 16 - loose[3], f"16 - {tt} rows[3].essay_near.occupied")
    rnd = load("tables_random.json")["defs"]["ref24_rank"]["rows"]
    put("random2", rnd["2"]["essay"]["occupied"], "tables_random.json rows[2].essay.occupied")
    put("random3", rnd["3"]["essay"]["occupied"], "tables_random.json rows[3].essay.occupied")
    for n in (1, 2, 3):
        put(f"kinds{n}", rows[n]["distinct_autonomous_behaviours"], f"{tt} rows[{n}].distinct_autonomous_behaviours")
        put(f"coarse{n}", len(rows[n]["coarse_behaviours"]), f"{tt} rows[{n}].coarse_behaviours (count)")
        put(f"types4_{n}", rows[n]["types4"]["occupied"], f"{tt} rows[{n}].types4.occupied")
        put(f"types3_{n}", rows[n]["types3"]["occupied"], f"{tt} rows[{n}].types3.occupied")
    put(
        "unsettled",
        sum(rows[n]["behaviours"].get("unsettled", 0) for n in (1, 2, 3)),
        f"{tt} rows[1..3].behaviours.unsettled",
    )
    put("nu_differs", sum(rows[n]["nu_differs"] for n in (1, 2, 3)), f"{tt} rows[1..3].nu_differs")
    put("kpf_differs", sum(rows[n]["k_pf_differs"] for n in (1, 2, 3)), f"{tt} rows[1..3].k_pf_differs")
    put("split_moved", tables["split"]["moved"], f"{tt} split.moved")
    defs = tables["defs"]
    put(
        "loops_counted",
        " ".join(
            f"{label} " + " ".join(str(defs[d]["rows"][n]["models"]) for n in "123")
            for d, label in (
                ("thomas", "every loop, as drawn"),
                ("ref24", "after the filters"),
                ("ref24_rank", "after the filters and the rank test (used here)"),
            )
        ),
        f"{tt} defs.*.rows[1..3].models",
    )
    rep, r24 = tables["replication"]["with reactions"], tables["replication"]["reference 24"]
    put("rep_n", rep["models"], f"{tt} replication['with reactions'].models")
    for key, field in (
        ("nobrake", "no negative circuit"),
        ("nopos", "no positive circuit"),
        ("norefined", "no refined positive circuit"),
    ):
        put(
            f"r24_{key}",
            f"{100 * r24[field] / r24['models']:.0f}%",
            f"{tt} replication['reference 24']['{field}'] / models",
        )
        put(
            f"rep_{key}",
            f"{100 * rep[field] / rep['models']:.0f}%",
            f"{tt} replication['with reactions']['{field}'] / models",
        )
    m270 = struct["BIOMD0000000270"]["defs"]["ref24_rank"]
    put(
        "erk_loops",
        m270["c"] if m270["k"] == m270["c"] else -1,
        "r31_structure_traj.jsonl BIOMD0000000270 defs.ref24_rank (c, all braking)",
    )
    put("paired", len(tables["paired_totals"]["models with one"]), f"{tt} paired_totals.models with one")
    integ = load_jsonl("r31_integrators.jsonl")
    put(
        "loose_models",
        sum(1 for d in integ.values() if d.get("near_integrators")),
        "r31_integrators.jsonl near_integrators non-empty",
    )
    put(
        "pair_unchecked",
        sum(d.get("pair_unchecked") or 0 for d in integ.values()),
        "r31_integrators.jsonl sum pair_unchecked",
    )
    controls = tables["controls"]
    put("schaber_loops", f"{controls['BIOMD0000000429']['loops']:,}", f"{tt} controls.BIOMD0000000429.loops")
    put("petelenz_loops", f"{controls['BIOMD0000000603']['loops']:,}", f"{tt} controls.BIOMD0000000603.loops")
    rep12 = struct["BIOMD0000000012"]
    put("rep_species", word(rep12["species"]).capitalize(), "r31_structure_traj.jsonl BIOMD0000000012 species")
    put("rep_reactions", word(rep12["reactions"]), "r31_structure_traj.jsonl BIOMD0000000012 reactions")
    runs12 = dyn["BIOMD0000000012"]["runs"]
    put(
        "rep_ticks_all",
        word(len(runs12)) if all(r == "oscillating" for r in runs12) else "not all",
        "r31_dynamics.jsonl BIOMD0000000012 runs (one label per start)",
    )

    # the proven rules, gain, families, step and return
    truth = load("truth_tests.json")
    N = truth_numbers()
    put("auto", N["auto"], "truth_tests.json rules.autonomous")
    # Figure 8's pipeline: what each step set aside, by subtraction
    put("not_listed", v["usable"] - v["complete"], f"{tt} usable - integrators.models with complete enumeration")
    put("not_own", v["usable"] - v["run_alone"], f"{tt} usable - r31_dynamics.jsonl run on their own")
    put(
        "unlabelled",
        v["run_alone"] - v["auto"],
        "r31_dynamics.jsonl run on their own - truth_tests.json rules.autonomous",
    )
    put("mem", N["mem"], "truth_tests.json rules.memory (memory_without_amplifying_loop empty)")
    put("clk", N["clk"], "truth_tests.json rules.clock (clock_without_braking_loop empty)")
    put(
        "single",
        len(N["single"]) if len(N["s_above"]) + len(N["s_below"]) == len(N["single"]) else -1,
        "truth_tests.json gain_brake, rings single as drawn (fold_census.truth_numbers), all called",
    )
    put("rings", len(N["rings"]), "truth_tests.json gain_brake, measurable rings")
    put("rings_hit", len(N["above"]) + len(N["below"]), "truth_tests.json gain_brake: clocks above floor + calm below")
    put(
        "miss_year",
        re.findall(r"\d{4}", struct[N["miss"][0]["model"]]["name"])[0] if len(N["miss"]) == 1 else "more than one miss",
        "truth_tests.json gain_brake: the one ring that ticks at or below its floor (the year in its name)",
    )
    put(
        "miss_name",
        ", ".join(struct[r["model"]]["name"].split(" - ")[0].replace("_", " ") for r in N["miss"]),
        "truth_tests.json gain_brake: ticks at or below floor",
    )
    put("toggle_tip", f"{N['tip']:.2f}", "truth_tests.json gain_amplify BIOMD0000000507 unstable state G")
    put(
        "toggle_rest",
        f"{N['rest'][0]:.3f} and {N['rest'][1]:.2f}",
        "truth_tests.json gain_amplify BIOMD0000000507 stable states G",
    )
    rep_gain = next(r["G"] for r in N["rings"] if r["model"] == "BIOMD0000000012")
    put("rep_gain", f"{rep_gain:.1f}", "truth_tests.json gain_brake BIOMD0000000012 G")
    fly = truth["families"]["fruit fly day clock"]
    put("fly_models", len(fly), "truth_tests.json families['fruit fly day clock'] (count)")
    put(
        "fly_addresses",
        len({(m["loops"], m["brakes"], m["running_totals"]) for m in fly}),
        "truth_tests.json families['fruit fly day clock'] distinct (loops, brakes, totals)",
    )
    put(
        "fly_all_tick",
        all("oscillating" in m["behaviours"] for m in fly),
        "truth_tests.json families['fruit fly day clock'] behaviours",
    )
    put("fams", len(N["fams"]), "truth_tests.json families, Smallbone left out (fold_census.truth_numbers)")
    put("fams_word", word(len(N["fams"])), "truth_tests.json families (fold_census.truth_numbers), in words")
    put("fams_does", sum(N["does"].values()), "truth_tests.json families: one set of behaviours")
    put(
        "fams_moved_word",
        word(v["fams"] - v["fams_does"]),
        "truth_tests.json families: more than one set of behaviours, in words",
    )
    put("fams_sits", sum(N["sits"].values()), "truth_tests.json families: one (loops, brakes, totals)")
    put("settling", N["settling"], "truth_tests.json step, status ok")
    put("exact", N["exact"], "truth_tests.json step, exact_returns non-empty")
    put("robust", len(N["robust"]), "robust_return.json, a robust pair")
    put("band", len(N["band"]), "robust_return.json robust, 1 to 3 loops")
    put(
        "band_list",
        ", ".join(
            f"{m['name'].split(' - ')[0].replace('_', ' ')} ({m['loops']} loop{'s' if m['loops'] > 1 else ''})"
            for m in N["band"]
        ),
        "robust_return.json robust, 1 to 3 loops: name and loops",
    )
    tr4 = load("trace_four.json")
    kinds = Counter(x["kind"] for x in tr4["all robust returns"])
    put("robust_exact", kinds["exact"], "trace_four.json all robust returns, kind == exact")
    four = {x["model"] for x in tr4["the four"]}
    put(
        "four_exact",
        word(sum(1 for x in tr4["all robust returns"] if x["model"] in four and x["kind"] == "exact")).capitalize(),
        "trace_four.json all robust returns of the four, kind == exact",
    )

    # the atlas
    fp = load("fingerprints.json")
    answers = ["ticks", "remembers", "returns exactly", "returns partly", "rings", "follows"]
    filed = [m for m in fp["models"] if m.get("status") == "ok" and m.get("row") in answers]
    put("fp_models", len(fp["models"]), "fingerprints.json models (count)")
    put("fp_read", sum(fp["rows"].values()), "fingerprints.json rows (sum, flat included)")
    put("fp_flat", fp["rows"]["flat"], "fingerprints.json rows.flat")
    put("fp_filed", len(filed), "fingerprints.json models filed in the six rows")
    for a in answers:
        key = a.replace(" ", "_")
        put(f"fp_{key}", fp["rows"][a], f"fingerprints.json rows['{a}']")
        put(
            f"wire_{key}",
            len({tuple(m["address"]) for m in filed if m["row"] == a and m.get("address")}),
            f"fingerprints.json models in '{a}', distinct address",
        )
    put(
        "wire_max",
        max(v[f"wire_{a.replace(' ', '_')}"] for a in answers),
        "fingerprints.json, most addresses in one row",
    )
    ticks = [m for m in filed if m["row"] == "ticks"]
    remembers = [m for m in filed if m["row"] == "remembers"]
    put(
        "ticks_brake",
        sum(1 for m in ticks if struct[m["model"]].get("plain_negative")),
        "fingerprints.json ticks x r31_structure_traj plain_negative",
    )
    put(
        "rem_selffeed",
        sum(
            1
            for m in remembers
            if struct[m["model"]].get("plain_positive") or struct[m["model"]].get("refined_positive")
        ),
        "fingerprints.json remembers x r31_structure_traj plain/refined_positive",
    )
    yeast = next(c for c in fp["checks"] if c["model"] == "BIOMD0000000603")
    put(
        "yeast_min",
        round((yeast["solver_stopped_at"] - 3600) / 60),
        "fingerprints.json checks BIOMD0000000603 solver_stopped_at, salt step at 3600",
    )
    put(
        "yeast_fold",
        round(yeast["trace"][-1][1]),
        "fingerprints.json checks BIOMD0000000603 last trace point (relative to before the step)",
    )
    put(
        "tyson_row",
        next(c for c in fp["checks"] if c["model"] == "BIOMD0000000312")["row"],
        "fingerprints.json checks BIOMD0000000312 row",
    )

    # the address test
    ap, hap = load("address_predicts.json"), load("holdout_score.json")["the address"]
    amended = ap["amended_primary"]
    put("ap_n", amended["n"], "address_predicts.json amended_primary.n (first form void)")
    put("ap_address", pct(amended["accuracy"]["address"]), "address_predicts.json amended_primary.accuracy.address")
    put("ap_sign", pct(amended["accuracy"]["sign"]), "address_predicts.json amended_primary.accuracy.sign")
    put("hap_n", hap["n"], "holdout_score.json 'the address'.n")
    put("hap_address", pct(hap["accuracy"]["address"]), "holdout_score.json 'the address'.accuracy.address")
    put("hap_sign", pct(hap["accuracy"]["sign"]), "holdout_score.json 'the address'.accuracy.sign")

    # the hold-out
    ho = load("holdout_score.json")
    hids = load("holdout_ids.json")
    put("ho_listed", len(hids["holdout"]), "holdout_ids.json holdout (count)")
    put("ho_n", ho["sign rules"]["n"], "holdout_score.json 'sign rules'.n")
    put("models_670", v["auto"] + v["ho_n"], "truth_tests.json rules.autonomous + holdout_score.json 'sign rules'.n")
    cands = ho["sign rules"]["candidate exceptions"]
    put("ho_cands", len(cands), "holdout_score.json 'sign rules'.candidate exceptions (count)")
    hand = {h["model"]: h for h in load("holdout_handcheck.json")}

    def cleared(c: dict) -> bool:
        h = hand[c["model"]]
        further = h.get("further check", {})
        if c["rule"] == "ticks with no brake":
            return h["has a brake"] or further.get("peaks of N_CTL in the second half of a 4000-unit run") == 0
        return further.get("stable fixed points") == 0

    put("ho_cands_word", word(len(cands)), "holdout_score.json 'sign rules'.candidate exceptions (count, in words)")
    put("ho_read", ho["funnel"]["read as equations"], "holdout_score.json funnel['read as equations']")
    put("ho_run_alone", ho["funnel"]["run on their own"], "holdout_score.json funnel['run on their own']")
    put(
        "ho_unusable",
        v["ho_listed"] - v["ho_read"],
        "holdout_ids.json holdout (count) - holdout_score.json funnel['read as equations']",
    )
    put(
        "ho_not_own",
        v["ho_read"] - v["ho_run_alone"],
        "holdout_score.json funnel['read as equations'] - funnel['run on their own'] (forced, timed out or failed)",
    )
    put("ho_small", ho["funnel"]["one to three loops"], "holdout_score.json funnel['one to three loops']")
    put("ho_atlas_read", ho["funnel"]["atlas read"], "holdout_score.json funnel['atlas read']")
    put("ho_flat", ho["six answers"]["rows"]["flat"], "holdout_score.json 'six answers'.rows.flat")
    put(
        "blind_n",
        len(ho["six answers"]["twenty for the blind read"]),
        "holdout_score.json 'six answers'.twenty for the blind read (count)",
    )
    put("ho_follows_pct", pct(ho["six answers"]["follows share"]), "holdout_score.json 'six answers'.follows share")
    put(
        "ho_cleared",
        sum(cleared(c) for c in cands),
        "holdout_handcheck.json: brake found, or no ticking / no two states on a closer run",
    )
    put(
        "ho_rings",
        ho["strength"]["single as drawn"] if not ho["strength"]["misses (ticks at or below floor)"] else -1,
        "holdout_score.json strength.single as drawn, no misses",
    )
    six = ho["six answers"]
    put("ho_filed", six["filed"], "holdout_score.json 'six answers'.filed")
    put("ho_follows", six["rows"]["follows"], "holdout_score.json 'six answers'.rows.follows")
    put(
        "ho_over_half",
        "just over half" if 0.5 < six["follows share"] < 0.55 else f"{six['follows share']:.2f}",
        "holdout_score.json 'six answers'.follows share",
    )
    put(
        "r31_follows",
        f"{100 * six['release 31 follows share']:.0f}%",
        "holdout_score.json 'six answers'.release 31 follows share",
    )
    blank = ho["blank squares"]
    put(
        "ho_new_rt",
        len(blank["newly filled, empty in release 31"]),
        "holdout_score.json 'blank squares'.newly filled, empty in release 31",
    )
    put(
        "ho_row3_rt",
        sum(
            1
            for k in blank["squares filled in the hold-out (loops, brakes, totals)"]
            if k.startswith("(3,") and not k.endswith(", 0)")
        ),
        "holdout_score.json blank squares: row 3 squares with a total",
    )
    hk = blank["kinds of behaviour against squares, by row"]
    put("ho_kinds2", hk["2"][0], "holdout_score.json 'blank squares'.kinds of behaviour, row 2")
    put("ho_kinds3", hk["3"][0], "holdout_score.json 'blank squares'.kinds of behaviour, row 3")

    # PR #1's audit: what a clean record is worth, and the loose reading's dial (analysis/audit.py)
    au = load("audit.json")
    sw, cl, dl = au["rules"]["switch"], au["rules"]["clock"], au["dial"]
    sweep = dl["sweep"]
    put("au_auto", au["rules"]["autonomous"], "audit.json rules.autonomous")
    put("sw_without", sw["models_without"], "audit.json rules.switch.models_without")
    put("sw_expected", f"{sw['expected_without_by_chance']:.1f}", "audit.json rules.switch.expected_without_by_chance")
    put(
        "sw_half",
        "about half the time" if 0.4 < sw["p_none_by_chance"] < 0.6 else f"{sw['p_none_by_chance']:.2f} of the time",
        "audit.json rules.switch.p_none_by_chance",
    )
    put("cl_without", cl["models_without"], "audit.json rules.clock.models_without")
    put("cl_expected", round(cl["expected_without_by_chance"]), "audit.json rules.clock.expected_without_by_chance")
    put(
        "cl_odds",
        f"one in {round(1 / cl['p_none_by_chance'] / 1e6)} million",
        "audit.json rules.clock.p_none_by_chance (as audit.odds)",
    )
    tails = round(math.log2(1 / cl["p_none_by_chance"]))
    put("cl_tails", tails, "audit.json rules.clock.p_none_by_chance: log2(1/p), rounded")
    put("cl_tails_word", word(tails), "audit.json rules.clock.p_none_by_chance: log2(1/p), in words")
    put("tails_odds", f"{round(2**tails / 1e6)} million", "2 ** cl_tails, in millions")
    put("sw_with", sw["models_with_loop"], "audit.json rules.switch.models_with_loop")
    put("sw_beh", sw["behaving_with_loop"], "audit.json rules.switch.behaving_with_loop")
    put("cl_with", cl["models_with_loop"], "audit.json rules.clock.models_with_loop")
    put("cl_beh", cl["behaving_with_loop"], "audit.json rules.clock.behaving_with_loop")
    put(
        "sw_one_in",
        round(sw["models_with_loop"] / sw["behaving_with_loop"]),
        "audit.json switch: with loop / switching",
    )
    put(
        "cl_in_ten",
        round(10 * cl["behaving_with_loop"] / cl["models_with_loop"]),
        "audit.json clock: ticking / with brake, in tenths",
    )
    put("sw_prec", f"{100 * sw['behaving_with_loop'] / sw['models_with_loop']:.0f}%", "audit.json switch: precision")
    put("cl_prec", f"{100 * cl['behaving_with_loop'] / cl['models_with_loop']:.0f}%", "audit.json clock: precision")
    put(
        "sw_recall",
        "perfect" if sw["behaving_without_loop"] == 0 else "imperfect",
        "audit.json rules.switch.behaving_without_loop == 0",
    )
    put(
        "cl_recall",
        "perfect" if cl["behaving_without_loop"] == 0 else "imperfect",
        "audit.json rules.clock.behaving_without_loop == 0",
    )
    put("dial_strict", dl["strict"]["filled"], "audit.json dial.strict.filled")
    put("dial_zero", sweep["0.0"]["filled"], "audit.json dial.sweep['0.0'].filled")
    put("dial_hundredth", sweep["0.01"]["filled"], "audit.json dial.sweep['0.01'].filled")
    put("dial_tenth", sweep["0.1"]["filled"], "audit.json dial.sweep['0.1'].filled")
    put("dial_one", sweep["1.0"]["filled"], "audit.json dial.sweep['1.0'].filled")
    put("dial_added", sweep["0.1"]["filled"] - dl["strict"]["filled"], "audit.json dial: sweep['0.1'] - strict")
    put("new_cells", dl["new_cells_at_zero"], "audit.json dial.new_cells_at_zero")
    put("models_zero", dl["models_at_zero"], "audit.json dial.models_at_zero")
    put("volt_word", word(dl["voltage_models"]), "audit.json dial.voltage_models, in words")
    put("volt_alone", dl["cells_on_voltage_alone"], "audit.json dial.cells_on_voltage_alone")
    put(
        "volt_all_osc",
        "Every one of those voltages oscillates"
        if dl["voltage_models_oscillate"] == dl["voltage_models"]
        else f"{dl['voltage_models_oscillate']} of those voltages oscillate",
        "audit.json dial.voltage_models_oscillate == voltage_models",
    )
    put(
        "volt_half",
        "half" if 2 * dl["voltage_models"] == dl["models_at_zero"] else f"{dl['voltage_models']}",
        "audit.json dial.voltage_models / models_at_zero",
    )
    put("readings_below", f"{dl['readings_below_one']:,}", "audit.json dial.readings_below_one")
    put("readings_zero", dl["readings_at_zero"], "audit.json dial.readings_at_zero")

    # nesting
    nest = load("nesting.json")
    toy = nest["toy"]
    put("mixed_models", nest["census"]["mixed_two_loop_models"], "nesting.json census.mixed_two_loop_models")
    put("toy_draws", toy["settings"]["draws"], "nesting.json toy.settings.draws")
    put("toy_clocks", toy["amplify fast"]["keeps time"], "nesting.json toy['amplify fast']['keeps time']")
    put("toy_swapped", toy["brake fast"]["keeps time"], "nesting.json toy['brake fast']['keeps time']")
    tt_ = nest["census"]["transit_time"]["table"]
    put(
        "transit",
        f"{tt_['amplifying']['keeps time']} of {sum(tt_['amplifying'].values())} against {tt_['braking']['keeps time']} of {sum(tt_['braking'].values())}",
        "nesting.json census.transit_time.table",
    )
    put(
        "brake_fast_clocks",
        word(tt_["braking"]["keeps time"]),
        "nesting.json census.transit_time.table.braking['keeps time']",
    )
    count = {r["loops"]: r for r in nest["count"]}
    put(
        "ordered",
        ", ".join(str(count[n]["types_ordered"]) for n in (1, 2)) + f" and {count[3]['types_ordered']}",
        "nesting.json count[1..3].types_ordered",
    )
    put(
        "electrons",
        ", ".join(str(count[n]["chemistry_2n2"]) for n in (1, 2)) + f" and {count[3]['chemistry_2n2']}",
        "nesting.json count[1..3].chemistry_2n2",
    )

    # the depletion clocks (Figure S9), and the essay's own model figures
    put(
        "dep_clocks",
        len(build_post.DEPLETION_KIND),
        "build_post.DEPLETION_KIND, asserted equal to the clocks with no brake in tables (build_post.build)",
    )
    L_off, L_on = cf.sw_thresholds()
    put("sw_off", f"{L_off:.1f}", "circuit_figures.sw_thresholds (lac model, where it lets go)")
    put("sw_on", f"{L_on:.1f}", "circuit_figures.sw_thresholds (lac model, where it commits)")
    put("ck_delay", word(int(cf.CK["D"])), "circuit_figures.CK['D']")
    put("ck_period", round(cf.check_clock()), "circuit_figures.check_clock (period at CK['D'])")
    put(
        "secant",
        ", ".join(f"{1 / math.cos(math.pi / n) ** n:.3g} for n = {n}" for n in (3, 4))
        + f" and {1 / math.cos(math.pi / 6) ** 6:.3g} for n = 6",
        "sec(pi/n)^n, Thron 1991",
    )
    put("secant6", f"{1 / math.cos(math.pi / 6) ** 6:.3g}", "sec(pi/6)^6")
    put("ad_set", f"{cf.AD['rR'] / cf.AD['rB']:.3f}", "circuit_figures.AD rR / rB")
    put("close_patterns", 2**3, "circuit_figures.check_close: 2^3 arrow patterns")

    from fold_census import read_time

    put("read_min", read_time(PAGE_TEXT[0])[2], "fold_census.read_time on the page (main read, 230 words a minute)")
    data = ROOT / "data" / "r31.tar.bz2"
    put(
        "release_mb",
        round(data.stat().st_size / 1e6) if data.exists() else "193 (data/ not present)",
        "data/r31.tar.bz2 size in MB (get_biomodels.sh)",
    )
    return v, src


# ------------------------------------------------------------------ the facts


@dataclass
class Fact:
    section: str
    text: str  # a format string over values()
    keys: tuple[str, ...]


def F(section: str, text: str) -> Fact:
    return Fact(section, text, tuple(re.findall(r"{(\w+)", text)))


FACTS = [
    # masthead lead
    F("top", "Count those loops in {models_670} published cell models"),
    F("top", "The table those counts make, above, has {rt_blank} blank squares."),
    F("top", "{nort} of {nort_total} found with no running total (top rows)"),
    F("top", "{rt} of {rt_total} found with one or more"),
    F("top", "{read_min} min read"),
    # 01
    F("close", "No exception in {auto} published models (chapter 03)"),
    # 02, the model figures
    F("circuits", "Between {sw_off} and {sw_on} the cell is on or off"),
    F("circuits", "In the model, {ck_delay} hours of delay make a {ck_period}-hour rhythm"),
    F("supplement", "which is {secant}"),
    F("supplement", "it needs {secant6}, has {rep_gain}"),
    F("circuits", "activity {ad_set} at set point"),
    # 03
    F(
        "table",
        "In {auto} models whose behaviour could be read, every switch has a self-feeding loop and every clock a brake, as a proved rule requires, and {ho_n} newer models broke neither rule",
    ),
    F(
        "table",
        "Gain called the behaviour of all {single} circuits made of a single loop, and of {ho_rings} newer ones.",
    ),
    F(
        "table",
        "Five models of the same fly clock, drawn at different detail, land at four addresses, and all of them tick.",
    ),
    F("table", "Ro{ro_models} element number"),
    # Figure 8, the pipeline's steps (svg#pf) and their cards
    F("table", "{census} curated models"),
    F("table", "{usable} read as equations {excluded} unusable"),
    F("table", "{complete} every loop listed {not_listed} hit step limit"),
    F("table", "{small} one to three loops"),
    F("table", "{run_alone} run on their own {not_own} not on their own"),
    F("table", "{auto} behaviour labelled {unlabelled} no label"),
    F("table", "{ho_listed} curated since 2017"),
    F("table", "{ho_read} read as equations {ho_unusable} unusable"),
    F("table", "{ho_run_alone} run on their own {ho_not_own} not on their own"),
    F("table", "the table {small} · {ho_small}"),
    F("table", "sign rules {auto} · {ho_n}"),
    F("table", "atlas {fp_filed} · {ho_filed}"),
    F("table", "address {ap_n} · {hap_n}"),
    F(
        "table",
        "{census} curated models. Downloaded BioModels release 31, the curated models of June 2017 ({release_mb} MB)",
    ),
    F("table", "{usable} read as equations. Read each model’s equations"),
    F("table", "{complete} every loop listed. Read each arrow’s sign"),
    F("table", "{small} one to three loops. Kept the models with one to three loops"),
    F("table", "Across the library, {loose_models} models have a loose running total and {paired} a paired one."),
    F("table", "{run_alone} run on their own. Simulated each readable model from twelve starting states."),
    F("table", "{forced} driven by an outside schedule were set aside, and {spent} ran out of work budget."),
    F("table", "{auto} behaviour labelled. Labelled what each run did"),
    F("table", "The other {unlabelled} never settled within 100,000 time units, or the solver failed."),
    F("table", "{ho_listed} curated since 2017. Listed and fetched"),
    F("table", "{ho_read} read as equations. Read with release 31’s pipeline"),
    F("table", "{ho_run_alone} run on their own. Ran each from twelve starting states"),
    F("table", "Test: the table, {small} · {ho_small}."),
    F("table", "Test: sign rules, {auto} · {ho_n}."),
    F("table", "Test: atlas, {fp_filed} · {ho_filed}."),
    F(
        "table",
        "Of {fp_read} readable answers in release 31, {fp_flat} barely moved; held out, {ho_flat} of {ho_atlas_read}.",
    ),
    F("table", "Test: address, {ap_n} · {hap_n}."),
    F(
        "table",
        "{excluded} could not be used: {delays} use built-in delays, {onoff} use on-off rules, {unset} have values the solver cannot set and {no_arrows} gave no arrows at the states read.",
    ),
    F("table", "For {unfinished} models the search reached its step limit."),
    # 03, what a clean record is worth (PR #1)
    F("supplement", "So when all {au_auto} models stay inside both fences"),
    F(
        "supplement",
        "after {cl_tails_word} in a row you start to believe them, because luck manages that about once in {tails_odds} tries",
    ),
    F(
        "supplement",
        "Of the {au_auto}, {sw_without} have no self-feeding loop, and if loops meant nothing, luck would hand those {sw_without} just {sw_expected} switches between them, with none at all {sw_half}.",
    ),
    F(
        "supplement",
        "{cl_without} have no brake, and luck would make them tick {cl_expected} times; none did, at odds of {cl_odds}, about {cl_tails} tails in a row.",
    ),
    F(
        "supplement",
        "{sw_with} of the {au_auto} carry a self-feeding loop and {sw_beh} switch, 1 in {sw_one_in}, while {cl_with} carry a brake and {cl_beh} tick, {cl_in_ten} in 10.",
    ),
    F(
        "supplement",
        "a self-feeding loop has {sw_recall} recall for switches and about {sw_prec} precision, and a brake has {cl_recall} recall for clocks and about {cl_prec}.",
    ),
    F(
        "supplement",
        "chapter 05’s atlas files each model by one answer and counts {fp_remembers} that remember and {fp_ticks} that tick",
    ),
    # 04
    F("hidden", "{rt_blank_word} of the {rt_total_word} running-total elements"),
    F("hidden", "and not read in any model by the census"),
    F("hidden", "These three the census did find, four models between them"),
    F("hidden", "rows one and two filled completely"),
    F(
        "hidden",
        "{robust} came back to within half a percent, {band} of them small circuits nobody had read as running totals",
    ),
    F("hidden", "A trace by hand split the four in half. {four_exact} come back exactly"),
    F("hidden", "Why would seventeen hide?"),
    F("hidden", "Row three is the open question, since {loose_blank3} of its 16 stay blank even read loosely."),
    F("hidden", "The first new batch, {ho_listed} models curated since 2017, filled none of them"),
    # 04, auditing the loose reading (PR #1)
    F("supplement", "Strictly, rows one to three hold {dial_strict} of {squares} elements."),
    F(
        "supplement",
        "Count every leak that reads as zero and the count reaches {dial_zero}, and still {dial_hundredth} with the dial at a hundredth; at a tenth, the cut used above, it is {dial_tenth}, and at one, {dial_one}.",
    ),
    F(
        "supplement",
        "Most of the new arrivals, {new_cells} of the {dial_added} elements that loosening adds, come in at zero leak",
    ),
    F(
        "supplement",
        "Those {new_cells} elements rest on {models_zero} models, {volt_word} of them membrane voltages in pancreatic and nerve cells, and {volt_alone} of the {new_cells} rest on voltages alone.",
    ),
    F("supplement", "{volt_all_osc}"),
    F("supplement", "all {readings_below} readings below one thin out smoothly toward zero"),
    F("supplement", "Off to one side sits a pile of {readings_zero} that read as zero"),
    # 05
    F("atlas", "ticks {fp_ticks} {wire_ticks} {ticks_brake} of {fp_ticks} have a brake"),
    F("atlas", "remembers {fp_remembers} {wire_remembers} {rem_selffeed} of {fp_remembers} have a self-feeding loop"),
    F("atlas", "returns exactly {fp_returns_exactly} {wire_returns_exactly}"),
    F("atlas", "returns partly {fp_returns_partly} {wire_returns_partly}"),
    F("atlas", "rings {fp_rings} {wire_rings}"),
    F("atlas", "follows {fp_follows} {wire_follows}"),
    F(
        "atlas",
        "Of the {fp_models} that run on their own and match a behaviour label, {fp_read} gave an answer that could be read, and {fp_filed} of those fill six rows.",
    ),
    F(
        "atlas",
        "Of the {fp_read}, {fp_flat} barely moved at all. The other {fp_filed}: {fp_ticks} tick, {fp_remembers} remember, {fp_returns_exactly} return exactly, {fp_returns_partly} return part way, {fp_rings} ring, {fp_follows} follow.",
    ),
    F("atlas", "the ticks row alone holds {wire_ticks} different loop addresses"),
    F("supplement", "lands in {tyson_row}"),
    F(
        "supplement",
        "its solver fails {yeast_min} minutes after the salt step, with Hog1 still {yeast_fold} times its starting level",
    ),
    F(
        "atlas",
        "all {ho_filed} newer models found a row, but {ho_follows} of them, {ho_over_half}, landed in follows, where release 31 had {r31_follows}",
    ),
    # 05, other numbers a table could use (PR #1)
    F("supplement", "chapter 03 found that what a circuit does survives redrawing in {fams_does} of {fams} families"),
    F("supplement", "{fams_moved_word} family in {fams_word} did change what it does when redrawn"),
    F("supplement", "Deficiency could be computed today for the {rep_n} census models that have reactions."),
    # 07
    F("question", "2026This census reads {usable} published cell models"),
    F("question", "test{auto} models; {ho_n} held out."),
    F(
        "question",
        "resultheldNo exception in {mem} switches and {clk} clocks; {ho_cands} held-out candidates fell to a hand check",
    ),
    F("question", "test{single} single rings; {ho_rings} held out."),
    F("question", "resultheld{single} of {single}; {ho_rings} of {ho_rings}."),
    F("question", "surpriseA {miss_year} fly clock ticks below its floor"),
    F("question", "test{ap_n} models; {hap_n} held out."),
    F(
        "question",
        "resultfailed{ap_address}% against the sign rules’ {ap_sign}%; held out, {hap_address}% against {hap_sign}%.",
    ),
    F("question", "test{small} small models; {ho_small} held out."),
    F("question", "Over half the new models land in follows ({r31_follows} in release 31)"),
    F("question", "test{fp_filed} models; {ho_filed} held out."),
    F("question", "resultfailed{ho_follows} of {ho_filed} follow: {ho_follows_pct}%."),
    F("question", "fail lineRows other than {electrons}."),
    F("question", "testThe count; {toy_draws} toy circuits; {mixed_models} models."),
    F("supplement", "lockThe {ho_listed} held-out models never reach the model."),
    F("supplement", "A model could read the {blind_n} follows traces blind"),
    F("question", "resultrejectedOrdering gives {ordered}."),
    F(
        "question",
        "surpriseAll {toy_clocks} toy clocks run the self-feeding loop fast; real models only lean that way, {transit}.",
    ),
    F(
        "supplement",
        "{squares} squares and an element zero.A census of {usable} curated models from BioModels, one 2017 release",
    ),
    F("supplement", "In {auto} models every switch has a self-feeding loop and every clock a brake."),
    F("supplement", "{rt_blank} of {squares} squares blank"),
    F("supplement", "Five drawings of one fly clock land at four addresses"),
    F(
        "supplement",
        "six answers over {fp_filed} models, is the more plausible table; {fp_follows} sit in a catch-all row",
    ),
    F("question", "five models of one fly clock land at four addresses"),
    F("question", "in {auto} models every switch has a self-feeding loop"),
    F(
        "question",
        "in {ap_n} models, and {hap_n} newer ones, the square called the answer no better than the two sign rules",
    ),
    F("question", "{rt_blank} of the {rt_total} running-total squares are blank"),
    F("question", "{ho_listed} newer models filled none"),
    F("question", "keep their square in {fams_sits} of {fams} families"),
    F("question", "No blank squares: {fp_filed} models fill six rows"),
    F("question", "which took half of {ho_filed} newer models"),
    F("question", "Redrawn models keep what they do in {fams_does} of {fams} families"),
    F("question", "Redrawn models keep what they do in {fams_does} of {fams} families."),
    # 08 and the ledger
    F("line", "ordering the loops would make rows of {ordered}, not {electrons}"),
    F(
        "line",
        "In {toy_draws} random circuits with one self-feeding loop and one brake, all {toy_clocks} that tick run the self-feeding loop fast",
    ),
    F("line", "{transit}, too close to rule out chance"),
    F("supplement", "two loops show {kinds2} kinds of behaviour against 9 elements, three loops {kinds3} against 16"),
    F("supplement", "one loop shows {kinds1} against its 4, or {coarse1} once behaviours are merged"),
    F(
        "supplement",
        "the same count ran on {ho_listed} newer models: {ho_kinds2} kinds against 9, {ho_kinds3} against 16",
    ),
    F("supplement", "as all {toy_clocks} toy clocks did"),
    F("supplement", "the census already holds {brake_fast_clocks} such models"),
    F("supplement", "remove the brakes of {dep_clocks} clocks"),
    F(
        "supplement",
        "It misses loops written as formulas ({no_arrows} models), and {unfinished} of its searches hit their step limit.",
    ),
    F("supplement", "all {close_patterns} arrow patterns checked"),
    F(
        "supplement",
        "no exception in {auto} census models, nor in {ho_n} newer ones, where {ho_cands_word} candidates fell to a hand check",
    ),
    F(
        "supplement",
        "The census agrees in all {single} rings single as drawn, {rings_hit} of {rings} counting rings the filters leave; no miss among {ho_rings} single rings in newer models",
    ),
    F(
        "supplement",
        "Redrawn models keep what they do in {fams_does} of {fams} families and their place in {fams_sits} of {fams}",
    ),
    F(
        "supplement",
        "{ap_address}% against {ap_sign}% in {ap_n} models, {hap_address}% against {hap_sign}% in {hap_n} newer ones; {ho_listed} newer models",
    ),
    F("supplement", "The atlas: {fp_read} of {fp_models} models read"),
    F("supplement", "up to {wire_max} wirings per answer"),
    F("supplement", "of {ho_filed} newer models filed, {ho_follows} land in the catch-all"),
    F(
        "supplement",
        "{robust} returns within 0.5% that survive redrawn rates, {robust_exact} of them exact to one part in a million",
    ),
    F("supplement", "Of the {band} in rows one to three, traced by hand, 2 are exact"),
    F("supplement", "(all {toy_clocks} clocks)"),
    F(
        "supplement",
        "a strong check for clocks ({cl_expected} expected by chance among the models with no brake, none seen) and a weak one for switches ({sw_expected} expected); run backwards, {sw_beh} of {sw_with} self-feeding models switch and {cl_beh} of {cl_with} with a brake tick",
    ),
    F(
        "supplement",
        "Against it: the loose reading’s fill at zero rests on {models_zero} models, {volt_half} of them oscillating voltages read at one moment",
    ),
    F("supplement", "{transit}, not significant"),
    # supplements
    F("supplement", "{rep_species} molecules (three RNAs and three proteins) and {rep_reactions} reactions."),
    F("supplement", "It ticks from all {rep_ticks_all} starts."),
    F(
        "supplement",
        "Baudier, Fages and Soliman found no brake in {r24_nobrake} of models; this census finds none in {rep_nobrake}.",
    ),
    F(
        "supplement",
        "{le3} of {usable} have three loops or fewer; for {unfinished} the search stopped at its step limit.",
    ),
    F("supplement", "The only models inside them are the {dep_clocks} dashed clocks"),
    F(
        "supplement",
        "one loop gives {kinds1} kinds, two loops {kinds2} and three loops {kinds3}; merged into four behaviours, {coarse1}, {coarse2} and {coarse3}.",
    ),
    F("supplement", "The paired running-total reading finds six models with a total kept by two molecules"),
    F(
        "supplement",
        "{usable} models could be read this way. Of the other {excluded}, {delays} use built-in delays, {onoff} use on-off rules, {unset} have values the solver cannot set and {no_arrows} gave no arrows at the states read",
    ),
    F("supplement", "It gives {random2} of 9 elements at two loops and {random3} of 16 at three"),
    F("supplement", "{loops_counted}"),
    F("supplement", "It differs from c in {nu_differs} of the {small} small models."),
    F("supplement", "it differs from k in {kpf_differs} of the {small}."),
    F("supplement", "{pair_unchecked} candidates whose rate laws use conditional formulas could not be confirmed"),
    F("supplement", "yeast osmoregulation, has one (Schaber 2012) {schaber_loops}"),
    F("supplement", "yeast osmoadaptation, has one (Petelenz-Kurdziel 2013) {petelenz_loops}"),
    F("supplement", "set aside ({forced} models)"),
    F("supplement", "{run_alone} models run on their own; {unsettled} small models never settle under these rules."),
    F("supplement", "of which the models fill {types4_2} at two loops and {types4_3} at three"),
    F("supplement", "three types give 3, 6 and 10 elements, of which they fill {types3_2} and {types3_3}"),
    F("supplement", "moves {split_moved} models to another cell"),
    F("supplement", "This census: {rep_n} models with reactions"),
    F(
        "supplement",
        "No brake {r24_nobrake} {rep_nobrake} No self-feeding loop {r24_nopos} {rep_nopos} No self-feeding loop after the filters {r24_norefined} {rep_norefined}",
    ),
    F("supplement", "{erk_loops} loops survive the filters, all braking"),
    F(
        "supplement",
        "Of the {run_alone} models that run on their own, the {auto} that match a behaviour label were checked against both rules",
    ),
    F(
        "supplement",
        "The {mem} that hold two states all have a self-feeding loop; the {clk} that tick all have a brake.",
    ),
    F("supplement", "On the {single} that are single rings before and after, the floor calls all {single}"),
    F(
        "supplement",
        "Gardner’s toggle has gain {toggle_tip} at its tipping point and {toggle_rest} at its two stable states.",
    ),
    F("supplement", "{exact} of {settling} models show one."),
    F("supplement", "{robust} models are robust, {band} of them in rows one to three: {band_list}."),
]

# Known slips: a number that is right next to a label that is wrong. Each pattern must never match again.
SLIPS = [
    (
        "atlas",
        r"Of (the )?392 models that run on their own(?! and match a behaviour label)",
        "392 is the models that run on their own AND match a behaviour label (fingerprints.json scans 392); 432 run on their own (Supplement B, D, E)",
        "Of the 392 models that run on their own and match a behaviour label, 302 gave an answer that could be read.",
    ),
    (
        "atlas",
        r"built from every published model that runs on its own(?! and matches a behaviour label)",
        "the atlas pushes the 392 labelled models, not all 432 that run on their own",
        "The atlas, built from every published model that runs on its own and matches a behaviour label:",
    ),
]

# Numbers on the page that the checker does not recompute, with where each comes from.
TRACED_ELSEWHERE = [
    (
        "top, the hook table's tiles",
        "element counts per square (Sw 45, Tk 22, Me 14, Ro 39, Cp 9, Mm 4, Wm 9, Mx 20, Ps 9, Ro∫ 2, Ro∫² 1, Mx∫ 1)",
        "build_post.fig_table from tables_traj.json rows.essay.cells; folded by fold_census.py (gen:ptable)",
    ),
    (
        "table, Figure 8 explorer",
        "per-model rows of the search box",
        "build_post.build from r31_structure_traj.jsonl and r31_dynamics.jsonl (gen:data)",
    ),
    ("hidden, Figure 10", "the blank band grids", "circuit_figures.fig_band from tables_traj.json (gen:band)"),
    (
        "circuits, Figures 2 to 4",
        "readouts lactose in 2.32, LacY 4.65, PER:CRY 0.05, methyl 2.0; sliders 0.50, 9.0 h, 5.0",
        "circuit_figures.fig_switch / fig_clock / fig_adapter (model run or settings SW, CK, AD; PER:CRY 0.05 and methyl 2.0 are literals at circuit_figures.py fig_clock, fig_adapter)",
    ),
    (
        "supplement, Figure S13",
        "answer key: five of seven",
        "build_post.fig_answer_key from r31_structure_traj.jsonl (TEXTBOOK)",
    ),
    (
        "supplement C",
        "the fly clock's loop counts (one, two, two each, 14)",
        "build_post.build fly_txt from r31_structure_traj.jsonl (asserted)",
    ),
    (
        "supplement C",
        "the 10 dashed clocks: seven calcium, two sugar-burning, one enzyme",
        "build_post.DEPLETION_KIND, asserted against tables_traj.json",
    ),
    (
        "supplement D",
        "running-total check table: Tyson 1991 2, Tyson 2003 0, Bray thousands",
        "build_post.build ctl_rows from tables_traj.json controls",
    ),
    (
        "supplement D",
        "settings: h 0.1%, 1e-13, t = 0, 1, 10, 100, 1000, 1e-6, x1000, rank 1e-4, ratio 12, 1e-9, CVODE 1e-8 / 1e-12, horizons, thresholds",
        "constants in analysis/loops.py, integrators.py, dynamics.py; quoted in build_post.py prose",
    ),
    (
        "supplement D",
        "5,000,000 steps, 20,000 loops, 300,000 arcs; solver work budgets; 6-hour safety net",
        "loops.py and elim.py budgets; WORK_BUDGET in dynamics.py, truth_tests.py, fingerprints.py, robust_return.py; "
        "budget.SAFETY_NET_S",
    ),
    (
        "supplement D",
        "SHA-256 b6fba03e…0532; Python 3.9.6 and package versions",
        "analysis/get_biomodels.sh SHA; requirements.txt",
    ),
    (
        "supplement D",
        "about two hours with 8 jobs on a 10-core laptop",
        "build_post.build runtime literal; measured runs in README (Reproduce)",
    ),
    (
        "supplement E",
        "gain table, families table, the three single-after-filter rings",
        "fold_census.truth_supp from truth_tests.json (gen:truth)",
    ),
    (
        "supplement B",
        "42 of 106 rate-rule models, 179 to 175",
        "history: the audit of the first full run (git log), not recomputed",
    ),
    ("line, ledger", "73 scored squares of 75", "counts of Figure 15's own squares"),
]


PAGE_TEXT = [""]  # the page's HTML, set in main() for values that read the page itself


def fill(fact: Fact, v: dict[str, object]) -> str:
    return fact.text.format(**{k: v[k] for k in fact.keys})


def page_says(expected: str, text: str) -> str:
    """The page's version of a phrase whose numbers differ: the phrase with each number made a wildcard."""
    pattern = re.escape(expected)
    pattern = re.sub(r"\d[\d,.]*", r"[\\w,.%]+?", pattern)
    m = re.search(pattern, text)
    return m.group(0) if m else "phrase not found"


SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“(])")
CITE = re.compile(r"\[[\d,–\s]+\]")
NOISE = re.compile(
    r"\[[\d,–\s]+\]|Figure S?\d+|chapters? \d+(?: to \d+)?|Supplement [A-E]|\b0[1-9](?=[a-z\s]|$)|ref(?:erence)?s? \d+|p53|Hog1|release 31|\bk = \d|elements? \d+(?:, \d+)*(?: and \d+)?"
)
NUMBER = re.compile(r"\d")

# Sentences with a number that is neither computed nor cited in the same paragraph, each read by hand.
HAND = {
    "left to right1proved": "label: Figure 14's evidence key, its four steps numbered 1 to 4",
    "from its first idea to 2026": "date: the timeline of Figure S5 ends in the year of writing",
    "Mendeleev left blank squares": "history: Mendeleev 1869 and gallium 1875, cited [38] in the next sentence",
    "density about 6": "history: eka-aluminium density 6.0, gallium 4.7 then 5.9 (HANDOFF, LibreTexts and Wikipedia, secondary)",
    "Gallium's discoverer weighed it": "history: as above",
    "Guessed by René Thomas in 1981": "history: the rule box cites [4, 58, 59] and [3] in the next sentences",
    "Primo Levi named all 21 chapters": "history: Levi's The Periodic Table has 21 element chapters (HANDOFF, Wikipedia and EBSCO, secondary)",
    "One loop gives 2 × 2 = 4 elements": "definition: (n + 1)^2 elements in row n",
    "row sizes, 4, 9 and 16": "definition and arithmetic: (n + 1)^2 = sum of 2l + 1",
    "layers of 1, 3, 5 and 7": "arithmetic",
    "4, 9 and 16 elements": "definition",
    "hold 4, 9 and 16 squares": "definition: (n + 1)^2 squares in the row of n loops",
    "the rows grow to 4, 10 and 20": "arithmetic: multisets of n loops from four loop types (Supplement D)",
    "The one miss is a 1995 fly clock": "fact: Goldbeter 1995, the gain table's miss (gen:truth)",
    "A p53 model totals all of its Mdm2": "trace_four.json BIOMD0000000159 (the total found by hand)",
    "up 20% and hold": "setting: fingerprints.json settings.step 0.2",
    "raised by 20%": "setting: truth_tests.json settings.step 0.2",
    "follow it 12%": "slider readout (Figure S7)",
    "release 31 from 2017": "BioModels release 31, 26 June 2017 (get_biomodels.sh)",
    "73 scored squares of 75": "count of Figure 15's squares",
    "every source opened on 10 November 2026": "date of the reading (HANDOFF section 4, the question chapter)",
    "Every row was opened on 10 November 2026": "date of the reading",
    "secant condition": "theorem statement, cited in Supplement E [70, 71]",
    "(n+1)² elements": "definition",
    "every 9 to 11 years": "cited in Figure S3's caption [76]",
    "in element 3": "definition: element 3 is Ad",
    "Atom2Vec recovered": "cited [118] in chapter 07",
    "p53 restoration reversed": "cited [18, 19] in chapter 06",
    "p53 pulses, slower amyloid": "cited [63 to 66, 147, 148] in chapter 06",
    "a tenth of a percent": "setting: loops.py central difference h = 1e-3 x",
    "st > 0": "code line (loops.py)",
    "spread_starts": "code line (dynamics.py)",
    "a0_tr + a_tr": "rate law of BIOMD0000000012",
    "42 of 106 rate-rule models": "history: the first full run's audit, not recomputed (git log of analysis/loops.py)",
    "(6 of 16)": "tables_traj.json rows[3].distinct_autonomous_behaviours = 6",
    "One loop shows more than its 4": "tables_traj.json rows[1]: 6 kinds, 4 coarse",
    "Goldbeter’s 1995 model has one loop": "build_post.build fly_txt from r31_structure_traj.jsonl (asserted)",
    "could be read this way": "fact: usable 613 (see Supplement D row)",
    "Of the other 27": "fact: see Supplement D row",
    "10−13": "setting: loops.py",
    "t = 0, 1, 10, 100 and 1000": "setting: loops.py sign states",
    "10−6 of the median": "setting: loops.py",
    "to t = 1000": "setting: loops.py random states",
    "pTN = 0": "definition",
    "5,000,000 steps": "setting: loops.py step budget",
    "scores exactly 1": "definition: first-order decay",
    "10−4 of the largest": "setting: integrators.py",
    "has one (Tyson 1991)": "control label (build_post.build ctl_rows)",
    "has none (Tyson 2003)": "control label",
    "has none (Bray 1995)": "control label",
    "has none (Bray 1993)": "control label",
    "ten times the largest": "setting: dynamics.py",
    "horizons of 102": "setting: dynamics.py horizons 1e2 to 1e5, 2001 samples",
    "10−5 of its level": "setting: dynamics.py",
    "10−3 of it": "setting: dynamics.py",
    "relative swing above 10−3": "setting: dynamics.py",
    "more than 1% apart": "setting: dynamics.py",
    "106 times its starting": "setting: dynamics.py",
    "row ν has (ν + 1)2": "definition",
    "layers of 2l + 1": "definition",
    "Table 1: 506 models": "cited [24], asserted in build_post.build (r24 models == 506)",
    "160 of 506": "cited [24]",
    "193 MB, SHA-256": "get_biomodels.sh SHA; size from data/r31.tar.bz2 (see the 193 MB fact)",
    "Python 3.9.6": "requirements.txt and the run's interpreter",
    "per model; elimination capped": "settings: loops.py and elim.py budgets",
    "counted in derivative evaluations": "settings: WORK_BUDGET in dynamics.py, truth_tests.py, fingerprints.py and "
    "robust_return.py; budget.SAFETY_NET_S",
    "OMP_NUM_THREADS=1": "setting: run_all.sh",
    "about two hours with 8 jobs": "runtime: see README Reproduce for measured runs",
    "with five loops before filtering": "r31_structure_traj.jsonl McClean2007 defs.thomas.c (literal in fold_census.truth_supp)",
    "Tyson 1991 cell cycle, 6 and 2 variables": "family label (truth_tests.json families)",
    "Borghans 1997 calcium": "family label",
    "Singh 2006 TCA": "family label",
    "2 are exact": "trace_four.json (see the ledger fact)",
    "BioModels release 31 (26 June 2017)": "get_biomodels.sh",
    "November 2026": "masthead date",
    "p is 0.05 or more, the lead over the sign rules is under 5 points": "fail line frozen 2026-11-16 in analysis/address_predicts.py (PROTOCOL; fails keys a_p_at_least_0.05, b_lead_over_sign_under_5_points)",
    "double to 2n²": "arithmetic: chemistry's rows 2, 8, 18, 32",
    "Every fail line was written before the held-out models": "process: fail lines frozen 2026-11-16 in proto/tests.html and the docstrings of holdout_score.py and address_predicts.py, before the hold-out census ran (proto/PROGRESS.md)",
    "release 31only after 01 and 02": "stage label of the search plan (Figure S6)",
    "fragment 103": "the epigraph: Heraclitus, fragment B103 (HANDOFF voice pass, translations)",
    "CC0": "licence of the open-data source (its own terms page, linked in the table)",
    "CC BY 4.0": "licence of the open-data source",
    "GSE92742": "GEO accession of the open-data source",
    "crystals230 space groups": "row label of Figure 15; cited [93] in its cards",
}


def classify(sentence: str, block: Block, expected: list[str], row_cites: set[int]) -> str:
    """fact, generated, cited, label, a hand note, or unclassified."""
    if any(
        e in sentence or sentence in e or (len(sentence) > 40 and sentence[:40] in e) or e[:40] in sentence
        for e in expected
    ):
        return "fact"
    note = next((n for k, n in HAND.items() if k in sentence), None)
    if note:
        return "read by hand: " + note
    if block.gen:
        return f"generated ({block.gen})"
    if block.label:
        return "label"
    if CITE.search(sentence) or CITE.search(block.text):
        return "cited"
    if block.row in row_cites:
        return "cited (same table row)"
    return "unclassified"


def inventory(blocks: list[Block], expected: list[str]) -> list[tuple[str, str, str]]:
    """Every sentence with a number, outside the references, as (section/kind, class, sentence)."""
    row_cites = {b.row for b in blocks if b.row and CITE.search(b.text)}
    out = []
    for b in blocks:
        if b.section == "refs":
            continue
        for s in SENT.split(b.text):
            if NUMBER.search(NOISE.sub("", s)):
                out.append((f"{b.section}/{b.kind}", classify(s, b, expected, row_cites), s))
    return out


def read_budget_rows(read_min: int) -> list[str]:
    """One trace row per read budget: words, minutes, target and how far off; the first must equal the masthead."""
    import read_budgets

    names = ("main read, folds closed", "chapters, folds open", "all, supplement open")
    rows = []
    for k, ((words, mins), name, target) in enumerate(
        zip(read_budgets.tiers(PAGE_TEXT[0]), names, read_budgets.TARGETS)
    ):
        off = "within" if mins <= target else f"{mins - target} min over"
        agrees = "" if k else (f"yes, {read_min} min" if mins == read_min else f"**NO** masthead {read_min} min")
        rows.append(f"| {name} | {words:,} | {mins} | {target} | {off} | {agrees} |")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page", type=pathlib.Path, default=ROOT / "every-line-is-a-loop.html")
    ap.add_argument("--out", type=pathlib.Path, default=RESULTS / "fact_trace.md")
    args = ap.parse_args()
    PAGE_TEXT[0] = args.page.read_text(encoding="utf-8")
    blocks = page_blocks(args.page)
    section_text: dict[str, str] = {}
    for b in blocks:
        section_text[b.section] = section_text.get(b.section, "") + " " + b.text
    v, src = values()

    rows, bad, expected = [], 0, []
    for fact in FACTS:
        text = fill(fact, v)
        expected.append(text)
        hay = section_text.get(fact.section, "")
        ok = text in hay
        kind = next((b.kind for b in blocks if b.section == fact.section and text[:30] in b.text), "?")
        sources = "; ".join(dict.fromkeys(src[k] for k in fact.keys)) or "words on the page (no computed value)"
        note = "" if ok else f"page says: “{page_says(text, hay)}”"
        bad += not ok
        rows.append(
            f"| {text.replace('|', '/')} | {fact.section}/{kind} | {sources.replace('|', '/')} | {'yes' if ok else '**NO** ' + note} |"
        )

    slips = []
    for section, pattern, why, fix in SLIPS:
        if re.search(pattern, section_text.get(section, "")):
            bad += 1
            slips.append(f"| {section} | “{pattern}” | {why} | {fix} |")

    budgets = read_budget_rows(v["read_min"])
    bad += sum(1 for r in budgets if "**NO**" in r)

    inv = inventory(blocks, expected)
    counts = Counter(c.split(":")[0].split(" (")[0] for _, c, _ in inv)
    lines = [
        "# Fact trace: every-line-is-a-loop.html",
        "",
        f"Generated by `tools/check_facts.py` from `{args.page.name}` and `results/`. {len(FACTS)} facts, {len(FACTS) - (bad - len(slips))} match; {len(slips)} known slips present.",
        "",
        "## Facts computed from results",
        "",
        "| the page should say | where (section/kind) | source | match |",
        "|---|---|---|---|",
        *rows,
        "",
        "## Known slips (a right number with a wrong label)",
        "",
        "| where | pattern | why it is wrong | fix |",
        "|---|---|---|---|",
        *(slips or ["| none | | | |"]),
        "",
        "## Read time",
        "",
        "Counted by `analysis/read_budgets.py` (fold_census.count_words at fold_census.WPM words a minute), the three "
        "budgets Kat set: the main read with folds closed, the chapters with folds open, and everything but the "
        "references. Over a target is reported here, not failed; the masthead must show the first.",
        "",
        "| read | words | minutes | target | against target | masthead agrees |",
        "|---|---|---|---|---|---|",
        *budgets,
        "",
        "## Numbers traced to code, not recomputed here",
        "",
        "| where | numbers | source |",
        "|---|---|---|",
        *(f"| {a} | {b} | {c} |" for a, b, c in TRACED_ELSEWHERE),
        "",
        "## Every sentence with a number, outside the references",
        "",
        "Classes: " + ", ".join(f"{n} {c}" for c, n in counts.most_common()) + ".",
        "",
        "fact: one of the facts above. read by hand: the note says where the number comes from. generated: written by the named gen: block from results (build_post.py, fold_census.py, circuit_figures.py), each with its own asserts. label: a heading, control or readout. cited: the paragraph carries a reference marker; checked against its source when it was cited (HANDOFF.md section 5), not reopened here. unclassified: none of these; each is a gap to close.",
        "",
        "| where | class | sentence |",
        "|---|---|---|",
        *(f"| {w} | {c} | {s.replace('|', '/')} |" for w, c, s in inv),
        "",
    ]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"{len(FACTS)} facts, {bad - len(slips)} missing; {len(slips)} known slips; {counts['unclassified']} unclassified sentences -> {args.out}"
    )
    for r in rows:
        if "**NO**" in r:
            print(r)
    for s in slips:
        print(s)
    for r in budgets:
        print(r)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
