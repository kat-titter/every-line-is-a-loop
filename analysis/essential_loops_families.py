"""List families of models by a written rule, before any reduced address is read (fail line 3 of essential_loops.py).

Reads:  data/r31_curated/*.xml, data/holdout_curated/*.xml (model name and publication annotation only)
Writes: results/essential_loops_found_families.json
Run:    .venv/bin/python analysis/essential_loops_families.py

The rule, fixed 2026-11-22 before the list was made: two models are in one family when their SBML files cite the same
paper (the model's isDescribedBy annotation, a PubMed id or DOI), or when their names open with the same first author
and year ("Leloup1999_CircClock"). Families are the connected groups of two or more models under those two links, over
release 31 (640 models) and the 435 newer ones. The 18 models of the hand-picked families (truth_tests.FAMILIES) are
left out first, so this list shares no model with fail line 1. No loop count, atlas row or reduced address is read
here. Fail line 3 is scored on the families in which at least two drawings could be reduced; the report counts the
rest with their reasons.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
SETS = {'r31': ROOT / 'data' / 'r31_curated', 'holdout': ROOT / 'data' / 'holdout_curated'}
OUT = ROOT / 'results' / 'essential_loops_found_families.json'
AUTHOR_YEAR = re.compile(r"^\s*([A-Za-z][A-Za-z'\-]*?)[_ ]?((?:19|20)\d{2})(?!\d)")


def describe(path: pathlib.Path) -> dict[str, str | None]:
    """A model's name, its paper (PubMed id or DOI) and its first author and year, read from the SBML file."""
    import libsbml

    m = libsbml.readSBMLFromFile(str(path)).getModel()
    paper = None
    for i in range(m.getNumCVTerms()):
        t = m.getCVTerm(i)
        if t.getQualifierType() == libsbml.MODEL_QUALIFIER and t.getModelQualifierType() == libsbml.BQM_IS_DESCRIBED_BY:
            uris = [t.getResourceURI(j) for j in range(t.getNumResources())]
            ids = [
                u.split('identifiers.org/')[-1].replace('urn:miriam:', '') for u in uris if 'pubmed' in u or 'doi' in u
            ]
            paper = paper or (sorted(ids)[0] if ids else None)
    name = m.getName() or m.getId()
    hit = AUTHOR_YEAR.match(name)
    return {'name': name, 'paper': paper, 'author_year': f'{hit.group(1).lower()} {hit.group(2)}' if hit else None}


def families(models: list[dict]) -> list[list[dict]]:
    """Connected groups of two or more models linked by a shared paper or a shared first author and year."""
    parent = list(range(len(models)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first = {}
    for i, m in enumerate(models):
        for key in (('paper', m['paper']), ('author_year', m['author_year'])):
            if key[1] is not None:
                parent[root(i)] = root(first.setdefault(key, i))
    groups = {}
    for i, m in enumerate(models):
        groups.setdefault(root(i), []).append(m)
    return sorted((g for g in groups.values() if len(g) >= 2), key=lambda g: g[0]['model'])


def main() -> None:
    """Write the family list."""
    import truth_tests as TT

    hand = {m for ms in TT.FAMILIES.values() for m in ms}
    models = [
        {'model': p.stem, 'set': s, **describe(p)}
        for s, folder in SETS.items()
        for p in sorted(folder.glob('*.xml'))
        if p.stem not in hand
    ]
    fam = families(models)
    out = {
        'rule': 'same paper (isDescribedBy), or same first author and year in the model name; connected groups of 2+',
        'listed': '2026-11-22, before any reduced address was read',
        'pool': {s: sum(m['set'] == s for m in models) for s in SETS},
        'left_out_hand_picked': sorted(hand),
        'families': [{'id': i + 1, 'models': g} for i, g in enumerate(fam)],
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(len(models), 'models,', len(fam), 'families,', sum(map(len, fam)), 'models in families')


if __name__ == '__main__':
    main()
