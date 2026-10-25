"""Citation sync for this page's markup: bracketed markers and one <ol class="refs">.

Every number in a [n], [n, m] or [a-b] marker (text or tables) must point to an
existing reference; every reference should be cited at least once.
Usage: python3 tools/check_refs.py [PAGE]
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
s = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'every-line-is-a-loop.html').read_text(encoding='utf-8')
s = s.replace('&#8211;', '–')
refs_block = re.search(r'<ol class="refs">(.*?)</ol>', s, re.S).group(1)
n_refs = len(re.findall(r'<li(?: id="r\d+")?>', refs_block))
body = s[:s.index('<ol class="refs">')]
body = re.sub(r'<script>.*?</script>', '', body, flags=re.S)
cited = {}
for m in re.finditer(r'\[(\d+(?:\s*[,–-]\s*\d+)*)\]', re.sub(r'<[^>]+>', '', body)):
    for part in re.split(r'\s*,\s*', m.group(1)):
        if re.search(r'[–-]', part):
            a, b = map(int, re.split(r'\s*[–-]\s*', part))
            nums = range(a, b + 1)
        else:
            nums = [int(part)]
        for n in nums:
            cited[n] = cited.get(n, 0) + 1
bad = sorted(n for n in cited if not 1 <= n <= n_refs)
uncited = [n for n in range(1, n_refs + 1) if n not in cited]
print(f'references {n_refs}; cited numbers {len(cited)}; out of range {bad}; never cited {uncited}')
sys.exit(1 if bad or uncited else 0)
