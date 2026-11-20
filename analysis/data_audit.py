"""Audit the data behind the census: funnel, imbalance, duplicates, hold-out leakage, grouped recounts, assumptions.

Reads   data/r31_curated/*.xml and data/holdout_curated/*.xml (model-level annotation and the math, through libSBML);
        data/r31.tar.bz2 (checksum against analysis/get_biomodels.sh); results/r31_structure_traj.jsonl,
        r31_dynamics.jsonl, r31_integrators.jsonl, list_ok.txt, fingerprints.json, tables_traj.json, truth_tests.json,
        address_predicts.json, nesting.json, holdout_ids.json, holdout_manifest.json, holdout_structure_traj.jsonl,
        holdout_dynamics.jsonl, holdout_integrators.jsonl, holdout_fingerprints.json, holdout_tables_traj.json,
        holdout_truth_tests.json, holdout_address_predicts.json, holdout_score.json, holdout_handcheck.json;
        git history (git log -S) for when each choice entered the code.
Writes  results/data_audit.json (every count, with the file and key it was read from) and results/DATASHEET.md
        (the datasheet, its numbers filled from the same audit).
Run     .venv/bin/python analysis/data_audit.py [--jobs 8]      4 to 15 minutes by machine load; seeded, deterministic

Every count here is computed from the files above. Nothing in results/ or analysis/ is modified. The address test's
own functions (analysis/address_predicts.py: load, run, loo_accuracy, size_bins) are imported unchanged, and the
original numbers are reproduced first as a pin before any grouped recount is trusted.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import random
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Iterable, Sequence
from multiprocessing import Pool
from typing import Any, Callable

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / 'results'
sys.path.insert(0, str(ROOT / 'analysis'))
import address_predicts as AP  # noqa: E402  the address test's own code, reused unchanged

OUT_JSON = RES / 'data_audit.json'
OUT_SHEET = RES / 'DATASHEET.md'
FOLDERS = {'r31': ROOT / 'data' / 'r31_curated', 'holdout': ROOT / 'data' / 'holdout_curated'}
PREFIX = {'r31': 'r31_', 'holdout': 'holdout_'}  # results file prefix per set (atlas and tests drop it for r31)

# Biological system, read from the model name (and SBML id): first pattern that matches wins. A keyword map, so it
# misfiles some models; it is shown here and in the output so a reader can judge it.
SYSTEMS: list[tuple[str, str]] = [
    ('p53', r'\bp53\b|mdm2'),
    ('NF-kB', r'nf ?-?k(appa)? ?-?b\b|nfkb|i ?-?kappa|\bikk|\bikb'),
    ('circadian clock', r'circadian|circ clock|\bclock\b|\bkai[abc]?\b|\bfrq\b|diurnal|\bper\d?\b|\bprr\d'),
    (
        'cell cycle',
        r'cell ?cycle|mitot|mitosis|min mit|\bcdk|\bcdc\d|cyclin|\bmpf\b|g1 s\b|g2 m\b|checkpoint|spindle|'
        r'\be2f|\brb\b|quiescen',
    ),
    ('calcium', r'calcium|\bca2\+|\bca\b|cicr|\bip3'),
    ('glycolysis', r'glycoly|\bpfk|phosphofructo'),
    ('MAPK and growth factors', r'mapk|\berk\b|\bras\b|\braf\b|\bmek\b|egf|ngf|erb ?b|kinase cascade'),
    ('apoptosis', r'apopto|caspase|\bbcl'),
    (
        'ageing, amyloid and DNA damage',
        r'amyloid|alzheimer|chaperon|proteostas|ageing|aging|telomer|senescen|dna damage|'
        r'parkinson|prion|huntingt',
    ),
    (
        'infection and epidemics',
        r'\bsir\b|seir|epidem|covid|sars|influenza|\bflu\b|malaria|\bhiv|virus|viral|hepatitis|'
        r'infect|transmission|ebola|zika|dengue|tubercul|vaccin|pathogen|bacteri|salmonella|incidence|prophage',
    ),
    ('immune', r'immun|t ?cell|\bth\d|macrophage|cytokine|interleukin|\bil ?\d|interferon|antibod|lymph|inflamm|wbc'),
    (
        'cancer',
        r'tumou?r|cancer|oncolytic|chemotherap|carcinoma|glioma|leuka?emi|\baml\b|metasta|melanoma|oligodendro|'
        r'virotherap',
    ),
    (
        'neurons and membranes',
        r'neuron|neural|axon|action potential|hodgkin|huxley|morris|lecar|synap|epsp|bursting|'
        r'membrane potential|channel|dopamin|purkinje|thalam|cortic|nerve|arousal|sleep|phototransduction|tufted',
    ),
    ('heart and muscle', r'cardiac|heart|ventric|atrial|myocyte|sarcomere|muscle'),
    ('blood clotting and complement', r'thrombin|coagul|fibrin|tfpi|complement|platelet|\bclot'),
    (
        'hormones and physiology',
        r'hormon|insulin|glucagon|thyroid|cortisol|oestrogen|estrogen|estrous|testosteron|'
        r'hypothalam|pituitar|menstrual|ovar|follic|gnrh|\bpth\b|bone|osteo|cartilage|kidney|renal|liver|blood|potassium|'
        r'iron|beta cell|diabet|pancrea|bicarbonate|melatonin|calcemia',
    ),
    (
        'metabolism',
        r'metabol|\btca\b|citric|krebs|amino acid|purine|pyrimidine|folate|fatty acid|lipid|cholesterol|'
        r'glucose|glycogen|photosynth|calvin|ru bis co|rubisco|nitrogen|sugar|sucrose|ethanol|lactate|mitochond|respirat|'
        r'\batp\b|threonine|glycerol|adenylate|trehalose|methionine|pentose|creatine|arginine|glutamate|arachidon|'
        r'peroxidase|phosphotransferase|carbohydrate|monosaccharide',
    ),
    (
        'other signalling',
        r'signal|receptor|gpcr|\bjak|\bstat\d?\b|tgf|smad|wnt|notch|hedgehog|camp|\bpka\b|\bpkc\b|'
        r'integrin|chemotaxis|osmo|hog1|tnf|toll|auxin|g ?protein|gtpase|\brho\b|\brgs\b|mtor|pheromone|\bepo|calmodulin|'
        r'nitric oxide|\bnos\b|shear stress',
    ),
    (
        'gene circuits and development',
        r'repressilator|toggle|operon|\blac\b|transcription|translation|\bmrna|micro ?rna|'
        r'\bmi ?r\d|gene regulat|gene network|feed ?forward|switch|oscillat|genetic|segment polarity|lineage|'
        r'differentiat|development|meiotic',
    ),
    (
        'pharmacology and toxicology',
        r'pharmaco|\bpk\b|pkpd|pbpk|\bdrug|\bdose|metformin|antibiotic|toxic|caffeine|'
        r'vicodin|opioid|inhibitor',
    ),
    ('ecology and populations', r'predator|prey|population|lotka|volterra|ecolog'),
]

# NCBI Taxonomy ids seen in the files, grouped for the organism count. Names are from memory of NCBI Taxonomy, not
# fetched (unverified); the ids themselves are what each file declares under bqbiol:hasTaxon.
TAXA: dict[str, tuple[str, str]] = {
    '9606': ('Homo sapiens', 'human'),
    '10090': ('Mus musculus', 'mouse and rat'),
    '10116': ('Rattus norvegicus', 'mouse and rat'),
    '10114': ('Rattus', 'mouse and rat'),
    '4932': ('Saccharomyces cerevisiae', 'yeast'),
    '559292': ('Saccharomyces cerevisiae S288C', 'yeast'),
    '4896': ('Schizosaccharomyces pombe', 'yeast'),
    '562': ('Escherichia coli', 'bacteria'),
    '83333': ('Escherichia coli K-12', 'bacteria'),
    '1423': ('Bacillus subtilis', 'bacteria'),
    '1773': ('Mycobacterium tuberculosis', 'bacteria'),
    '7227': ('Drosophila melanogaster', 'fly'),
    '8355': ('Xenopus laevis', 'frog'),
    '3702': ('Arabidopsis thaliana', 'plant'),
    '3701': ('Arabidopsis', 'plant'),
    '33090': ('Viridiplantae', 'plant'),
    '5141': ('Neurospora crassa', 'other fungus'),
    '2697049': ('SARS-CoV-2', 'virus'),
    '11676': ('HIV-1', 'virus'),
    '9913': ('Bos taurus', 'other mammal'),
    '10141': ('Cavia porcellus', 'other mammal'),
    '9615': ('Canis lupus familiaris', 'other mammal'),
    '131567': ('cellular organisms', 'broad clade only'),
    '2759': ('Eukaryota', 'broad clade only'),
    '33208': ('Metazoa', 'broad clade only'),
    '7711': ('Chordata', 'broad clade only'),
    '7742': ('Vertebrata', 'broad clade only'),
    '40674': ('Mammalia', 'broad clade only'),
}

VERSION_TOKEN = re.compile(
    r'\b(?:model|version|ver|variant|scenario|case|fig(?:ure)?|part|v)\s*[_\-.]?\s*(?:\d+[a-z]?|[ivx]{1,4}|[a-d])\b'
    r'|/\d+\b|[_\-]v?\d+$|\bmodel\s*[a-d]\b',
    re.I,
)
AUTHOR_YEAR = re.compile(
    r"^\s*([A-Za-zÀ-ɏ][A-Za-zÀ-ɏ'\- _&.]{0,40}?)\s*(?:et\.?\s*al\.?)?\s*[_ ]?((?:18|19|20)\d{2})(?!\d)"
)
N_SHUFFLES = AP.N_SHUFFLES  # 10,000, the address test's own count
SEED = AP.SEED + 1  # the amended runs of address_predicts.py draw from Random(SEED + 1) first; reused so p reproduces


# ---------------------------------------------------------------- small helpers
def jl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.open() if line.strip()]


def jd(path: pathlib.Path) -> Any:
    return json.loads(path.read_text())


def counter(values: Iterable[Any]) -> dict[str, int]:
    """Counts, most common first (ties by name), keys as strings."""
    c = collections.Counter(str(v) for v in values)
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def spread(values: Iterable[Any]) -> dict[str, Any]:
    """Counts plus how concentrated they are: top share and the effective number (1 / sum of squared shares)."""
    c = counter(values)
    n = sum(c.values())
    if not n:
        return {'n': 0, 'counts': {}}
    p = np.array(list(c.values()), float) / n
    top = next(iter(c))
    return {
        'n': n,
        'distinct': len(c),
        'top': top,
        'top_share': round(c[top] / n, 4),
        'effective_number': round(float(1 / np.sum(p**2)), 2),
        'counts': c,
    }


def tvd(a: dict[str, int], b: dict[str, int]) -> float:
    """Total variation distance between two count tables (0 = same mix, 1 = no overlap)."""
    na, nb = sum(a.values()), sum(b.values())
    keys = set(a) | set(b)
    return round(0.5 * sum(abs(a.get(k, 0) / na - b.get(k, 0) / nb) for k in keys), 4) if na and nb else float('nan')


def quartiles(values: Sequence[float]) -> dict[str, float]:
    v = np.array([x for x in values if x is not None], float)
    if not len(v):
        return {'n': 0}
    q = np.percentile(v, [25, 50, 75])
    return {'n': int(len(v)), 'q1': float(q[0]), 'median': float(q[1]), 'q3': float(q[2]), 'max': float(v.max())}


def share(k: int, n: int) -> float | None:
    return round(k / n, 4) if n else None


def fisher_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for the table [[a, b], [c, d]] (alternative: a is large), as scipy's 'greater'."""
    r1, c1, n = a + b, a + c, a + b + c + d
    total = math.comb(n, c1)
    return sum(math.comb(r1, x) * math.comb(n - r1, c1 - x) for x in range(a, min(r1, c1) + 1)) / total


