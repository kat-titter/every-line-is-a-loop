"""List, size and fetch the hold-out: BioModels models curated since release 31 (the essay's census read release 31).

    python3 analysis/get_holdout.py            # list today's curated SBML models, size the ones not in release 31
    python3 analysis/get_holdout.py --download # then fetch them into data/holdout_curated/ (resumable)

Writes results/holdout_ids.json (the list, its date, sizes) and results/holdout_manifest.json (SHA-256 per file).
Reads:  the BioModels web service (network), data/r31_curated/*.xml, results/holdout_ids.json when it exists
Writes: results/holdout_ids.json, results/holdout_manifest.json, data/holdout_curated/*.xml (with --download)
Run:    python3 analysis/get_holdout.py [--download] [--relist]

Standard library only. One request at a time, a pause between requests, a generic client name, no personal details.
The downloaded files are data: nothing here executes them.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = 'https://www.biomodels.org'
R31 = ROOT / 'data' / 'r31_curated'
DEST = ROOT / 'data' / 'holdout_curated'
IDS = ROOT / 'results' / 'holdout_ids.json'
MANIFEST = ROOT / 'results' / 'holdout_manifest.json'
PAUSE = 0.25
MAX_BYTES = 30 * 1024 * 1024  # a single model file larger than this is recorded and skipped


def get(url: str, raw: bool = False, tries: int = 4) -> bytes | dict[str, object]:
    """GET url with a pause after each request; bytes if raw, else parsed JSON. Retries, then raises."""
    for k in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'census-script', 'Accept': 'application/json' if not raw else '*/*'}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(PAUSE)
            return data if raw else json.loads(data)
        except Exception:  # network hiccup or a bad reply: wait and try again, then give up loudly
            if k == tries - 1:
                raise
            time.sleep(2 + 3 * k)


def listing() -> tuple[int, list[dict[str, object]]]:
    """Every manually curated model BioModels lists today: (match count, model records)."""
    models, offset = [], 0
    while True:
        q = urllib.parse.urlencode(
            {
                'query': 'curationstatus:"Manually curated"',
                'numResults': 100,
                'offset': offset,
                'sort': 'id-asc',
                'format': 'json',
            }
        )
        d = get(f'{BASE}/search?{q}')
        models += d['models']
        offset += 100
        if offset >= d['matches'] or not d['models']:
            return d['matches'], models


def main() -> None:
    """List and size the hold-out; with --download, fetch the files and write the manifest."""
    old = {p.stem for p in R31.glob('*.xml')}
    assert len(old) == 640, len(old)
    if IDS.exists() and '--relist' not in sys.argv:
        out = json.loads(IDS.read_text())
    else:
        matches, models = listing()
        ids = {m['id']: m for m in models}
        assert len(ids) == matches, (len(ids), matches)
        new = sorted(i for i, m in ids.items() if i not in old and m.get('format') == 'SBML' and i.startswith('BIOMD'))
        out = {
            'read': datetime.date.today().isoformat(),
            'source': BASE + '/search, curationstatus:"Manually curated"',
            'curated_today': matches,
            'sbml_today': sum(1 for m in ids.values() if m.get('format') == 'SBML'),
            'release31': len(old),
            'release31_missing_today': sorted(old - set(ids)),
            'curated_not_in_release31': len([i for i in ids if i not in old]),
            'not_sbml': sorted(i for i, m in ids.items() if i not in old and m.get('format') != 'SBML'),
            'holdout': [
                {'id': i, 'name': ids[i].get('name'), 'submitted': (ids[i].get('submissionDate') or '')[:10]}
                for i in new
            ],
        }
        for n, h in enumerate(out['holdout']):
            f = get(f'{BASE}/model/files/{h["id"]}?format=json')
            main_files = f.get('main') or []
            h['file'] = main_files[0]['name'] if main_files else None
            h['bytes'] = int(main_files[0].get('fileSize') or 0) if main_files else 0
            if n % 50 == 0:
                print('sized', n, 'of', len(out['holdout']), flush=True)
        out['total_bytes'] = sum(h['bytes'] for h in out['holdout'])
        IDS.write_text(json.dumps(out, indent=1))
    hold = out['holdout']
    print(
        f"curated today {out['curated_today']} (SBML {out['sbml_today']}); release 31 holds {out['release31']}, "
        f"{len(out['release31_missing_today'])} of them missing today; not in release 31: {out['curated_not_in_release31']} "
        f"({len(out['not_sbml'])} not SBML); hold-out {len(hold)} models, {out['total_bytes'] / 1e6:.1f} MB; "
        f"no main file: {sum(1 for h in hold if not h['file'])}; over {MAX_BYTES // 2**20} MB each: {sum(1 for h in hold if h['bytes'] > MAX_BYTES)}; "
        f"largest {max(h['bytes'] for h in hold) / 1e6:.1f} MB"
    )
    if '--download' not in sys.argv:
        return
    DEST.mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for n, h in enumerate(hold):
        p = DEST / f"{h['id']}.xml"
        if not h['file'] or h['bytes'] > MAX_BYTES:
            man[h['id']] = {'skipped': 'no main file' if not h['file'] else 'too large'}
            continue
        if p.exists() and h['id'] in man and man[h['id']].get('sha256'):
            continue
        try:
            data = get(f"{BASE}/model/download/{h['id']}?filename={urllib.parse.quote(h['file'])}", raw=True)
        except Exception as e:
            man[h['id']] = {'skipped': 'download failed: ' + str(e)[:80]}
            continue
        if b'<sbml' not in data[:4000]:
            man[h['id']] = {'skipped': 'not an SBML document', 'bytes': len(data)}
            continue
        tmp = p.with_suffix('.part')
        tmp.write_bytes(data)
        tmp.replace(p)
        man[h['id']] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'file': h['file']}
        if n % 25 == 0:
            MANIFEST.write_text(json.dumps(man, indent=1))
            print('fetched', n, 'of', len(hold), flush=True)
    MANIFEST.write_text(json.dumps(man, indent=1))
    ok = [k for k, v in man.items() if v.get('sha256')]
    print(
        f"downloaded {len(ok)} files, {sum(man[k]['bytes'] for k in ok) / 1e6:.1f} MB; skipped {len(man) - len(ok)}: "
        + json.dumps({k: v['skipped'] for k, v in man.items() if 'skipped' in v})[:600]
    )


if __name__ == '__main__':
    main()