class Groups:
    """Union-find over model ids; a group is named by its lowest id."""

    def __init__(self, ids: Iterable[str]) -> None:
        self.parent = {m: m for m in ids}

    def find(self, m: str) -> str:
        while self.parent[m] != m:
            self.parent[m] = self.parent[self.parent[m]]
            m = self.parent[m]
        return m

    def join(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo

    def label(self) -> dict[str, str]:
        roots = {m: self.find(m) for m in self.parent}
        low: dict[str, str] = {}
        for m, r in roots.items():
            low[r] = min(low.get(r, m), m)
        return {m: low[r] for m, r in roots.items()}


def members(label: dict[str, str], scope: Iterable[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    for m in sorted(scope):
        out[label[m]].append(m)
    return dict(out)


def one_per_group(label: dict[str, str], scope: Iterable[str]) -> list[str]:
    """The lowest model id of each group inside the scope."""
    return sorted(v[0] for v in members(label, scope).values())


# ---------------------------------------------------------------- reading the SBML files
def resource(uri: str) -> tuple[str, str]:
    """('pubmed', '8983160'), ('doi', '10.1063/1.4825874'), ('biomodels.db', 'BIOMD0000000003'), ('taxonomy', '9606')."""
    u = uri.strip()
    u = re.sub(r'^https?://(www\.)?ncbi\.nlm\.nih\.gov/pubmed/', 'pubmed/', u)
    u = re.sub(r'^https?://(dx\.)?doi\.org/', 'doi/', u)
    u = re.sub(r'^https?://arxiv\.org/(abs|pdf)/', 'arxiv/', u)
    u = re.sub(r'^https?://identifiers\.org/', '', u)
    u = re.sub(r'^urn:miriam:', '', u)
    m = re.match(r'^([A-Za-z.]+)[/:](.+)$', u)
    if not m:
        return 'other', u
    ns, val = m.group(1).lower(), urllib.parse.unquote(m.group(2)).strip()
    ns = {'obo.go': 'go'}.get(ns, ns)
    if ns == 'doi':
        val = val.lower()
    if ns == 'taxonomy':
        val = val.split(':')[-1]
    return ns, val


def cv_terms(sb: Any) -> list[tuple[str, str]]:
    import libsbml

    out = []
    for i in range(sb.getNumCVTerms()):
        t = sb.getCVTerm(i)
        if t.getQualifierType() == libsbml.MODEL_QUALIFIER:
            q = 'bqmodel:' + str(libsbml.ModelQualifierType_toString(t.getModelQualifierType()))
        else:
            q = 'bqbiol:' + str(libsbml.BiolQualifierType_toString(t.getBiologicalQualifierType()))
        out += [(q, t.getResourceURI(j)) for j in range(t.getNumResources())]
    return out


def renamed_formula(ast: Any, names: dict[str, str]) -> str:
    """The formula with every id replaced by its role and declaration index (S0, P3, R2.L0), time as 'time'."""
    import libsbml

    if ast is None:
        return ''
    a = ast.deepCopy()
    stack = [a]
    while stack:
        n = stack.pop()
        t = n.getType()
        if t == libsbml.AST_NAME_TIME:
            n.setName('time')
        elif t == libsbml.AST_NAME_AVOGADRO:
            n.setName('avogadro')
        elif t in (libsbml.AST_NAME, libsbml.AST_FUNCTION) and n.getName() in names:
            n.setName(names[n.getName()])
        stack.extend(n.getChild(i) for i in range(n.getNumChildren()))
    return libsbml.formulaToL3String(a)


def num(x: float | None) -> str | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.6g}'


def math_keys(m: Any) -> tuple[str, str]:
    """Two fingerprints of a model's mathematics with ids normalised by declaration order: the equations alone, and
    the equations with every number (sizes, initial values, parameter values). Order-sensitive: a copy matches,
    a re-encoding with its entities declared in another order does not."""
    names: dict[str, str] = {}
    comps = [m.getCompartment(i) for i in range(m.getNumCompartments())]
    spec = [m.getSpecies(i) for i in range(m.getNumSpecies())]
    pars = [m.getParameter(i) for i in range(m.getNumParameters())]
    funs = [m.getFunctionDefinition(i) for i in range(m.getNumFunctionDefinitions())]
    reacs = [m.getReaction(i) for i in range(m.getNumReactions())]
    for prefix, items in (('C', comps), ('S', spec), ('P', pars), ('F', funs), ('R', reacs)):
        for k, x in enumerate(items):
            names[x.getId()] = f'{prefix}{k}'
    eq: dict[str, Any] = {
        'compartments': [c.getSpatialDimensions() for c in comps],
        'species': [
            [names.get(s.getCompartment()), s.getBoundaryCondition(), s.getConstant(), s.getHasOnlySubstanceUnits()]
            for s in spec
        ],
        'parameters': [p.getConstant() for p in pars],
        'functions': [renamed_formula(f.getMath(), names) for f in funs],
        'initial_assignments': [
            [names.get(a.getSymbol(), a.getSymbol()), renamed_formula(a.getMath(), names)]
            for a in (m.getInitialAssignment(i) for i in range(m.getNumInitialAssignments()))
        ],
        'rules': [
            [r.getTypeCode(), names.get(r.getVariable(), r.getVariable()), renamed_formula(r.getMath(), names)]
            for r in (m.getRule(i) for i in range(m.getNumRules()))
        ],
        'reactions': [],
        'events': [],
    }
    values: dict[str, Any] = {
        'compartments': [num(c.getSize()) if c.isSetSize() else None for c in comps],
        'species': [
            num(s.getInitialConcentration())
            if s.isSetInitialConcentration()
            else num(s.getInitialAmount())
            if s.isSetInitialAmount()
            else None
            for s in spec
        ],
        'parameters': [num(p.getValue()) if p.isSetValue() else None for p in pars],
        'local': [],
    }
    for r in reacs:
        local = dict(names)
        kl = r.getKineticLaw() if r.isSetKineticLaw() else None
        lp = []
        if kl is not None:
            n_local = kl.getNumParameters() or kl.getNumLocalParameters()
            getp = kl.getParameter if kl.getNumParameters() else kl.getLocalParameter
            lp = [getp(i) for i in range(n_local)]
            for k, p in enumerate(lp):
                local[p.getId()] = f'{names[r.getId()]}.L{k}'

        def refs(lst: Any, n: int, stoich: bool = True) -> list[Any]:
            out = []
            for i in range(n):
                sr = lst(i)
                row = [names.get(sr.getSpecies(), sr.getSpecies())]
                if stoich:
                    row.append(num(sr.getStoichiometry()))
                out.append(row)
            return sorted(out, key=str)

        eq['reactions'].append(
            [
                r.getReversible(),
                refs(r.getReactant, r.getNumReactants()),
                refs(r.getProduct, r.getNumProducts()),
                refs(r.getModifier, r.getNumModifiers(), stoich=False),
                renamed_formula(kl.getMath(), local) if kl is not None else '',
            ]
        )
        values['local'].append([num(p.getValue()) if p.isSetValue() else None for p in lp])
    for i in range(m.getNumEvents()):
        e = m.getEvent(i)
        eq['events'].append(
            [
                renamed_formula(e.getTrigger().getMath(), names) if e.isSetTrigger() else '',
                renamed_formula(e.getDelay().getMath(), names) if e.isSetDelay() else '',
                sorted(
                    [names.get(a.getVariable(), a.getVariable()), renamed_formula(a.getMath(), names)]
                    for a in (e.getEventAssignment(j) for j in range(e.getNumEventAssignments()))
                ),
            ]
        )

    def h(x: Any) -> str:
        return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]

    return h(eq), h([eq, values])


def uses_time(m: Any) -> bool:
    """dynamics.forced's second test: time read by a rate law, rule or function definition."""
    import libsbml

    maths = [
        m.getReaction(i).getKineticLaw().getMath()
        for i in range(m.getNumReactions())
        if m.getReaction(i).isSetKineticLaw()
    ]
    maths += [m.getRule(i).getMath() for i in range(m.getNumRules())]
    maths += [m.getFunctionDefinition(i).getMath() for i in range(m.getNumFunctionDefinitions())]
    stack = [x for x in maths if x is not None]
    while stack:
        n = stack.pop()
        if n.getType() == libsbml.AST_NAME_TIME:
            return True
        stack.extend(n.getChild(i) for i in range(n.getNumChildren()))
    return False


def read_model(path_str: str) -> dict[str, Any]:
    """One SBML file in, a plain record out: annotation, history, the forced tests and the math fingerprints."""
    import libsbml

    path = pathlib.Path(path_str)
    rec: dict[str, Any] = {'model': path.stem}
    try:
        m = libsbml.readSBMLFromFile(str(path)).getModel()
        if m is None:
            return dict(rec, read_error='libSBML returned no model')
        cv = [(q, resource(u)) for q, u in cv_terms(m)]
        hist = m.getModelHistory() if m.isSetModelHistory() else None
        created = hist.getCreatedDate() if hist is not None and hist.isSetCreatedDate() else None
        eq_key, full_key = math_keys(m)
        notes = m.getNotesString() or ''
        rec.update(
            name=m.getName() or m.getId(),
            sbml_id=m.getId(),
            level=f'L{m.getLevel()}V{m.getVersion()}',
            taxa=[v for q, (ns, v) in cv if q == 'bqbiol:hasTaxon' and ns == 'taxonomy'],
            taxon_other=[f'{ns}:{v}' for q, (ns, v) in cv if q == 'bqbiol:hasTaxon' and ns != 'taxonomy'],
            pubs=sorted(
                {f'{ns}:{v}' for q, (ns, v) in cv if q.endswith(':isDescribedBy') and ns in ('pubmed', 'doi', 'arxiv')}
            ),
            derived_pubs=sorted(
                {f'{ns}:{v}' for q, (ns, v) in cv if q == 'bqmodel:isDerivedFrom' and ns in ('pubmed', 'doi', 'arxiv')}
            ),
            model_links=sorted({v for q, (ns, v) in cv if ns == 'biomodels.db' and q != 'bqmodel:is'}),
            own_ids=sorted({v for q, (ns, v) in cv if ns == 'biomodels.db' and q == 'bqmodel:is'}),
            created=created.getDateAsString()[:10] if created is not None else None,
            events=m.getNumEvents(),
            time_in_math=uses_time(m),
            species=m.getNumSpecies(),
            reactions=m.getNumReactions(),
            eq_key=eq_key,
            full_key=full_key,
            empty_math=not (m.getNumReactions() or m.getNumRules() or m.getNumEvents()),
            cc0=bool(re.search(r'CC0|public domain', notes, re.I)),
            notes_say_cc_by=bool(re.search(r'creativecommons\.org/licenses/by', notes, re.I)),
            notes_say_copyright_team=bool(re.search(r'copyright \(c\)[^<]*BioModels Team', notes, re.I)),
        )
    except Exception as e:  # recorded, never silent: the record says the file could not be read
        rec['read_error'] = repr(e)[:200]
    return rec


def read_all(jobs: int) -> dict[str, dict[str, Any]]:
    paths = [str(p) for s in ('r31', 'holdout') for p in sorted(FOLDERS[s].glob('*.xml'))]
    with Pool(jobs) as pool:
        recs = pool.map(read_model, paths, chunksize=4)
    out = {}
    for p, r in zip(paths, recs):
        r['set'] = 'r31' if pathlib.Path(p).parent == FOLDERS['r31'] else 'holdout'
        out[r['model']] = r
    return out


# ---------------------------------------------------------------- names: author, year, system, version
def author_year(name: str) -> tuple[str | None, int | None]:
    """First author and year from a BioModels name such as 'Edelstein1996 - EPSP ACh event'."""
    m = AUTHOR_YEAR.match(name or '')
    if m:
        first = re.split(r'&| and ', m.group(1))[0]
        first = re.sub(r'\s+[A-Z]\.?$', '', first.strip())  # a trailing initial: 'Robertson-Tessi M'
        key = re.sub(r"[^a-zÀ-ɏ]", '', first.lower())
        return (key or None), int(m.group(2))
    m = re.match(r'^([A-Z][A-Za-z\-]+?)(?:\d{2,3}\b|_)', name or '')  # 'Perez-Garcia19', 'PetelenzKuehn_osmo...'
    return (re.sub(r'[^a-z]', '', m.group(1).lower()) if m else None), None


def system_of(text: str) -> str:
    """The first SYSTEMS label whose pattern matches the name, read with separators as spaces and CamelCase split."""
    raw = text or ''
    plain = re.sub(r'[_\-/.]+', ' ', raw).lower()
    camel = re.sub(r'[_\-/.]+', ' ', re.sub(r'([a-z])([A-Z])', r'\1 \2', raw)).lower()
    for label, pat in SYSTEMS:
        if re.search(pat, plain) or re.search(pat, camel):
            return label
    return 'other'


def name_base(name: str) -> tuple[str, bool]:
    """The name with version tokens removed ('Borghans1997 - Calcium Oscillation - Model 2' -> its stem), and whether
    a version token was there."""
    n = name or ''
    hit = bool(VERSION_TOKEN.search(n))
    base = VERSION_TOKEN.sub(' ', n.lower())
    base = re.sub(r'[^a-z0-9]+', ' ', base).strip()
    return base, hit


def organism(taxa: list[str]) -> tuple[str, str]:
    """(taxon id with name, organism group) from the first declared taxonomy id."""
    if not taxa:
        return 'none declared', 'none declared'
    t = taxa[0]
    name, group = TAXA.get(t, (None, 'other taxon'))
    return (f'{t} {name}' if name else f'{t} (name not mapped)'), group


# ---------------------------------------------------------------- the funnel
def error_reason(text: str) -> str:
    """The libRoadRunner or libSBML message fragment that names why a model could not be read."""
    for frag in (
        'Unable to support delay differential equations',
        'is missing a value',
        'is not physically stored',
        "information from the 'qual' package",
    ):
        if frag in (text or ''):
            return frag
    return (text or '')[:80]


def funnel(s: str, sbml: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Every step from files on disk to the address test, each exclusion named as the code's records name it."""
    pre = PREFIX[s]
    S = jl(RES / f'{pre}structure_traj.jsonl')
    D = jl(RES / f'{pre}dynamics.jsonl')
    F = jd(RES / ('fingerprints.json' if s == 'r31' else 'holdout_fingerprints.json'))
    T = jd(RES / ('truth_tests.json' if s == 'r31' else 'holdout_truth_tests.json'))
    A = jd(RES / ('address_predicts.json' if s == 'r31' else 'holdout_address_predicts.json'))
    files = sorted(p.stem for p in FOLDERS[s].glob('*.xml'))
    ok = [r for r in S if r.get('status') == 'ok']
    not_ok = [r for r in S if r.get('status') != 'ok']
    errors: dict[str, list[str]] = collections.defaultdict(list)
    for r in not_ok:
        key = r['status'] if r['status'] != 'error' else 'error: ' + error_reason(r.get('error', ''))
        errors[key].append(r['model'])
    complete = [r for r in ok if (r.get('defs') or {}).get('ref24_rank', {}).get('complete')]
    done = {r['model'] for r in complete}
    unfinished = [r for r in ok if r['model'] not in done]
    loops = [r['defs']['ref24_rank']['c'] for r in complete]

    def bins(c: int) -> str:
        return '0' if c == 0 else str(c) if c <= 3 else '4-9' if c <= 9 else '10-99' if c <= 99 else '100+'

    small = [r for r in complete if 1 <= r['defs']['ref24_rank']['c'] <= 3]
    spent = [d['model'] for d in D if (d.get('status') or '').startswith('budget')]
    dyn_errors = [d['model'] for d in D if d.get('status') == 'error']
    forced = [d for d in D if d.get('status') == 'ok' and d.get('forced')]
    own = [d for d in D if d.get('status') == 'ok' and d.get('forced') is False]
    # every model read reaches one of the four, so the step to "run on their own" adds up on the datasheet
    assert len(spent) + len(dyn_errors) + len(forced) + len(own) == len(ok) == len(D), (
        pre,
        len(spent),
        len(dyn_errors),
        len(forced),
        len(own),
        len(ok),
        len(D),
    )
    labelled = [d for d in own if d.get('behaviours')]
    unlabelled = [d for d in own if not d.get('behaviours')]
    why_forced = counter(
        'events and time'
        if sbml[d['model']]['events'] and sbml[d['model']]['time_in_math']
        else 'events'
        if sbml[d['model']]['events']
        else 'time in a rate law, rule or function'
        if sbml[d['model']]['time_in_math']
        else 'neither (disagrees with dynamics.forced)'
        for d in forced
    )
    run_kinds = counter('+'.join(sorted(set(d['runs']))) for d in unlabelled)
    fm = F['models']
    fstatus = counter(m.get('status') for m in fm)
    read_atlas = [m for m in fm if m.get('status') == 'ok']
    filed = [m for m in read_atlas if m.get('row') != 'flat']
    address = [m for m in filed if m.get('address')]
    primary = [m for m in address if 1 <= m['address'][0] <= 3]
    out: dict[str, Any] = {
        'files on disk': len(files),
        'structure records (loops.py)': {'n': len(S), 'file': f'results/{pre}structure_traj.jsonl'},
        'read as equations (status ok)': {'n': len(ok), 'key': f'{pre}structure_traj.jsonl status == "ok"'},
        'not read, by status': {k: {'n': len(v), 'models': v} for k, v in sorted(errors.items())},
        'every loop listed (defs.ref24_rank.complete)': {'n': len(complete)},
        'loop search unfinished (5,000,000 steps or 20,000 loops)': {
            'n': len(unfinished),
            'models': sorted(r['model'] for r in unfinished),
        },
        'loop count among the listed (defs.ref24_rank.c)': counter(bins(c) for c in loops),
        'one to three loops': {'n': len(small)},
        'running-total records (integrators.py)': {
            'n': len(jl(RES / f'{pre}integrators.jsonl')),
            'file': f'results/{pre}integrators.jsonl',
        },
        'dynamics records (dynamics.py)': {'n': len(D), 'file': f'results/{pre}dynamics.jsonl'},
        'dynamics status budget (solver work spent)': {'n': len(spent), 'models': spent},
        'dynamics status error': {'n': len(dyn_errors), 'models': dyn_errors},
        'forced (events, or time in a rate law, rule or function)': {'n': len(forced), 'why': why_forced},
        'run on their own (status ok, forced false)': {'n': len(own)},
        'match a behaviour label (behaviours not empty)': {
            'n': len(labelled),
            'check': {'truth_tests rules.autonomous': T['rules']['autonomous']},
        },
        'run on their own with no behaviour label': {
            'n': len(unlabelled),
            'what the twelve runs ended as (dynamics.runs)': run_kinds,
            'models': sorted(d['model'] for d in unlabelled),
        },
        'atlas records (fingerprints.py)': {'n': len(fm)},
        'atlas status': fstatus,
        'atlas read (status ok)': {'n': len(read_atlas)},
        'atlas flat (no 20% step moves any molecule by 5%)': {
            'n': sum(1 for m in read_atlas if m.get('row') == 'flat')
        },
        'atlas filed in a row': {'n': len(filed), 'rows': counter(m['row'] for m in filed)},
        'filed with a loop address (0 to 3 loops, all listed)': {'n': len(address)},
        'address test scope (1 to 3 loops)': {
            'n': len(primary),
            'check': {'address_predicts amended_primary.n': A['amended_primary']['n']},
        },
    }
    return out


def cross_checks(sbml: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Every pair of files that should agree, compared; 'agree' false marks a disagreement."""
    checks: list[dict[str, Any]] = []

    def check(what: str, a_src: str, a: Any, b_src: str, b: Any, note: str = '') -> None:
        checks.append(
            {'what': what, 'a': {a_src: a}, 'b': {b_src: b}, 'agree': a == b, **({'note': note} if note else {})}
        )

    for s in ('r31', 'holdout'):
        pre = PREFIX[s]
        S = {r['model']: r for r in jl(RES / f'{pre}structure_traj.jsonl')}
        D = {r['model']: r for r in jl(RES / f'{pre}dynamics.jsonl')}
        integ = {r['model']: r for r in jl(RES / f'{pre}integrators.jsonl')}
        F = jd(RES / ('fingerprints.json' if s == 'r31' else 'holdout_fingerprints.json'))
        T = jd(RES / ('truth_tests.json' if s == 'r31' else 'holdout_truth_tests.json'))
        TB = jd(RES / ('tables_traj.json' if s == 'r31' else 'holdout_tables_traj.json'))
        A = jd(RES / ('address_predicts.json' if s == 'r31' else 'holdout_address_predicts.json'))
        files = {p.stem for p in FOLDERS[s].glob('*.xml')}
        ok = {m for m, r in S.items() if r.get('status') == 'ok'}
        own = {m for m, d in D.items() if d.get('status') == 'ok' and d.get('forced') is False}
        auto = {m for m in own if D[m].get('behaviours')}
        filed = [m for m in F['models'] if m.get('status') == 'ok' and m.get('row') != 'flat']
        check(
            f'{s}: models on disk = structure records', 'data folder', len(files), f'{pre}structure_traj.jsonl', len(S)
        )
        check(
            f'{s}: structure ids = file names', 'data folder', sorted(files - set(S)), f'{pre}structure_traj.jsonl', []
        )
        check(
            f'{s}: dynamics ran on exactly the models read',
            f'{pre}structure_traj.jsonl status ok',
            sorted(ok),
            f'{pre}dynamics.jsonl models',
            sorted(D),
        )
        check(
            f'{s}: integrators ran on exactly the models read',
            f'{pre}structure_traj.jsonl status ok',
            len(ok),
            f'{pre}integrators.jsonl',
            len(set(integ) & ok),
        )
        check(
            f'{s}: structure status counts',
            f'{pre}structure_traj.jsonl',
            counter(r['status'] for r in S.values()),
            f'{pre}tables_traj.json census',
            counter_from(TB['census']),
        )
        check(
            f'{s}: forced models',
            f'{pre}dynamics.jsonl forced',
            sum(1 for d in D.values() if d.get('forced')),
            f'{pre}tables_traj.json theorem_checks."forced models excluded"',
            TB['theorem_checks']['forced models excluded'],
        )
        check(
            f'{s}: autonomous labelled models',
            f'{pre}dynamics.jsonl',
            len(auto),
            f'{pre}truth_tests.json rules.autonomous',
            T['rules']['autonomous'],
        )
        check(
            f'{s}: clocks (oscillating)',
            f'{pre}tables_traj.json theorem_checks.oscillating',
            TB['theorem_checks']['oscillating'],
            f'{pre}truth_tests.json rules.clock',
            T['rules']['clock'],
        )
        check(
            f'{s}: memories (multistable)',
            f'{pre}tables_traj.json theorem_checks.multistable',
            TB['theorem_checks']['multistable'],
            f'{pre}truth_tests.json rules.memory',
            T['rules']['memory'],
        )
        n_checked = sum(1 for m in own)  # tabulate checks every autonomous model, labelled or not
        check(
            f'{s}: denominator of the sign-rule check',
            'tables_traj theorem_checks (run on their own)',
            n_checked,
            f'{pre}truth_tests.json rules.autonomous (labelled only)',
            T['rules']['autonomous'],
            'both report no exception; the two files check different sets (with and without the unlabelled models) '
            'and tabulate reads the memory rule on refined_positive alone, truth_tests on plain or refined',
        )
        check(
            f'{s}: atlas ran on the labelled autonomous models',
            f'{pre}dynamics.jsonl',
            sorted(auto),
            'fingerprints.json models',
            sorted(m['model'] for m in F['models']),
        )
        check(
            f'{s}: atlas rows recount',
            'fingerprints.json models[].row',
            counter(m['row'] for m in F['models'] if m.get('status') == 'ok'),
            'fingerprints.json rows',
            counter_from(F['rows']),
        )
        check(
            f'{s}: filed models',
            'fingerprints.json recount',
            len(filed),
            'address_predicts.json filed_models',
            A['filed_models'],
        )
        check(
            f'{s}: filed with an address',
            'fingerprints.json recount',
            sum(1 for m in filed if m.get('address')),
            'address_predicts.json with_address',
            A['with_address'],
        )
        listed = {r['model'] for r in S.values() if r.get('status') == 'ok' and r['defs']['ref24_rank'].get('complete')}
        if 'integrators' in TB:
            check(
                f'{s}: complete loop listings',
                f'{pre}structure_traj.jsonl',
                len(listed),
                f'{pre}tables_traj.json integrators."models with complete ref24_rank enumeration"',
                TB['integrators']['models with complete ref24_rank enumeration'],
            )
        for n in ('1', '2', '3'):
            rec = sum(1 for m in listed if S[m]['defs']['ref24_rank']['c'] == int(n))
            check(
                f'{s}: models with {n} loop(s)',
                f'{pre}structure_traj.jsonl',
                rec,
                f'{pre}tables_traj.json defs.ref24_rank.rows.{n}.models',
                TB['defs']['ref24_rank']['rows'][n]['models'],
            )
    # release 31 only
    S = {r['model']: r for r in jl(RES / 'r31_structure_traj.jsonl')}
    D = {r['model']: r for r in jl(RES / 'r31_dynamics.jsonl')}
    N = jd(RES / 'nesting.json')['census']
    lst = [line.strip() for line in (RES / 'list_ok.txt').read_text().splitlines() if line.strip()]
    check(
        'r31: list_ok.txt = models read',
        'results/list_ok.txt',
        len(lst),
        'r31_structure_traj.jsonl status ok',
        sum(1 for r in S.values() if r.get('status') == 'ok'),
    )
    mixed = [
        m
        for m, d in S.items()
        if d.get('status') == 'ok'
        and d.get('loops') == 2
        and d.get('loop_list')
        and sorted(lp['sign'] for lp in d['loop_list']) == ['+', '-']
    ]
    check(
        'r31: mixed two-loop models',
        'r31_structure_traj.jsonl recount',
        len(mixed),
        'nesting.json census.mixed_two_loop_models',
        N['mixed_two_loop_models'],
    )
    t = N['transit_time']
    check(
        'r31: speed-order test, models in the table',
        'nesting.json census.transit_time.usable',
        t['usable'],
        'sum of nesting.json census.transit_time.table',
        sum(sum(v.values()) for v in t['table'].values()),
        'usable counts the one tie (ties_left_out) that the table leaves out',
    )
    for m, d in D.items():
        if m in sbml and d.get('status') == 'ok':
            mine = bool(sbml[m]['events']) or sbml[m]['time_in_math']
            if mine != d['forced']:
                check(f'r31: forced flag of {m}', 'r31_dynamics.jsonl', d['forced'], 'this audit, from the SBML', mine)
    # hold-out bookkeeping
    ids = jd(RES / 'holdout_ids.json')
    man = jd(RES / 'holdout_manifest.json')
    sc = jd(RES / 'holdout_score.json')
    fun = funnel('holdout', sbml)
    check(
        'holdout: listed = with a checksum',
        'holdout_ids.json holdout',
        len(ids['holdout']),
        'holdout_manifest.json entries with sha256',
        sum(1 for v in man.values() if v.get('sha256')),
    )
    check(
        'holdout: curated not in release 31 minus not SBML',
        'holdout_ids.json curated_not_in_release31 - len(not_sbml)',
        ids['curated_not_in_release31'] - len(ids['not_sbml']),
        'holdout_ids.json holdout',
        len(ids['holdout']),
    )
    check(
        'holdout: bytes listed = bytes in manifest',
        'holdout_ids.json holdout[].bytes',
        sum(h['bytes'] for h in ids['holdout']),
        'holdout_manifest.json bytes',
        sum(v.get('bytes', 0) for v in man.values()),
    )
    pairs = [
        ('read as equations', 'read as equations (status ok)'),
        ('every loop listed', 'every loop listed (defs.ref24_rank.complete)'),
        ('one to three loops', 'one to three loops'),
        ('run on their own', 'run on their own (status ok, forced false)'),
        ('match a behaviour label', 'match a behaviour label (behaviours not empty)'),
        ('atlas read', 'atlas read (status ok)'),
        ('atlas filed', 'atlas filed in a row'),
    ]
    for a, b in pairs:
        check(f'holdout funnel: {a}', f'holdout_score.json funnel.{a}', sc['funnel'][a], 'this audit', fun[b]['n'])
    F31 = jd(RES / 'fingerprints.json')
    filed31 = sum(v for k, v in F31['rows'].items() if k != 'flat')
    check(
        'holdout_score: release 31 follows share',
        'holdout_score.json "six answers"."release 31 follows share" (typed in holdout_score.py as 111 / 273)',
        sc['six answers']['release 31 follows share'],
        'fingerprints.json rows.follows / filed',
        round(F31['rows']['follows'] / filed31, 4),
        'the score script types the two numbers (111 / 273) instead of reading them',
    )
    return checks


def counter_from(d: dict[str, int]) -> dict[str, int]:
    return dict(sorted(((str(k), v) for k, v in d.items()), key=lambda kv: (-kv[1], kv[0])))


def verify_checksums() -> dict[str, Any]:
    sh = (ROOT / 'analysis' / 'get_biomodels.sh').read_text()
    expected = re.search(r'SHA="([0-9a-f]{64})"', sh).group(1)
    release = re.search(r'releases/(\d{4}-\d{2}-\d{2})/', sh).group(1)
    tar = ROOT / 'data' / 'r31.tar.bz2'
    got = hashlib.sha256(tar.read_bytes()).hexdigest() if tar.exists() else None
    man = jd(RES / 'holdout_manifest.json')
    bad = []
    for m, e in sorted(man.items()):
        if e.get('sha256'):
            f = FOLDERS['holdout'] / f'{m}.xml'
            if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != e['sha256']:
                bad.append(m)
    return {
        'release 31 date (get_biomodels.sh URL)': release,
        'release 31 archive sha256 expected (get_biomodels.sh)': expected,
        'release 31 archive sha256 now': got,
        'release 31 archive matches': got == expected,
        'holdout files checked against holdout_manifest.json': sum(1 for e in man.values() if e.get('sha256')),
        'holdout files that differ': bad,
    }


# ---------------------------------------------------------------- per-model table and groups
def model_table(sbml: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    holdout = {h['id']: h for h in jd(RES / 'holdout_ids.json')['holdout']}
    rows = {}
    for m, r in sorted(sbml.items()):
        au, yr = author_year(r.get('name', ''))
        taxon, org = organism(r.get('taxa', []))
        base, ver = name_base(r.get('name', ''))
        rows[m] = {
            'set': r['set'],
            'name': r.get('name'),
            'author': au,
            'year': yr,
            'encoded': (r.get('created') or '')[:4] or None,
            'submitted': holdout.get(m, {}).get('submitted'),
            'taxon': taxon,
            'organism': org,
            'system': system_of(f"{r.get('name', '')} {r.get('sbml_id', '')}"),
            'pubs': r.get('pubs', []),
            'name_base': base,
            'version_in_name': ver,
        }
    return rows


def link_sets(sbml: dict[str, dict[str, Any]], table: dict[str, dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Pairs of models joined by each kind of evidence (over release 31 and the hold-out together)."""
    alias = {}
    for m, r in sbml.items():
        for v in r.get('own_ids', []):
            alias[v] = m
        alias[m] = m
    by: dict[str, dict[str, list[str]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for m, r in sorted(sbml.items()):
        if 'read_error' in r:
            continue
        if not r['empty_math']:  # SBML-qual files have no core math; empty is not identical
            by['exact copy (same equations and numbers)'][r['full_key']].append(m)
            by['same equations, other numbers'][r['eq_key']].append(m)
        for p in r['pubs']:
            by['same publication (isDescribedBy)'][p].append(m)
        t = table[m]
        if t['version_in_name']:
            by['declared version in the name'][t['name_base']].append(m)
        if t['author'] and t['year']:
            by['same first author and year'][f"{t['author']} {t['year']}"].append(m)
        if t['author']:
            by['same first author'][t['author']].append(m)
    # a version token on one member is enough: its unversioned sibling shares the stem
    stems = collections.defaultdict(list)
    for m, t in table.items():
        stems[t['name_base']].append(m)
    for b in list(by['declared version in the name']):
        by['declared version in the name'][b] = sorted(set(stems[b]))
    pairs: dict[str, list[tuple[str, str]]] = {}
    for kind, groups in by.items():
        pairs[kind] = [(v[0], x) for k, v in sorted(groups.items()) if len(set(v)) > 1 for x in sorted(set(v))[1:]]
    pubs_of = collections.defaultdict(list)
    for m, r in sbml.items():
        for p in r.get('pubs', []):
            pubs_of[p].append(m)
    derived = []
    for m, r in sorted(sbml.items()):
        for v in r.get('model_links', []):
            if v in alias and alias[v] != m:
                derived.append((m, alias[v]))
        for p in r.get('derived_pubs', []):
            derived += [(m, x) for x in sorted(pubs_of.get(p, [])) if x != m]
    pairs['declared derivation (isDerivedFrom, or a link to another BioModels entry)'] = sorted(set(derived))
    fam = jd(RES / 'truth_tests.json')['families']
    pairs['truth_tests.json family'] = [(v[0]['model'], x['model']) for v in fam.values() for x in v[1:]]
    return pairs


PUBLICATION_KINDS = (
    'exact copy (same equations and numbers)',
    'same equations, other numbers',
    'same publication (isDescribedBy)',
    'declared version in the name',
    'truth_tests.json family',
)
DERIVATION = 'declared derivation (isDerivedFrom, or a link to another BioModels entry)'
LEVELS: list[tuple[str, tuple[str, ...]]] = [
    ('publication', PUBLICATION_KINDS),
    ('lineage', PUBLICATION_KINDS + (DERIVATION,)),
    ('author-year', PUBLICATION_KINDS + (DERIVATION, 'same first author and year')),
    ('lab', PUBLICATION_KINDS + (DERIVATION, 'same first author and year', 'same first author')),
]


def groupings(ids: Iterable[str], pairs: dict[str, list[tuple[str, str]]]) -> dict[str, dict[str, str]]:
    """Four nested groupings, each a union of the evidence before it: publication (one paper or one system drawn again:
    copies, same equations, same isDescribedBy, a version in the name, the truth tests' families), lineage (adds
    declared derivation: a model built from another), author-year (adds same first author and year), lab (adds same
    first author)."""
    out = {}
    ids = sorted(ids)
    for name, kinds in LEVELS:
        g = Groups(ids)
        for k in kinds:
            for a, b in pairs.get(k, []):
                if a in g.parent and b in g.parent:
                    g.join(a, b)
        out[name] = g.label()
    return out


def group_summary(
    label: dict[str, str], scope: Iterable[str], table: dict[str, dict[str, Any]], full: bool = False
) -> dict[str, Any]:
    mem = members(label, scope)
    sizes = [len(v) for v in mem.values()]
    big = sorted(mem.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return {
        'models': sum(sizes),
        'groups': len(mem),
        'singletons': sum(1 for x in sizes if x == 1),
        'models in groups of 2 or more': sum(x for x in sizes if x > 1),
        'largest': [
            {'group': k, 'size': len(v), 'names': sorted({(table[x]['name'] or '')[:50] for x in v})[:6], 'models': v}
            for k, v in big[:12]
            if len(v) > 1
        ],
        **({'all groups of 2 or more': [v for k, v in big if len(v) > 1]} if full else {}),
    }


# ---------------------------------------------------------------- imbalance
def imbalance(s: str, table: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pre = PREFIX[s]
    S = {r['model']: r for r in jl(RES / f'{pre}structure_traj.jsonl')}
    D = {r['model']: r for r in jl(RES / f'{pre}dynamics.jsonl')}
    F = jd(RES / ('fingerprints.json' if s == 'r31' else 'holdout_fingerprints.json'))
    read = sorted(m for m, r in S.items() if r.get('status') == 'ok')
    auto = sorted(
        m for m, d in D.items() if d.get('status') == 'ok' and d.get('forced') is False and d.get('behaviours')
    )
    filed = {m['model']: m for m in F['models'] if m.get('status') == 'ok' and m.get('row') != 'flat'}

    def loops_bin(m: str) -> str:
        d = S[m]['defs']['ref24_rank']
        if not d.get('complete'):
            return 'unfinished'
        c = d['c']
        return '0' if c == 0 else str(c) if c <= 3 else '4-9' if c <= 9 else '10-99' if c <= 99 else '100+'

    def decade(m: str) -> str:
        y = table[m]['year']
        return f'{y // 10 * 10}s' if y else 'no year in name'

    def by(scope: Sequence[str], f: Callable[[str], Any]) -> dict[str, Any]:
        return spread(f(m) for m in scope)

    out: dict[str, Any] = {}
    for scope_name, scope in (('read', read), ('labelled', auto), ('filed', sorted(filed))):
        out[scope_name] = {
            'n': len(scope),
            'organism': by(scope, lambda m: table[m]['organism']),
            'taxon': by(scope, lambda m: table[m]['taxon']),
            'publication decade (name)': by(scope, decade),
            'year encoded in BioModels (model history)': by(scope, lambda m: table[m]['encoded'] or 'none'),
            'first author (name)': by(scope, lambda m: table[m]['author'] or 'not parsed'),
            'system (keyword map)': by(scope, lambda m: table[m]['system']),
            'loop count (defs.ref24_rank.c)': by(scope, loops_bin),
        }
    out['labelled']['behaviour label (models showing it)'] = counter(b for m in auto for b in D[m]['behaviours'])
    out['labelled']['behaviour signature (as tabulate.py)'] = spread(
        '+'.join(x for x in D[m]['behaviours'] if x != 'steady' or len(D[m]['behaviours']) == 1) for m in auto
    )
    out['filed']['atlas row'] = spread(filed[m]['row'] for m in sorted(filed))
    ticks = sorted(m for m in filed if filed[m]['row'] == 'ticks')
    out['ticks'] = {
        'n': len(ticks),
        'system': spread(table[m]['system'] for m in ticks),
        'first author': spread(table[m]['author'] or 'not parsed' for m in ticks),
        'started by the push, not before': sum(1 for m in ticks if filed[m].get('why') == 'the push starts it ticking'),
    }
    out['follows'] = follows_profile(filed, S, D, table)
    return out


def follows_profile(
    filed: dict[str, dict], S: dict[str, dict], D: dict[str, dict], table: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """What 'follows' holds, against the other rows: a class has a mix of its own; a leftover bin looks like the whole."""
    rows = collections.defaultdict(list)
    for m, r in sorted(filed.items()):
        rows[r['row']].append(m)
    allsys = counter(table[m]['system'] for m in filed)
    fol = rows.get('follows', [])
    ratio = [filed[m]['step_final'] / filed[m]['step_peak'] for m in fol if filed[m].get('step_peak')]

    def size(ms: Sequence[str]) -> dict[str, float]:
        return quartiles([D[m].get('state_variables') for m in ms])

    return {
        'n': len(fol),
        'share of filed': share(len(fol), len(filed)),
        'why (fingerprints.json models[].why)': counter(filed[m].get('why') for m in fol),
        'system': spread(table[m]['system'] for m in fol),
        'first author': spread(table[m]['author'] or 'not parsed' for m in fol),
        'system mix distance from all filed models, by row (TVD)': {
            r: tvd(counter(table[m]['system'] for m in ms), allsys) for r, ms in sorted(rows.items())
        },
        'state variables by row (quartiles)': {r: size(ms) for r, ms in sorted(rows.items())},
        'with a loop address': sum(1 for m in fol if filed[m].get('address')),
        'loop address': counter(
            tuple(filed[m]['address']) if filed[m].get('address') else 'none (4+ loops or unfinished)' for m in fol
        ),
        'census behaviours': counter('+'.join(D[m]['behaviours']) for m in fol),
        'final shift over peak shift (step_final / step_peak)': quartiles(ratio),
        'final shift at least 95% of peak': sum(1 for x in ratio if x >= 0.95),
        'overshoots (crossings)': counter(filed[m].get('crossings') for m in fol),
        'members': [{'model': m, 'name': (table[m]['name'] or '')[:70], 'system': table[m]['system']} for m in fol],
    }


# ---------------------------------------------------------------- leakage and shift
def leakage(table: dict[str, dict[str, Any]], pairs: dict[str, list[tuple[str, str]]]) -> dict[str, Any]:
    r31 = {m for m, t in table.items() if t['set'] == 'r31'}
    hold = sorted(m for m, t in table.items() if t['set'] == 'holdout')
    kinds = {
        'derives from a release 31 model': 'declared derivation (isDerivedFrom, or a link to another BioModels entry)',
        'same publication as a release 31 model': 'same publication (isDescribedBy)',
        'same equations as a release 31 model': 'same equations, other numbers',
        'exact copy of a release 31 model': 'exact copy (same equations and numbers)',
        'same name stem as a versioned release 31 model': 'declared version in the name',
        'same first author and year as a release 31 model': 'same first author and year',
    }
    hits: dict[str, dict[str, list[str]]] = {k: collections.defaultdict(list) for k in kinds}
    for label, kind in kinds.items():
        groups = collections.defaultdict(set)
        for a, b in pairs.get(kind, []):
            groups[a].add(b)
            groups[a].add(a)
        for g in groups.values():
            if g & r31:
                for h in g - r31:
                    hits[label][h] = sorted(g & r31)
    # derivation edges are directed pairs, not stars: read them directly
    hits['derives from a release 31 model'] = collections.defaultdict(list)
    for a, b in pairs[kinds['derives from a release 31 model']]:
        if a in hold and b in r31:
            hits['derives from a release 31 model'][a].append(b)
        if b in hold and a in r31:
            hits['derives from a release 31 model'][b].append(a)
    authors31 = {table[m]['author'] for m in r31 if table[m]['author']}
    same_author = [m for m in hold if table[m]['author'] in authors31]
    leaked = sorted({h for k in hits.values() for h in k})
    r31_date = verify_release_date()
    before = [m for m in hold if (table[m]['submitted'] or '9999') < r31_date]
    return {
        'definition': 'leaked = any of the kinds below except "same first author" (reported, not removed)',
        'by kind': {
            k: {'n': len(v), 'pairs': {h: sorted(set(x)) for h, x in sorted(v.items())}} for k, v in hits.items()
        },
        'leaked': {
            'n': len(leaked),
            'of': len(hold),
            'models': [
                {'model': h, 'name': (table[h]['name'] or '')[:70], 'kinds': [k for k, v in hits.items() if h in v]}
                for h in leaked
            ],
        },
        'same first author as a release 31 model (not removed)': {'n': len(same_author)},
        'submitted before release 31 (holdout_ids.json submitted)': {
            'n': len(before),
            'release 31': r31_date,
            'models': before,
        },
    }


def verify_release_date() -> str:
    return re.search(r'releases/(\d{4}-\d{2}-\d{2})/', (ROOT / 'analysis' / 'get_biomodels.sh').read_text()).group(1)


def shift(table: dict[str, dict[str, Any]], imb: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The hold-out's mix against release 31's, per axis: TVD of the shares, and size quartiles."""
    out: dict[str, Any] = {}
    for scope, axes in (
        (
            'read',
            (
                'organism',
                'publication decade (name)',
                'system (keyword map)',
                'loop count (defs.ref24_rank.c)',
                'first author (name)',
            ),
        ),
        ('labelled', ('behaviour signature (as tabulate.py)',)),
        ('filed', ('atlas row',)),
    ):
        for ax in axes:
            a = imb['r31'][scope][ax]['counts']
            b = imb['holdout'][scope][ax]['counts']
            out[f'{scope}: {ax}'] = {
                'tvd': tvd(a, b),
                'release 31 shares': {k: share(v, sum(a.values())) for k, v in list(a.items())[:8]},
                'hold-out shares': {k: share(v, sum(b.values())) for k, v in list(b.items())[:8]},
            }
    for s in ('r31', 'holdout'):
        S = {r['model']: r for r in jl(RES / f'{PREFIX[s]}structure_traj.jsonl')}
        D = {r['model']: r for r in jl(RES / f'{PREFIX[s]}dynamics.jsonl')}
        ok = [m for m, r in S.items() if r.get('status') == 'ok']
        out[f'size, {s}'] = {
            'species (structure)': quartiles([S[m]['species'] for m in ok]),
            'reactions (structure)': quartiles([S[m]['reactions'] for m in ok]),
            'state variables (dynamics)': quartiles([D[m].get('state_variables') for m in ok if m in D]),
            'rate rules used (structure rate_rules > 0)': sum(1 for m in ok if S[m].get('rate_rules')),
            'no reactions (written as rules)': sum(1 for m in ok if not S[m]['reactions']),
        }
    return out


# ---------------------------------------------------------------- grouped recounts
def address_records(s: str) -> list[dict]:
    """address_predicts.load for either set (same fields, same filter); pinned against AP.load() on release 31."""
    pre = PREFIX[s]
    F = jd(RES / ('fingerprints.json' if s == 'r31' else 'holdout_fingerprints.json'))
    size = {r['model']: r.get('state_variables') for r in jl(RES / f'{pre}dynamics.jsonl')}
    plain = {
        r['model']: (bool(r.get('plain_negative')), bool(r.get('plain_positive')))
        for r in jl(RES / f'{pre}structure_traj.jsonl')
    }
    recs = []
    for m in F['models']:
        if m.get('status') != 'ok' or m.get('row') not in AP.ROWS or not m.get('address'):
            continue
        c, k, j = m['address']
        sv = size.get(m['model'])
        recs.append(
            {
                'model': m['model'],
                'answer': m['row'],
                'address': (c, k, j),
                'sign': (k >= 1, c - k >= 1),
                'plain': plain[m['model']],
                'size': len(sv) if isinstance(sv, list) else sv,
            }
        )
    return recs


def predictor_keys(recs: list[dict]) -> tuple[list[Any], dict[str, list[Any]]]:
    """The amended test's sign strata and its three predictors, built as address_predicts.run builds them."""
    signs = [r['plain'] for r in recs]
    n_addr, n_sign = len({r['address'] for r in recs}), len(set(signs))
    q = math.ceil(n_addr / n_sign)
    return signs, {
        'sign': signs,
        'address': [(r['plain'], r['address']) for r in recs],
        'size': list(zip(signs, AP.size_bins(recs, q))),
    }


def logo_accuracy(answers: list[str], keys: list[Any], signs: list[Any], groups: list[str]) -> float:
    """Leave-one-group-out majority vote: a model's answer is predicted only from models outside its group, with the
    address test's fallbacks (its sign stratum, then everyone); a tie or an empty pool falls through."""
    by_key: dict[Any, collections.Counter] = collections.defaultdict(collections.Counter)
    by_sign: dict[Any, collections.Counter] = collections.defaultdict(collections.Counter)
    overall: collections.Counter = collections.Counter()
    g_key: dict[tuple[str, Any], collections.Counter] = collections.defaultdict(collections.Counter)
    g_sign: dict[tuple[str, Any], collections.Counter] = collections.defaultdict(collections.Counter)
    g_all: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for a, k, s, g in zip(answers, keys, signs, groups):
        by_key[k][a] += 1
        by_sign[s][a] += 1
        overall[a] += 1
        g_key[g, k][a] += 1
        g_sign[g, s][a] += 1
        g_all[g][a] += 1

    def pick(pool: collections.Counter, minus: collections.Counter) -> str | None:
        c = pool - minus
        best = c.most_common(2)
        if not best or (len(best) > 1 and best[1][1] == best[0][1]):
            return None
        return best[0][0]

    hit = 0
    for a, k, s, g in zip(answers, keys, signs, groups):
        guess = pick(by_key[k], g_key[g, k]) or pick(by_sign[s], g_sign[g, s]) or pick(overall, g_all[g])
        hit += guess == a
    return hit / len(answers)


def logo_test(recs: list[dict], label: dict[str, str], seed: int) -> dict[str, Any]:
    """All models kept, each predicted from other groups only; null = answers shuffled inside sign strata."""
    answers = [r['answer'] for r in recs]
    groups = [label[r['model']] for r in recs]
    signs, keys = predictor_keys(recs)
    acc = {k: logo_accuracy(answers, v, signs, groups) for k, v in keys.items()}
    rng = random.Random(seed)
    idx_by_sign = collections.defaultdict(list)
    for i, s in enumerate(signs):
        idx_by_sign[s].append(i)
    ge = 0
    for _ in range(N_SHUFFLES):
        sh = answers[:]
        for idx in idx_by_sign.values():
            vals = [answers[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                sh[i] = v
        ge += logo_accuracy(sh, keys['address'], signs, groups) >= acc['address'] - 1e-12
    sizes = collections.Counter(groups)
    return {
        'n': len(recs),
        'groups': len(sizes),
        'groups with 2 or more models': sum(1 for v in sizes.values() if v > 1),
        'accuracy': {k: round(v, 4) for k, v in acc.items()},
        'p': round((1 + ge) / (1 + N_SHUFFLES), 4),
    }


def address_tests(s: str, labels: dict[str, dict[str, str]], leaked: Sequence[str]) -> dict[str, Any]:
    """The amended primary address test: as published (a pin), one model per group, leave-one-group-out, and for the
    hold-out with the leaked models removed."""
    recs = [r for r in address_records(s) if 1 <= r['address'][0] <= 3]
    A = jd(RES / ('address_predicts.json' if s == 'r31' else 'holdout_address_predicts.json'))['amended_primary']

    def brief(r: dict[str, Any]) -> dict[str, Any]:
        return {k: r[k] for k in ('n', 'distinct_addresses', 'chance', 'accuracy', 'p', 'verdict')}

    base = AP.run(recs, 'amended: one to three loops', random.Random(SEED), 'plain')
    out: dict[str, Any] = {
        'published (address_predicts amended_primary)': brief(A),
        'recomputed here': brief(base),
        'reproduces': all(base[k] == A[k] for k in ('n', 'accuracy', 'p')),
    }
    assert out['reproduces'], f'{s}: the address test does not reproduce from the files; no recount is trusted'
    for g, label in labels.items():
        reps = set(one_per_group(label, [r['model'] for r in recs]))
        out[f'one model per {g} group'] = brief(
            AP.run([r for r in recs if r['model'] in reps], g, random.Random(SEED), 'plain')
        )
        out[f'leave one {g} group out'] = logo_test(recs, label, SEED)
    if leaked:
        kept = [r for r in recs if r['model'] not in set(leaked)]
        out['leaked removed'] = brief(AP.run(kept, 'no leak', random.Random(SEED), 'plain'))
        reps = set(one_per_group(labels['publication'], [r['model'] for r in kept]))
        out['leaked removed, one model per publication group'] = brief(
            AP.run([r for r in kept if r['model'] in reps], 'no leak, publication', random.Random(SEED), 'plain')
        )
    return out


def sign_rule_recount(s: str, labels: dict[str, dict[str, str]], leaked: Sequence[str]) -> dict[str, Any]:
    pre = PREFIX[s]
    S = {r['model']: r for r in jl(RES / f'{pre}structure_traj.jsonl')}
    D = {r['model']: r for r in jl(RES / f'{pre}dynamics.jsonl')}
    auto = sorted(
        m for m, d in D.items() if d.get('status') == 'ok' and d.get('forced') is False and d.get('behaviours')
    )
    cand = [
        m
        for m in auto
        if ('multistable' in D[m]['behaviours'] and not (S[m].get('plain_positive') or S[m].get('refined_positive')))
        or ('oscillating' in D[m]['behaviours'] and not S[m].get('plain_negative'))
    ]
    cleared = []
    if s == 'holdout':
        H = jd(RES / 'holdout_handcheck.json')
        for h in H:
            if h['rule'] == 'ticks with no brake':
                ok = h.get('has a brake') or (
                    h.get('further check', {}).get('peaks of N_CTL in the second half of a 4000-unit run') == 0
                )
            else:
                ok = h.get('further check', {}).get('stable fixed points') == 0 or h.get('has a self-feeding loop')
            if ok:
                cleared.append(h['model'])
    exceptions = [m for m in cand if m not in cleared]
    out = {
        'models': len(auto),
        'candidates on the unfiltered sign graph': cand,
        'cleared by the hand check (holdout_handcheck.json, one reader)': cleared,
        'exceptions': exceptions,
        'clocks': sum(1 for m in auto if 'oscillating' in D[m]['behaviours']),
        'memories': sum(1 for m in auto if 'multistable' in D[m]['behaviours']),
    }
    for g, label in labels.items():
        out[f'{g} groups'] = len(members(label, auto))
    if leaked:
        out['leaked removed'] = len([m for m in auto if m not in set(leaked)])
    return out


def gain_recount(s: str, labels: dict[str, dict[str, str]], leaked: Sequence[str]) -> dict[str, Any]:
    pre = PREFIX[s]
    S = {r['model']: r for r in jl(RES / f'{pre}structure_traj.jsonl')}
    T = jd(RES / ('truth_tests.json' if s == 'r31' else 'holdout_truth_tests.json'))
    rings = [r for r in T['gain_brake'] if r.get('status') == 'ok' and r.get('G') is not None]
    single = [r for r in rings if S[r['model']]['defs']['thomas']['c'] == 1]
    called = [
        r['model']
        for r in single
        if (r['ticks'] and r['G'] > r['threshold']) or (not r['ticks'] and r['G'] < r['threshold'])
    ]
    out = {'single rings as drawn': len(single), 'called': len(called), 'models': sorted(r['model'] for r in single)}
    for g, label in labels.items():
        reps = one_per_group(label, [r['model'] for r in single])
        out[f'one per {g} group'] = {'rings': len(reps), 'called': sum(1 for m in reps if m in called)}
    if leaked:
        kept = [r['model'] for r in single if r['model'] not in set(leaked)]
        out['leaked removed'] = {'rings': len(kept), 'called': sum(1 for m in kept if m in called)}
    return out


def atlas_recount(s: str, labels: dict[str, dict[str, str]], leaked: Sequence[str]) -> dict[str, Any]:
    F = jd(RES / ('fingerprints.json' if s == 'r31' else 'holdout_fingerprints.json'))
    filed = {m['model']: m['row'] for m in F['models'] if m.get('status') == 'ok' and m.get('row') != 'flat'}

    def rows_of(ms: Sequence[str]) -> dict[str, Any]:
        c = counter(filed[m] for m in ms)
        return {
            'filed': len(ms),
            'rows': c,
            'follows share': share(c.get('follows', 0), len(ms)),
            'ticks share': share(c.get('ticks', 0), len(ms)),
        }

    out = {'as published': rows_of(sorted(filed))}
    for g, label in labels.items():
        out[f'one per {g} group'] = rows_of(one_per_group(label, filed))
        mem = members(label, filed)
        w = collections.Counter()
        for v in mem.values():
            for m in v:
                w[filed[m]] += 1 / len(v)
        out[f'{g} groups weighted equally'] = {
            'groups': len(mem),
            'follows share': round(w['follows'] / len(mem), 4),
            'ticks share': round(w['ticks'] / len(mem), 4),
        }
    if leaked:
        kept = [m for m in sorted(filed) if m not in set(leaked)]
        out['leaked removed'] = rows_of(kept)
        out['leaked removed, one per publication group'] = rows_of(one_per_group(labels['publication'], kept))
    return out


def speed_order_recount(labels: dict[str, dict[str, str]]) -> dict[str, Any]:
    N = jd(RES / 'nesting.json')['census']
    usable = [
        r
        for r in N['models']
        if r.get('faster_transit') in ('amplifying', 'braking') and not r['forced'] and r['behaviours']
    ]

    def table(rs: Sequence[dict]) -> dict[str, Any]:
        a = sum(1 for r in rs if r['faster_transit'] == 'amplifying' and r['keeps_time'])
        b = sum(1 for r in rs if r['faster_transit'] == 'amplifying' and not r['keeps_time'])
        c = sum(1 for r in rs if r['faster_transit'] == 'braking' and r['keeps_time'])
        d = sum(1 for r in rs if r['faster_transit'] == 'braking' and not r['keeps_time'])
        return {
            'amplifying faster: keeps time / does not': [a, b],
            'braking faster: keeps time / does not': [c, d],
            'fisher one-sided p': round(fisher_greater(a, b, c, d), 4),
        }

    out = {
        'published (nesting.json census.transit_time)': N['transit_time']['fisher_one_sided_p'],
        'recomputed': table(usable),
    }
    assert out['recomputed']['fisher one-sided p'] == N['transit_time']['fisher_one_sided_p'], (
        'speed-order p does not reproduce'
    )
    by = {r['model']: r for r in usable}
    for g, label in labels.items():
        out[f'one per {g} group'] = table([by[m] for m in one_per_group(label, by)])
    return out


# ---------------------------------------------------------------- assumptions and their history
def git(*args: str) -> str:
    try:
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # no git: say so in the record
        return f'git unavailable: {e!r}'[:120]


def first_commit_with(text: str, path: str) -> dict[str, str] | None:
    lines = git(
        'log', '--reverse', '--format=%h|%ad|%s', '--date=format:%Y-%m-%d %H:%M', f'-S{text}', '--', path
    ).splitlines()
    if not lines or '|' not in lines[0]:
        return None
    h, d, s = lines[0].split('|', 2)
    return {'commit': h, 'date': d, 'subject': s[:90], 'commits touching it': len(lines)}


def first_commit_of(path: str) -> dict[str, str] | None:
    lines = git('log', '--reverse', '--format=%h|%ad', '--date=format:%Y-%m-%d %H:%M', '--', path).splitlines()
    if not lines or '|' not in lines[0]:
        return None
    h, d = lines[0].split('|', 1)
    return {'commit': h, 'date': d}


def where(path: str, pattern: str) -> str | None:
    """file:line of the first line matching pattern, read now (line numbers move when the code moves)."""
    p = ROOT / path
    if not p.exists():
        return None
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if re.search(pattern, line):
            return f'{path}:{i}'
    return None


# (choice, value, file, line pattern, git -S text, results file it shapes, why, documented evidence, documented timing)
ASSUMPTIONS: list[tuple[str, str, str, str, str, str, str, str, str]] = [
    (
        'behaviour read at the published rates and starts',
        'curated parameters; own start + 11 spread across its conservation class',
        'analysis/dynamics.py',
        r'^STARTS = ',
        'STARTS = 12',
        'results/r31_dynamics.jsonl',
        'the curated model as published is the object under test; spread starts look for memory',
        '',
        'unknown',
    ),
    (
        'twelve starts per model',
        '12',
        'analysis/dynamics.py',
        r'^STARTS = ',
        'STARTS = 12',
        'results/r31_dynamics.jsonl',
        'enough starts to find a second resting state in small models',
        '',
        'unknown',
    ),
    (
        'run horizons',
        '100, 1,000, 10,000, 100,000 time units',
        'analysis/dynamics.py',
        r'^HORIZONS = ',
        'HORIZONS = (1e2, 1e3, 1e4, 1e5)',
        'results/r31_dynamics.jsonl',
        'a run that has not settled by 1e5 is called unsettled (most of the unlabelled models)',
        '',
        'unknown',
    ),
    (
        'signs read at five moments',
        "t = 0, 1, 10, 100, 1000 on the model's own run",
        'analysis/loops.py',
        r'contexts = \[\(t, None\) for t in \(0, 1, 10, 100, 1000\)\]',
        '(0, 1, 10, 100, 1000)',
        'results/r31_structure_traj.jsonl',
        "an arrow's sign where the model actually goes; random states are the check (tables_random.json)",
        'holdout_handcheck.json: three hold-out clocks have a brake that five moments missed and a '
        '600-point reading found',
        'unknown',
    ),
    (
        'loop search budget',
        '5,000,000 search steps or 20,000 loops per enumeration',
        'analysis/loops.py',
        r'^CIRCUIT_CAP = ',
        '5_000_000',
        'results/r31_structure_traj.jsonl',
        'a count, not a clock, so a rerun lists the same loops',
        '',
        'unknown',
    ),
    (
        '"runs on its own"',
        'no events and no time in a rate law, rule or function definition',
        'analysis/dynamics.py',
        r'^def forced',
        'AST_NAME_TIME',
        'results/r31_dynamics.jsonl',
        'the sign-rule theorems are about autonomous systems; a forcing input is outside them',
        '',
        'unknown',
    ),
    (
        'negative self-loops dropped (decay), except end-product inhibition',
        'kept only where production slows as the species rises',
        'analysis/loops.py',
        r'Self-loops: a negative self-loop is kept only',
        'reference 24 omits negative self-loops',
        'results/r31_structure_traj.jsonl',
        'follows reference 24 (Baudier, Fages and Soliman 2018)',
        '',
        'unknown',
    ),
    (
        'filters applied to braking loops',
        'the Cor. 2.3 to 2.5 filters, proved for amplifying loops, also applied to brakes',
        'analysis/README.md',
        r'Braking loops are filtered the same way',
        'Braking loops are filtered the same way',
        'results/tables_traj.json',
        'one reading for every loop; tabulate.py also reports the split with brakes as drawn',
        'HANDOFF.md backlog item 4, written after the census: "Open: whether braking loops are counted before or after the '
        'filters"; the first address test was void because the filters remove the brake of 10 clocks',
        'after',
    ),
    (
        'running total, strict',
        'a variable whose own value appears in none of the rate laws that change it',
        'analysis/loops.py',
        r'structural integrators: the variable',
        'structural integrators',
        'results/r31_structure_traj.jsonl',
        'read from the equations, no threshold',
        '',
        'unknown',
    ),
    (
        'running total, loose',
        'own level moves its net rate by less than 0.1 of the flow through it',
        'analysis/integrators.py',
        r'^R_CUT = ',
        'R_CUT = 0.1',
        'results/r31_integrators.jsonl',
        'a near-integrator, read at the last state reached',
        '',
        'unknown',
    ),
    (
        'running total, paired',
        'a weighted sum of two variables whose rate depends on neither (rank test, tolerance 1e-4)',
        'analysis/integrators.py',
        r'^PAIR_TOL = ',
        'PAIR_TOL',
        'results/r31_integrators.jsonl',
        "Khammash's antithetic controller keeps its total this way",
        'HANDOFF.md: added on branch running-total-pairs after the strict and loose counts were reported',
        'after',
    ),
    (
        'step, moved, exact (truth tests)',
        'step 20%; moved = peak over 5%; exact = back within 0.5%',
        'analysis/truth_tests.py',
        r'^STEP, MOVE, BACK, OTHERS = ',
        'STEP, MOVE, BACK, OTHERS = 0.2, 0.05, 0.005, 0.05',
        'results/truth_tests.json',
        'a push big enough to read, small enough to stay near the resting state',
        'trace_four.json (2026-11-16): at one part in a million 9 of the 22 exact returns hold, 2 of the 4 small ones; the '
        'essay now names 0.5% as the census tolerance',
        'unknown',
    ),
    (
        'atlas: step, moved, exact, memory gap, 40 parameters',
        '0.2, 0.05, 0.005, 0.05; first 40 global parameters by name',
        'analysis/fingerprints.py',
        r'^STEP, MOVE, BACK, MEMORY = ',
        'MAX_PARAMS = 40',
        'results/fingerprints.json',
        "the truth tests' thresholds reused; 40 parameters bound the run time",
        'HANDOFF.md, the atlas: "Two earlier runs were wrong and fixed" (reading only the biggest pair; an unsettled tail '
        'read as ticking and an unsettled ramp as memory)',
        'after',
    ),
    (
        'robust return: redrawn rates',
        '5 redraws, each rate times 10^U(-0.15, 0.15); robust if at least 3 settle and all return',
        'analysis/robust_return.py',
        r'uniform\(-0\.15, 0\.15\)',
        'uniform(-0.15, 0.15)',
        'results/robust_return.json',
        'integral control returns exactly whatever the rates are; a coincidence does not survive a redraw',
        '',
        'unknown',
    ),
    (
        'wall-clock safety net',
        '6 hours per model, every step; no record depends on it',
        'analysis/budget.py',
        r'^SAFETY_NET_S = ',
        'SAFETY_NET_S = 6 * 3600',
        'results/',
        'stops a runaway only; every limit that decides a record counts work, so a rerun on any machine files the same',
        'replaced wall-clock caps (1,200 s loops, 900 s dynamics, 240 s atlas and running totals, 300 and 600 s truth '
        'tests, 600 s robust return) that flipped records between reruns of identical code (2026-11-19)',
        'after',
    ),
    (
        'work budget: dynamics',
        '3e10 derivative evaluations of solver work per model',
        'analysis/dynamics.py',
        r'^WORK_BUDGET = ',
        'WORK_BUDGET = 3e10',
        'results/r31_dynamics.jsonl',
        'a count, not a clock; above the most any model that finished in the committed run spends (1.17e10)',
        'measured alone 2026-11-19 on the 28 models that took 88 s or more in the committed run',
        'after',
    ),
    (
        'work budget: truth tests',
        '1.1e11 derivative evaluations of solver work per test and model',
        'analysis/truth_tests.py',
        r'^WORK_BUDGET = ',
        'WORK_BUDGET = 1.1e11',
        'results/truth_tests.json',
        'a count, not a clock; the old 600 s cap at the fastest rate measured (1.7e8 a second), so no record that finished under it can run out',
        '',
        'after',
    ),
    (
        'work budget: atlas',
        '4.1e10 derivative evaluations of solver work per model',
        'analysis/fingerprints.py',
        r'^WORK_BUDGET = ',
        'WORK_BUDGET = 4.1e10',
        'results/fingerprints.json',
        'a count, not a clock; the old 240 s cap at the fastest rate measured (1.7e8 a second), so no record that finished under it can run out',
        'HANDOFF.md, the atlas evening: load average 27 to 66 (the old 240 s cap timed out seven models)',
        'after',
    ),
    (
        'work budget: robust return',
        '1.1e11 derivative evaluations of solver work per model',
        'analysis/robust_return.py',
        r'^WORK_BUDGET = ',
        'WORK_BUDGET = 1.1e11',
        'results/robust_return.json',
        'a count, not a clock; the old 600 s cap at the fastest rate measured (1.7e8 a second), so no record that finished under it can run out',
        '',
        'after',
    ),
    (
        'families of one system (truth tests)',
        'six families named by hand',
        'analysis/truth_tests.py',
        r'^FAMILIES = \{',
        'FAMILIES = {',
        'results/truth_tests.json',
        'models of one system at different detail, chosen by name',
        'chosen from the census five days after its results were committed (2e2919f, 2026-10-20)',
        'after',
    ),
    (
        'address test protocol and its amendment',
        'leave-one-out majority vote, 10,000 shuffles inside sign strata; amended: sign bits from the unfiltered graph',
        'analysis/address_predicts.py',
        r'^N_SHUFFLES, SEED = ',
        'AMENDMENT',
        'results/address_predicts.json',
        'fail line written first',
        'proto/PROGRESS.md: protocol written 09:46:55 before any address-by-answer table; first run VOID; amendment written '
        '09:48:12, after the void and before the rerun',
        'before (protocol); after (amendment, after the void)',
    ),
    (
        'hold-out fail lines',
        'sign rules, strength, six answers (follows over half), blank squares, the address',
        'analysis/holdout_score.py',
        r'^Definitions, fixed before',
        '111 / 273',
        'results/holdout_score.json',
        'scored against lines frozen before the hold-out was read',
        'HANDOFF.md: "Fail lines were fixed that morning before any new data was read"; the follows line (over half) was '
        'set knowing release 31 had 41%',
        'before',
    ),
]


def assumptions() -> list[dict[str, Any]]:
    out = []
    for choice, value, path, pat, s_text, shaped, why, doc, doc_timing in ASSUMPTIONS:
        intro = first_commit_with(s_text, path)
        res = first_commit_of(shaped)
        if intro is None or res is None:
            git_verdict = 'unknown (no git record)'
        elif intro['commit'] == res['commit']:
            git_verdict = 'unknown: entered git in the same commit as the results it shapes'
        elif intro['date'] > res['date']:
            git_verdict = 'after: entered git after the results file existed'
        else:
            git_verdict = 'before: entered git before the results file existed'
        timing = doc_timing if doc_timing != 'unknown' else git_verdict.split(':')[0]
        out.append(
            {
                'choice': choice,
                'value': value,
                'where': where(path, pat),
                'why': why,
                'entered git': intro,
                'results file first committed': {shaped: res},
                'set before or after results (git)': git_verdict,
                'documented': doc or 'none found',
                'set before or after results': timing,
            }
        )
    return out


# ---------------------------------------------------------------- headline moves
COLUMNS = [
    'one per publication group',
    'one per lineage group',
    'one per lab group',
    'leave one lineage group out',
    'leaked removed',
]


def moves(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """Each headline beside its recounts: one model per group (publication, lineage, author-year, lab), leave one group
    out, and for the hold-out the leaked models removed."""
    out = []

    def norm(k: str) -> str:
        return k.replace('one model per', 'one per').replace(' groups weighted equally', ' groups weighted')

    def add(name: str, published: Any, variants: dict[str, Any]) -> None:
        v = {norm(k): x for k, x in variants.items()}
        nums = [x for x in v.values() if isinstance(x, (int, float))]
        out.append(
            {
                'headline': name,
                'published': published,
                'recounts': v,
                'largest move': round(max((abs(x - published) for x in nums), default=0), 4),
            }
        )

    for s, lab in (('r31', 'release 31'), ('holdout', 'hold-out')):
        A = {
            k: v
            for k, v in rec['address test'][s].items()
            if isinstance(v, dict) and not k.startswith(('published', 'recomputed'))
        }
        pub = rec['address test'][s]['published (address_predicts amended_primary)']
        add(
            f'address test, {lab}: square accuracy',
            pub['accuracy']['address'],
            {k: v['accuracy']['address'] for k, v in A.items()},
        )
        add(
            f'address test, {lab}: sign-rule accuracy',
            pub['accuracy']['sign'],
            {k: v['accuracy']['sign'] for k, v in A.items()},
        )
        add(f'address test, {lab}: p', pub['p'], {k: v['p'] for k, v in A.items()})
        add(f'address test, {lab}: models', pub['n'], {k: v['n'] for k, v in A.items()})
        R = rec['atlas rows'][s]
        add(
            f'atlas, {lab}: follows share',
            R['as published']['follows share'],
            {k: v['follows share'] for k, v in R.items() if k != 'as published'},
        )
        G = rec['gain'][s]
        add(
            f'gain, {lab}: single rings called',
            f"{G['called']} of {G['single rings as drawn']}",
            {k: f"{v['called']} of {v['rings']}" for k, v in G.items() if isinstance(v, dict)},
        )
        SR = rec['sign rules'][s]
        add(
            f'sign rules, {lab}: exceptions in models',
            f"{len(SR['exceptions'])} in {SR['models']}",
            {
                f'one per {k[:-7]} group': f"{len(SR['exceptions'])} in {v}"
                for k, v in SR.items()
                if k.endswith(' groups')
            }
            | (
                {'leaked removed': f"{len(SR['exceptions'])} in {SR['leaked removed']}"}
                if 'leaked removed' in SR
                else {}
            ),
        )
    so = rec['speed order']
    add(
        'speed order: Fisher p (11 of 16 against 4 of 9)',
        so['published (nesting.json census.transit_time)'],
        {k: v['fisher one-sided p'] for k, v in so.items() if k.startswith('one per')},
    )
    return out


def verdicts(rec: dict[str, Any]) -> dict[str, Any]:
    """Each test's pass or fail as published and under every recount, by the test's own line."""
    out: dict[str, Any] = {}
    for s, lab in (('r31', 'release 31'), ('holdout', 'hold-out')):
        A = {k: v['verdict'] for k, v in rec['address test'][s].items() if isinstance(v, dict) and 'verdict' in v}
        out[f'address test, {lab} (FAIL if p >= 0.05, lead under 5 points, or size does as well)'] = A
        R = rec['atlas rows'][s]
        out[f'follows line, {lab} (FAIL if follows share > 1/2)'] = {
            k: ('FAIL' if v['follows share'] > 0.5 else 'PASS') for k, v in R.items()
        }
        SR = rec['sign rules'][s]
        out[f'sign rules, {lab} (FAIL if an exception survives)'] = (
            'FAIL' if SR['exceptions'] else 'PASS (exceptions cannot rise when models are dropped)'
        )
        G = rec['gain'][s]
        out[f'gain, {lab} (every single ring called)'] = {
            k: ('PASS' if v['called'] == v['rings'] else 'MISS') for k, v in G.items() if isinstance(v, dict)
        }
    so = rec['speed order']
    out['speed order (significant if p < 0.05)'] = {
        k: ('significant' if v['fisher one-sided p'] < 0.05 else 'not significant')
        for k, v in so.items()
        if isinstance(v, dict)
    }
    return out


# ---------------------------------------------------------------- the datasheet
def datasheet(a: dict[str, Any]) -> str:
    """results/DATASHEET.md, every number read from the audit dict."""
    f31, fho = a['funnel']['r31'], a['funnel']['holdout']
    ck, lic, imb, dup, lk, rc = (
        a['checksums'],
        a['licence'],
        a['imbalance'],
        a['duplicates'],
        a['leakage'],
        a['grouped recounts'],
    )

    def n(d: dict[str, Any], k: str) -> int:
        return d[k]['n']

    def pct(x: float) -> str:
        return f'{100 * x:.1f}%'

    def top(sp: dict[str, Any], k: int = 3) -> str:
        return ', '.join(f'{x} {c}' for x, c in list(sp['counts'].items())[:k])

    def kv(d: dict[str, Any]) -> str:
        return ', '.join(f'{v} {k}' for k, v in d.items())

    fol, tk = imb['r31']['follows'], imb['r31']['ticks']
    folh = imb['holdout']['follows']
    tv, tvh = (
        fol['system mix distance from all filed models, by row (TVD)'],
        folh['system mix distance from all filed models, by row (TVD)'],
    )
    is_min = [min(t, key=t.get) == 'follows' for t in (tv, tvh)]
    closest = (
        'In both sets it is the row closest to the whole.'
        if all(is_min)
        else 'It is the row closest to the whole in '
        + ' and '.join(x for x, m in zip(('release 31', 'the hold-out'), is_min) if m)
        + '.'
        if any(is_min)
        else 'It is not the row closest to the whole.'
    )
    forced_key = 'forced (events, or time in a rate law, rule or function)'
    sh = a['shift']
    L: list[str] = []
    w = L.append
    w('# Datasheet: the BioModels census behind "Every line is a loop"\n')
    w(
        'Generated by `analysis/data_audit.py`. Every number below is read from `results/data_audit.json` (key in brackets) '
        'or from the results file named beside it. Rerun the script to refresh both.\n'
    )
    vd = a['verdicts under grouping']
    fl = vd['follows line, hold-out (FAIL if follows share > 1/2)']
    flips = [k for k, v in fl.items() if v != fl['as published']]
    addr_all = [
        v
        for k in vd
        if k.startswith('address test')
        for kk, v in vd[k].items()
        if not kk.startswith(('published', 'recomputed'))
    ]
    w('In short:')
    w('')
    w(
        f'- {f31["files on disk"]} release 31 models narrow to {n(f31, "match a behaviour label (behaviours not empty)")} with a '
        f'behaviour label and {n(f31, "atlas filed in a row")} filed in the atlas; the {fho["files on disk"]}-model hold-out narrows '
        f'to {n(fho, "match a behaviour label (behaviours not empty)")} and {n(fho, "atlas filed in a row")}.'
    )
    w(f'- {lk["leaked"]["n"]} hold-out models are tied to a release 31 model by derivation, publication or authorship.')
    w(
        f'- Counting one model per group changes no address-test verdict ({addr_all.count("FAIL")} of {len(addr_all)} recounts with a '
        f'verdict FAIL, as published) and no sign-rule or gain verdict. The hold-out "follows" line fails by one model as published; it passes in '
        f'{len(flips)} of {len(fl) - 1} recounts ({"; ".join(flips)}) [verdicts under grouping].'
    )
    w('')
    w('## 1. Source\n')
    w(
        f'- Release 31 of BioModels, dated {ck["release 31 date (get_biomodels.sh URL)"]}, one archive from the EBI FTP '
        f'(`BioModels_Database-r31_pub-sbml_files.tar.bz2`). SHA-256 `{ck["release 31 archive sha256 expected (get_biomodels.sh)"]}`, '
        f'pinned in `analysis/get_biomodels.sh`; the archive on disk {"matches" if ck["release 31 archive matches"] else "DOES NOT MATCH"} '
        '[checksums].'
    )
    w(
        f'- The census reads its {f31["files on disk"]} curated SBML files (`data/r31_curated/`) [funnel.r31."files on disk"].'
    )
    hl = a['holdout list']
    w(
        f'- The hold-out was listed on {hl["read"]}: BioModels showed {hl["curated today"]} manually curated models, '
        f'{hl["curated not in release 31"]} of them not in release 31, {hl["not SBML"]} of those not SBML, leaving '
        f'{fho["files on disk"]} files fetched one at a time through the BioModels API (`analysis/get_holdout.py`, '
        f'`results/holdout_ids.json`) [holdout list]. Each file has a SHA-256 in `results/holdout_manifest.json`; '
        f'{ck["holdout files checked against holdout_manifest.json"]} were rehashed for this datasheet and '
        f'{len(ck["holdout files that differ"])} differ [checksums]. None of release 31\'s models is missing from today\'s list '
        f'({hl["release 31 missing today"]}).'
    )
    w('')
    w('## 2. Licence\n')
    for s, lab in (('r31', 'Release 31'), ('holdout', 'Hold-out')):
        x = lic[s]
        w(
            f'- {lab}: of {x["files"]} files, {x["notes name CC0 or public domain"]} carry a CC0 public-domain dedication in their '
            f'notes, {x["notes say copyright (c) The BioModels Team, see terms of use"]} carry the older notice "copyright (c) '
            f'The BioModels Team" with a link to the terms of use, and {x["neither notice"]} carry neither [licence.{s}].'
        )
    w(
        '- The files do not all say CC0. BioModels\' terms page was not opened for this audit, so "BioModels terms: CC0" '
        'rests on the files that say so and is otherwise unverified.'
    )
    w('')
    w('## 3. How it was collected\n')
    w(
        '- Modellers chose what to publish. BioModels curators chose what to curate and checked each model against its paper.'
    )
    w(
        '- Release 31 is a snapshot of that library in 2017. The hold-out is what curators added afterwards, read in 2026.'
    )
    w('- No model was edited. Every script runs on the files as downloaded.')
    w('')
    w('## 4. Pipeline, step by step\n')
    w(
        'The hold-out runs the same scripts byte for byte (`analysis/run_holdout.sh`, after six release 31 models reproduce).'
    )
    w('')
    w('| step | what happens | script | release 31 | hold-out | count read from |')
    w('|---|---|---|---|---|---|')
    steps = [
        (
            'raw download',
            'archive or API, checksums',
            'get_biomodels.sh, get_holdout.py',
            f31['files on disk'],
            fho['files on disk'],
            'data folders; holdout_ids.json',
        ),
        (
            'parsing',
            'libSBML reads the file, libRoadRunner compiles it',
            'loops.py',
            n(f31, 'read as equations (status ok)'),
            n(fho, 'read as equations (status ok)'),
            '*_structure_traj.jsonl status "ok"',
        ),
        (
            'sign reading',
            'arrow signs at t = 0, 1, 10, 100, 1000',
            'loops.py',
            n(f31, 'read as equations (status ok)'),
            n(fho, 'read as equations (status ok)'),
            'same records',
        ),
        (
            'loop listing and filters',
            'every loop listed within budget, Baudier et al. filters',
            'loops.py, elim.py',
            n(f31, 'every loop listed (defs.ref24_rank.complete)'),
            n(fho, 'every loop listed (defs.ref24_rank.complete)'),
            'defs.ref24_rank.complete',
        ),
        (
            'one to three loops',
            'the table\'s rows',
            'loops.py',
            n(f31, 'one to three loops'),
            n(fho, 'one to three loops'),
            'defs.ref24_rank.c in 1..3',
        ),
        (
            'running totals',
            'strict (in the loop listing), loose and paired',
            'loops.py, integrators.py',
            n(f31, 'running-total records (integrators.py)'),
            n(fho, 'running-total records (integrators.py)'),
            '*_integrators.jsonl (one record per model read)',
        ),
        (
            'runs on its own',
            'no events, no time in the math',
            'dynamics.py',
            n(f31, 'run on their own (status ok, forced false)'),
            n(fho, 'run on their own (status ok, forced false)'),
            '*_dynamics.jsonl forced false',
        ),
        (
            'behaviour labels',
            'twelve runs at published rates',
            'dynamics.py',
            n(f31, 'match a behaviour label (behaviours not empty)'),
            n(fho, 'match a behaviour label (behaviours not empty)'),
            'behaviours not empty; truth_tests rules.autonomous',
        ),
        (
            'table placement',
            'rows one to three, strict reading',
            'tabulate.py',
            n(f31, 'one to three loops'),
            n(fho, 'one to three loops'),
            'tables_traj.json defs.ref24_rank.rows',
        ),
        (
            'atlas read',
            'settled, then pushed',
            'fingerprints.py',
            n(f31, 'atlas read (status ok)'),
            n(fho, 'atlas read (status ok)'),
            'fingerprints.json models[].status',
        ),
        (
            'atlas filed',
            'one of six rows',
            'fingerprints.py',
            n(f31, 'atlas filed in a row'),
            n(fho, 'atlas filed in a row'),
            'fingerprints.json rows',
        ),
        (
            'tests: sign rules',
            'no clock without a brake, no memory without a self-feeding loop',
            'truth_tests.py',
            rc['sign rules']['r31']['models'],
            rc['sign rules']['holdout']['models'],
            'truth_tests.json rules.autonomous',
        ),
        (
            'tests: address',
            'does the square predict the atlas row',
            'address_predicts.py',
            n(f31, 'address test scope (1 to 3 loops)'),
            n(fho, 'address test scope (1 to 3 loops)'),
            'address_predicts.json amended_primary.n',
        ),
    ]
    for r in steps:
        w('| ' + ' | '.join(str(x) for x in r) + ' |')
    w('')
    w('## 5. Exclusions, named as the code names them\n')
    for s, f, lab in (('r31', f31, 'Release 31'), ('holdout', fho, 'Hold-out')):
        nr = ', '.join(
            f'{v["n"]} with status "error" ("{k[7:]}")' if k.startswith('error: ') else f'{v["n"]} "{k}"'
            for k, v in f['not read, by status'].items()
        )
        w(
            f'- {lab}, not read ({f["files on disk"] - n(f, "read as equations (status ok)")}): {nr} [funnel.{s}."not read, by status"].'
        )
        w(
            f'- {lab}, loop search unfinished at 5,000,000 steps or 20,000 loops: '
            f'{n(f, "loop search unfinished (5,000,000 steps or 20,000 loops)")} (`defs.ref24_rank.complete` false).'
        )
        w(
            f'- {lab}, not on their own ({n(f, "read as equations (status ok)") - n(f, "run on their own (status ok, forced false)")}): '
            f'{n(f, forced_key)} forced ({kv(f[forced_key]["why"])}); '
            f'{n(f, "dynamics status budget (solver work spent)")} spent the dynamics work budget; '
            f'{n(f, "dynamics status error")} dynamics error{" (" + ", ".join(f["dynamics status error"]["models"]) + ")" if f["dynamics status error"]["models"] else ""} [funnel.{s}].'
        )
        u = f['run on their own with no behaviour label']
        w(
            f'- {lab}, run on their own with no behaviour label: {u["n"]}. In all twelve runs: '
            f'{kv(u["what the twelve runs ended as (dynamics.runs)"])} (`dynamics.runs`). No run settled, ticked or ran away.'
        )
        st = kv({k: v for k, v in f['atlas status'].items() if k != 'ok'})
        w(
            f'- {lab}, atlas not read: {st}; then {n(f, "atlas flat (no 20% step moves any molecule by 5%)")} flat '
            '("no 20% step moves any molecule by 5%") [funnel.' + s + '."atlas status"].'
        )
    w('')
    w('## 6. Class balance and missingness\n')
    w(
        f'- Atlas rows, release 31: {kv(f31["atlas filed in a row"]["rows"])}. Hold-out: {kv(fho["atlas filed in a row"]["rows"])}.'
    )
    w(
        f'- Behaviour labels, release 31 (models showing each): {kv(imb["r31"]["labelled"]["behaviour label (models showing it)"])}.'
    )
    w(
        f'- The {tk["n"]} ticking models by system: {top(tk["system"], 5)}; by first author: {top(tk["first author"], 5)}. '
        f'{tk["started by the push, not before"]} tick only after the push [imbalance.r31.ticks].'
    )
    for s, lab in (('r31', 'Release 31'), ('holdout', 'Hold-out')):
        rd = imb[s]['read']
        fa = rd['first author (name)']
        w(
            f'- {lab}, the {rd["n"]} read models. Organism: {top(rd["organism"], 4)}. System: {top(rd["system (keyword map)"], 4)}. '
            f'Decade of the paper: {top(rd["publication decade (name)"], 3)}. First authors: {fa["distinct"]} names, the most '
            f'frequent {fa["top"]} with {fa["counts"][fa["top"]]} [imbalance.{s}.read].'
        )
    w(
        f'- "Follows" holds {fol["n"]} of {n(f31, "atlas filed in a row")} filed models ({pct(fol["share of filed"])}) and '
        f'{folh["n"]} of {n(fho, "atlas filed in a row")} in the hold-out ({pct(folh["share of filed"])}). Every member carries one '
        f'reason in the file, "{next(iter(fol["why (fingerprints.json models[].why)"]))}": it is the filing order\'s last branch, '
        'reached when nothing else is found.'
    )
    w(
        f'- Its members look like the whole library. Its system mix sits {tv["follows"]:.2f} from all filed models (total variation '
        f'distance; ticks {tv["ticks"]:.2f}, rings {tv["rings"]:.2f}); in the hold-out {tvh["follows"]:.2f}. '
        f'{closest} Inside it, '
        f'{fol["final shift at least 95% of peak"]} of {fol["n"]} end at 95% or more of their peak shift, and '
        f'{fol["overshoots (crossings)"].get("0", 0)} never overshoot: one plain shape, a monotone shift that stays. '
        f'{fol["loop address"].get("(0, 0, 0)", 0)} have no loop at all and {fol["loop address"].get("none (4+ loops or unfinished)", 0)} '
        'have four or more or an unfinished search. So "follows" is a leftover bin whose members share one shape, not a class '
        'with its own kind of circuit [imbalance.r31.follows].'
    )
    mt = {s: imb[s]['read']['organism']['counts'].get('none declared', 0) for s in ('r31', 'holdout')}
    my = {
        s: imb[s]['read']['publication decade (name)']['counts'].get('no year in name', 0) for s in ('r31', 'holdout')
    }
    w(
        f'- Missing: no taxon declared in {mt["r31"]} release 31 and {mt["holdout"]} hold-out models; no year in the name in '
        f'{my["r31"]} and {my["holdout"]}; the keyword map leaves {imb["r31"]["read"]["system (keyword map)"]["counts"].get("other", 0)} '
        f'and {imb["holdout"]["read"]["system (keyword map)"]["counts"].get("other", 0)} as "other".'
    )
    w('')
    w('## 7. Duplicates and families\n')
    w('Pairs found across both sets [duplicates."pairs by kind (both sets)"]:')
    w('')
    for k, v in dup['pairs by kind (both sets)'].items():
        w(f'- {k}: {v}')
    w('')
    w('Groups, nested, each adding one kind of evidence to the one before [duplicates.groups]:')
    w('')
    w(
        '| grouping | adds | release 31 groups (of models read) | in groups of 2+ | hold-out groups | largest release 31 group |'
    )
    w('|---|---|---|---|---|---|')
    adds = {
        'publication': 'copies, same equations, same isDescribedBy, version in the name, truth-test families',
        'lineage': 'declared derivation (isDerivedFrom)',
        'author-year': 'same first author and year',
        'lab': 'same first author',
    }
    for g in ('publication', 'lineage', 'author-year', 'lab'):
        r, h = dup['groups']['r31'][g], dup['groups']['holdout'][g]
        big = r['largest'][0] if r['largest'] else {'size': 1, 'names': ['']}
        w(
            f'| {g} | {adds[g]} | {r["groups"]} of {r["models"]} | {r["models in groups of 2 or more"]} | {h["groups"]} of {h["models"]} '
            f'| {big["size"]}: {big["names"][0][:40]} |'
        )
    w('')
    w('## 8. Hold-out independence\n')
    w(
        f'- {lk["leaked"]["n"]} of {lk["leaked"]["of"]} hold-out models are tied to a release 31 model: '
        f'{kv({k: v["n"] for k, v in lk["by kind"].items()})} (a model can have several) [leakage.leaked].'
    )
    w(
        f'- {lk["same first author as a release 31 model (not removed)"]["n"]} more share only a first author with release 31; '
        'they are reported, not removed.'
    )
    sb = lk['submitted before release 31 (holdout_ids.json submitted)']
    w(
        f'- {sb["n"]} hold-out models were submitted before {sb["release 31"]} and curated later, so "since release 31" means curated '
        'since, not published since.'
    )
    w(
        f'- The mix moved (total variation distance, hold-out against release 31): system {sh["read: system (keyword map)"]["tvd"]}, '
        f'organism {sh["read: organism"]["tvd"]}, decade {sh["read: publication decade (name)"]["tvd"]}, loop count '
        f'{sh["read: loop count (defs.ref24_rank.c)"]["tvd"]}, behaviour {sh["labelled: behaviour signature (as tabulate.py)"]["tvd"]}, '
        f'atlas row {sh["filed: atlas row"]["tvd"]} [shift]. Median species {sh["size, r31"]["species (structure)"]["median"]} against '
        f'{sh["size, holdout"]["species (structure)"]["median"]}; models written as rules with no reactions '
        f'{sh["size, r31"]["no reactions (written as rules)"]} against {sh["size, holdout"]["no reactions (written as rules)"]}.'
    )
    w('')
    w('## 9. Headline numbers recounted by group\n')
    w(
        'One model per group keeps the lowest BioModels id of each group. Leave one group out keeps every model but predicts '
        'each only from other groups. The address test uses its own code and seed; it was reproduced exactly first '
        f'(release 31 {rc["address test"]["r31"]["reproduces"]}, hold-out {rc["address test"]["holdout"]["reproduces"]}).'
    )
    w('')
    w('| headline | published | ' + ' | '.join(COLUMNS) + ' |')
    w('|---|---|' + '---|' * len(COLUMNS))
    for m in a['headline moves']:
        cells = [m['recounts'].get(c, m['recounts'].get(c.replace('one per', 'one model per'), '')) for c in COLUMNS]
        w(f'| {m["headline"]} | {m["published"]} | ' + ' | '.join(str(c) for c in cells) + ' |')
    w('')
    w('All recounts, author-year included, are in [grouped recounts] and [headline moves].')
    w('')
    w('## 10. Where the files disagree\n')
    w(
        f'Every pair of files that should agree was compared: {len(a["cross checks"])} checks, {len(a["disagreements"])} disagree '
        '[cross checks, disagreements].'
    )
    w('')
    for c in a['disagreements']:
        ((ka, va),) = c['a'].items()
        ((kb, vb),) = c['b'].items()
        w(
            f'- {c["what"]}: {ka} gives {va}; {kb} gives {vb}.'
            + (f' {c["note"][0].upper()}{c["note"][1:]}.' if c.get('note') else '')
        )
    noted = [c for c in a['cross checks'] if c['agree'] and c.get('note')]
    for c in noted:
        w(f'- {c["what"]}: the files agree, but {c["note"]}.')
    forced_checks = [c for c in a['cross checks'] if c['what'].startswith('r31: forced flag')]
    w(
        f'- The forced flag was recomputed from the SBML for every release 31 model with a dynamics record; '
        f'{len(forced_checks)} disagree with `r31_dynamics.jsonl`.'
    )
    w('')
    w('## 11. Choices that shape the numbers\n')
    w('| choice | value | where | set before or after results | evidence |')
    w('|---|---|---|---|---|')
    for x in a['assumptions']:
        ev = x['documented'] if x['documented'] != 'none found' else x['set before or after results (git)']
        w(f'| {x["choice"]} | {x["value"]} | `{x["where"]}` | {x["set before or after results"]} | {ev} |')
    w('')
    w('## 12. Known biases\n')
    w(
        '- Selection: modellers publish what worked and what was interesting, and curators curate a subset. Clocks, switches '
        'and famous systems are over-represented. The census cannot say how common a circuit is in cells.'
    )
    w('- Behaviour is read at published rates only. What a model does at other rates is not seen.')
    w(
        '- Some systems are drawn many times (section 7). Counts treat each model as one vote unless recounted by group '
        '(section 9).'
    )
    w('- Names, years, systems and first authors are read from model names by rules in the script, so a few are wrong.')
    w(
        '- Every per-model limit counts work (budget.py), so a slower or busier machine files the same models; a 6-hour '
        'wall-clock safety net only stops a runaway.'
    )
    w('')
    w('## 13. What is not done\n')
    w(
        '- No second reader. One person decided the hold-out hand check of five sign-rule candidates (`holdout_handcheck.json`), '
        'the six truth-test families (`analysis/truth_tests.py` FAMILIES) and the scores of chapter 07\'s squares. The blind '
        'read of 20 "follows" traces is not done (`holdout_score.json` "six answers"."blind read").'
    )
    w(
        '- Exact duplicates are found only when two files declare their parts in the same order; re-encodings of one paper are '
        'caught through the shared publication instead.'
    )
    w(
        '- Publication years come from model names; the papers\' own records were not fetched. Taxon names are from memory.'
    )
    after = [x['choice'] for x in a['assumptions'] if 'after' in x['set before or after results']]
    w(f'- Choices set or kept after results were seen: {len(after)} ({"; ".join(after)}).')
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------- main
def main(jobs: int = 8) -> None:
    sbml = read_all(jobs)
    bad = [m for m, r in sbml.items() if 'read_error' in r]
    assert not bad, f'libSBML could not read {bad[:5]}'
    table = model_table(sbml)
    pairs = link_sets(sbml, table)
    labels_all = groupings(table, pairs)
    lk = leakage(table, pairs)
    leaked = [x['model'] for x in lk['leaked']['models']]
    imb = {s: imbalance(s, table) for s in ('r31', 'holdout')}
    ids = jd(RES / 'holdout_ids.json')
    # pins: this audit's loader, leave-one-group-out and Fisher test must give the published numbers before any recount
    assert address_records('r31') == AP.load()[1], 'address_records no longer matches address_predicts.load'
    for s in ('r31', 'holdout'):
        recs = [r for r in address_records(s) if 1 <= r['address'][0] <= 3]
        signs, keys = predictor_keys(recs)
        ans = [r['answer'] for r in recs]
        assert all(
            logo_accuracy(ans, v, signs, [r['model'] for r in recs]) == AP.loo_accuracy(ans, v, signs)
            for v in keys.values()
        ), f'{s}: leave-one-group-out with one-model groups differs from leave-one-out'
    rec: dict[str, Any] = {
        'sign rules': {
            s: sign_rule_recount(s, labels_all, leaked if s == 'holdout' else []) for s in ('r31', 'holdout')
        },
        'gain': {s: gain_recount(s, labels_all, leaked if s == 'holdout' else []) for s in ('r31', 'holdout')},
        'atlas rows': {s: atlas_recount(s, labels_all, leaked if s == 'holdout' else []) for s in ('r31', 'holdout')},
        'address test': {s: address_tests(s, labels_all, leaked if s == 'holdout' else []) for s in ('r31', 'holdout')},
        'speed order': speed_order_recount(labels_all),
    }
    S31 = [r['model'] for r in jl(RES / 'r31_structure_traj.jsonl') if r.get('status') == 'ok']
    Sho = [r['model'] for r in jl(RES / 'holdout_structure_traj.jsonl') if r.get('status') == 'ok']
    audit: dict[str, Any] = {
        'about': 'analysis/data_audit.py; every count read from the files named in each key',
        'checksums': verify_checksums(),
        'holdout list': {
            'read': ids['read'],
            'curated today': ids['curated_today'],
            'sbml today': ids['sbml_today'],
            'curated not in release 31': ids['curated_not_in_release31'],
            'not SBML': len(ids['not_sbml']),
            'release 31 missing today': len(ids['release31_missing_today']),
        },
        'licence': {
            s: {
                'files': sum(1 for r in sbml.values() if r['set'] == s),
                'notes name CC0 or public domain': sum(1 for r in sbml.values() if r['set'] == s and r['cc0']),
                'notes link a CC BY licence': sum(1 for r in sbml.values() if r['set'] == s and r['notes_say_cc_by']),
                'notes say copyright (c) The BioModels Team, see terms of use': sum(
                    1 for r in sbml.values() if r['set'] == s and r['notes_say_copyright_team']
                ),
                'neither notice': sum(
                    1 for r in sbml.values() if r['set'] == s and not r['cc0'] and not r['notes_say_copyright_team']
                ),
            }
            for s in ('r31', 'holdout')
        },
        'funnel': {s: funnel(s, sbml) for s in ('r31', 'holdout')},
        'cross checks': [],
        'imbalance': imb,
        'keyword map (system)': SYSTEMS,
        'taxon map (names from memory, unverified)': TAXA,
        'duplicates': {
            'pairs by kind (both sets)': {k: len(v) for k, v in pairs.items()},
            'groups': {
                s: {
                    g: group_summary(lab, scope, table, full=g in ('publication', 'lineage'))
                    for g, lab in labels_all.items()
                }
                for s, scope in (('r31', S31), ('holdout', Sho), ('both', S31 + Sho))
            },
            'exact copies': [sorted({a, b}) for a, b in pairs['exact copy (same equations and numbers)']],
            'same equations': [sorted({a, b}) for a, b in pairs['same equations, other numbers']],
            'declared derivations': pairs['declared derivation (isDerivedFrom, or a link to another BioModels entry)'],
            'truth_tests families': {
                k: [m['model'] for m in v] for k, v in jd(RES / 'truth_tests.json')['families'].items()
            },
        },
        'leakage': lk,
        'shift': shift(table, imb),
        'grouped recounts': rec,
        'assumptions': assumptions(),
        'models': table,
    }
    audit['cross checks'] = cross_checks(sbml)
    audit['disagreements'] = [c for c in audit['cross checks'] if not c['agree']]
    audit['headline moves'] = moves(rec)
    audit['verdicts under grouping'] = verdicts(rec)
    OUT_JSON.write_text(json.dumps(audit, indent=1, default=str))
    OUT_SHEET.write_text(datasheet(audit))
    print('wrote', OUT_JSON.relative_to(ROOT), 'and', OUT_SHEET.relative_to(ROOT))
    print('disagreements:', len(audit['disagreements']))
    for c in audit['disagreements']:
        print('  ', c['what'], c['a'], c['b'])
    for m in audit['headline moves']:
        print('  ', m['headline'], m['published'], m['recounts'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=8)
    main(ap.parse_args().jobs)
