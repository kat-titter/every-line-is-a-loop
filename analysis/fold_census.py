"""Fold the census into the essay. The census is still built by build_post.py (into build/, not published); this
script takes the pieces the one-page essay shows (the loop toy, the row grids, the orbital arithmetic, the periodic
table with its cards, the data figure with the funnel and the explorer, the claims scorecard, the research loop, and
supplements A to D) from that build, remaps its citations onto the essay's reference list (appending the sources the
essay did not have, in a fixed order so the numbers stay stable), renumbers its figures, strips its citation cards,
pulls the stylesheet rules its components need, adds the punchline figure (loop_morph.py) and writes everything
between the essay's <!-- gen:NAME --> markers.

Usage: python3 analysis/fold_census.py        (rebuilds build/count-the-elements.html first when it is missing)
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import table_figures as TF  # noqa: E402
import loop_morph as LM  # noqa: E402

BUILD = ROOT / 'build' / 'count-the-elements.html'
ESSAY = ROOT / 'every-line-is-a-loop.html'

# The essay's own list is 1 to 37. Sources the census brings in take the numbers after it, in this order.
EXTRA_ORDER = [
    '10.1016/S0039-3681(01)00023-1',   # Scerri and Worrall 2001, prediction and the periodic table
    '10.1080/14786441308635052',       # Moseley 1913
    '10.1093/nar/gkz1055',             # BioModels, Malik-Sheriff 2020
    '10.1093/nar/gkj092',              # BioModels Database, Le Novère 2006
    '10.1093/bioinformatics/btg015',   # SBML, Hucka 2003
    '10.1126/science.298.5594.824',    # network motifs, Milo 2002
    '10.1038/nrg2102',                 # Alon 2007
    '10.1126/science.aaa2245',         # Ahnert 2015
    '10.1016/j.cels.2016.01.004',      # Briat 2016, antithetic integral feedback
    '10.1038/s41586-019-1321-1',       # Aoki 2019, universal integral controller
    '10.1038/140193b0',                # Perrier and Segrè 1937, element 43
    '10.1103/PhysRev.74.230',          # Bardeen and Brattain 1948
    '10.1016/j.cell.2009.06.013',      # Ma 2009, topologies that adapt
    '10.1016/j.cels.2017.06.013',      # Li 2017
    '10.1101/170951',                  # Lillacci 2017
    '10.1529/biophysj.107.125021',     # Sontag 2008, Boolean negative loops
    '10.1007/s11538-013-9893-7',       # Soliman 2013
    '10.1093/bioinformatics/btac770',  # libRoadRunner
    '10.1093/bioinformatics/btn051',   # libSBML
    '10.1145/1089014.1089020',         # SUNDIALS
    '10.1142/S0218339098000042',       # Snoussi 1998
    '10.1142/S0218339098000054',       # Gouzé 1998
]
# Sources the essay cites by hand in the hidden-elements chapter, verified through Crossref on 2026-10-25.
NEW_REFS = [
    ('10.1098/rsta.1895.0006', 'Rayleigh (Strutt JW), Ramsay W. Argon, a new constituent of the atmosphere. <i>Philos Trans R Soc Lond A</i> 186:187&#8211;241 (1895). <a href="https://doi.org/10.1098/rsta.1895.0006">doi:10.1098/rsta.1895.0006</a>'),
    ('10.1038/111079a0', 'Coster D, Hevesy G. On the missing element of atomic number 72. <i>Nature</i> 111:79 (1923). <a href="https://doi.org/10.1038/111079a0">doi:10.1038/111079a0</a>'),
    ('10.1021/ja01203a059', 'Marinsky JA, Glendenin LE, Coryell CD. The chemical identification of radioisotopes of neodymium and of element 61. <i>J Am Chem Soc</i> 69(11):2781&#8211;2785 (1947). <a href="https://doi.org/10.1021/ja01203a059">doi:10.1021/ja01203a059</a>'),
]
# The same work cited through two records (post key -> essay key).
ALIASES = {}

# Figure numbers in the merged page for the figures that come from the census build.
FIG = {'Figure 1. Arrows and loops.': 'Figure 1. Flip the arrows.',
       'Figure 5. The periodic table of loops.': 'Figure 6. The periodic table of loops.',
       'Figure 6. The data.': 'Figure 7. The data.',
       'Figure 7. The research loop.': 'Figure 12. The research loop.'}

CSS_WANT = ['.pt-', '.ptable', '.ecard', '.rc-', '.refcard', '.tile', '.tiles', '.cards', '.card', '.summary-cards', '.f-', '.explorer',
            '.ex-', 'ol.ex-list', '#ex-q', '.pick', '.sl-', '.sn', '.sp', '.solo', '.bars', '.grid-fig', '.grid-key', '.rows-grid', '.quad',
            '.pair', '.bio', '.sy-i', 'ol.steps', 'details.supp', '.interactive', '.fig-wide', '.fig-narrow', '.wide', '.nowrap', '.arr',
            'math[display', 'table.key', '.lt-', '.coast', '.badge', '.shaft', '.ruler', '.builder', '.b-', '.seg', '.gauge', '.g-']
CSS_DROP = {'body', 'html', '.text', 'h2', 'figure.fig', 'figure', '.ctl', '.chip', '.cite', '.mast', '.post', '.abstract', '.eyebrow',
            '.end', 'ol.refs', 'a', 'p', 'svg', 'section', 'table', 'td', 'th', 'b', 'strong', 'label', 'title', '.label', 'code', 'pre'}


def key_of(li):
    """A DOI when the record has one, else an arXiv id, else the first link."""
    for pat in (r'doi\.org/([^"]+)"', r'arxiv\.org/abs/([^"]+)"', r'href="([^"]+)"'):
        m = re.search(pat, li)
        if m:
            return m.group(1)
    return None


def refs_of(html, start='<ol class="refs">'):
    i = html.index(start)
    j = html.index('</ol>', i)
    out = []
    for m in re.finditer(r'<li(?: id="r\d+")?>(.*?)</li>', html[i:j], re.S):
        out.append((key_of(m.group(1)), m.group(1).strip()))
    return out


def block(html, start, end_tag, from_index=0):
    i = html.index(start, from_index)
    j = html.index(end_tag, i) + len(end_tag)
    return html[i:j]


def inner(fig):
    """The content of a <figure> block without its own plate and caption: the essay wraps it in its own figure."""
    body = fig[fig.index('>') + 1:fig.rindex('</figure>')]
    body = re.sub(r'<figcaption>.*?</figcaption>', '', body, flags=re.S)
    return body.strip()


def div_block(html, start):
    """A <div ...> and its matching </div>."""
    i = html.index(start)
    depth, k = 0, i
    for m in re.finditer(r'<div\b|</div>', html[i:]):
        depth += 1 if m.group(0) == '<div' else -1
        if depth == 0:
            return html[i:i + m.end()]
    raise ValueError(start)


def split_css(css):
    """Top-level rules and @-blocks as (prelude, body, nested) triples."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j < 0:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while depth and k < n:
            depth += 1 if css[k] == '{' else -1 if css[k] == '}' else 0
            k += 1
        body = css[j + 1:k - 1]
        out.append((prelude, body))
        i = k
    return out


def wanted(selector):
    sel = selector.strip()
    if sel in CSS_DROP:
        return False
    return any(sel.startswith(w) or (' ' + w) in sel or ('>' + w) in sel or (',' + w) in sel for w in CSS_WANT)


def extract_css(css):
    kept = []
    for prelude, body in split_css(css):
        prelude = re.sub(r'/\*.*?\*/', '', prelude, flags=re.S).strip()
        if prelude.startswith('@media') or prelude.startswith('@supports'):
            inner = [f'{p} {{{b}}}' for p, b in split_css(body) if any(wanted(x) for x in p.split(','))]
            if inner:
                kept.append(f'{prelude} {{ ' + ' '.join(inner) + ' }')
        elif prelude.startswith('@'):
            continue
        elif any(wanted(x) for x in prelude.split(',')):
            kept.append(f'{prelude} {{{body}}}')
    return '\n'.join(kept)


def main():
    if not BUILD.exists():
        BUILD.parent.mkdir(exist_ok=True)
        subprocess.run([sys.executable, str(ROOT / 'analysis' / 'build_post.py')], check=True)
    post = BUILD.read_text(encoding='utf-8')
    essay = ESSAY.read_text(encoding='utf-8')

    # ---- references: the essay's list, then the census's extras in a fixed order, then the hand-cited sources
    essay_refs = refs_of(essay[:essay.index('<!-- gen:refs-extra -->')] + '</ol>')
    ekey = {k: n + 1 for n, (k, _) in enumerate(essay_refs) if k}
    post_refs = refs_of(post)
    pkey = {n + 1: (k, li) for n, (k, li) in enumerate(post_refs)}
    extras = []
    for k in EXTRA_ORDER:
        li = next((li for kk, li in post_refs if kk == k), None)
        assert li, k
        extras.append((k, li))
    for k, li in NEW_REFS:
        extras.append((k, li))
    base = len(essay_refs)
    number = dict(ekey)
    for n, (k, li) in enumerate(extras):
        assert k not in number, k
        number[k] = base + n + 1
    pmap = {}
    for n, (k, li) in pkey.items():
        k2 = ALIASES.get(k, k)
        assert k2 in number, (n, k, re.sub(r'<[^>]+>', '', li)[:60])
        pmap[n] = number[k2]

    def recite(html):
        def one(m):
            nums = [pmap[int(x)] for x in re.findall(r'href="#r(\d+)"', m.group(0))]
            return '<span class="cite">[' + ', '.join(str(x) for x in nums) + ']</span>'
        return re.sub(r'<span class="cite">.*?</span>', one, html, flags=re.S)

    def refig(html):
        for a, b in FIG.items():
            html = html.replace(a, b)
        return html

    def clean(html):
        return refig(recite(html))

    # ---- blocks from the census build
    elcard = block(post, '<script>\nwindow.ElCard', '</script>')
    theory = post[post.index('<section id="theory">'):post.index('<section id="table">')]
    toy = block(theory, '<figure class="fig">', '</figure>')
    assert 'lt-ring' in toy
    table_sec = post[post.index('<section id="table">'):post.index('<section id="data">')]
    ptable = block(table_sec, '<figure class="fig">', '</figure>', table_sec.index('Figure 5. The periodic table') - 60000)
    ptable = table_sec[table_sec.rfind('<figure class="fig">', 0, table_sec.index('Figure 5. The periodic table')):table_sec.index('</figure>', table_sec.index('Figure 5. The periodic table')) + 9]
    assert 'pt-card' in ptable and 'ptable' in ptable
    ptable = ptable.replace(div_block(ptable, '<div class="pt-keybox">'), '')   # the explainer tile: the cards explain each real tile
    data_sec = post[post.index('<section id="data">'):post.index('<section id="results">')]
    datafig = block(data_sec, '<figure class="fig">', '</figure>')
    assert 'ex-q' in datafig and 'funnel' in datafig
    # the explorer opens on one worked search, the repressilator; the chips and the box lead to the rest
    k = datafig.index('  draw();\n})();', datafig.index('var R = [{'))
    datafig = datafig[:k] + "  q.value = 'repressilator'; draw();\n})();" + datafig[k + len('  draw();\n})();'):]
    results_sec = post[post.index('<section id="results">'):post.index('<section id="gaps">')]
    cards = div_block(results_sec, '<div class="summary-cards">')
    next_sec = post[post.index('<section id="next">'):post.index('<section id="limits">')]
    nextfig = block(next_sec, '<figure class="fig">', '</figure>')
    assert 'id="sl"' in nextfig
    supp = post[post.index('<details class="supp" id="supp-a">'):post.index('<details class="supp" id="refs-d">')]
    css = extract_css(re.search(r'<style>(.*?)</style>', post, re.S).group(1))
    for claim in ('613 models', '175 have one to three loops', 'all 10 of them', 'Of the 20 elements with a running total, 3 are filled, by 4 models',
                  'five curated models', 'from one to 14 loops', 'remove the brakes of 10 clocks', '(13 models)', '102 loop searches'):
        assert claim in post, claim
    css += ('\n/* the essay reads in one sans; symbols and tiles follow it; its own key table wraps on a phone */\n'
            '.pt-sym, .tile .sym, .ecard h3, .pt-el .pt-sym, .card h3, .f-panel, .ex-name, details.supp > summary, .text h3 { font-family: var(--sans); }\n'
            '.text table.key td:nth-child(2) { white-space: normal; }\n')

    blocks = {
        'css-census': '<style>\n' + css + '\n</style>',
        'elcard': elcard,
        'toy': clean(inner(toy)[inner(toy).index('<div class="pair interactive">'):]),   # the ring and its plot; the gauges stay in the build
        'orbitals': TF.fig_orbitals(),
        'ptable': clean(inner(ptable)),
        'data': clean(inner(datafig)),
        'cards': clean(cards),
        'next': clean(inner(nextfig)),
        'morph': LM.fig_morph(),
        'supp': clean(supp),
        'refs-extra': '\n'.join(f'<li>{li}</li>' for k, li in extras),
    }
    for name, body in blocks.items():
        pat = re.compile(r'(<!-- gen:' + name + r' -->).*?(<!-- /gen:' + name + r' -->)', re.S)
        assert pat.search(essay), name
        essay = pat.sub(lambda m: m.group(1) + '\n' + body + '\n' + m.group(2), essay, count=1)
    # the read time of the main read: no folds, references, masthead, scripts, styles or figure text
    main = essay[:essay.index('<section id="refs">')]
    main = re.sub(r'<details.*?</details>|<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<header.*?</header>', '', main, flags=re.S)
    import html as html_lib
    text = ' '.join(re.findall(r'<(?:p|li|figcaption|h2)(?:\s[^>]*)?>(.*?)</(?:p|li|figcaption|h2)>', main, flags=re.S))
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-]*", html_lib.unescape(re.sub(r'<[^>]+>', ' ', text)))
    mins = max(1, round(len(words) / 230))
    essay = re.sub(r'<span id="readtime">[^<]*</span>', f'<span id="readtime">{mins} min read</span>', essay)
    ESSAY.write_text(essay, encoding='utf-8')
    print('main read', len(words), 'words,', mins, 'min')
    left = sorted(set(re.findall(r'href="#r\d+"', essay)))
    assert not left, left
    print('folded', ', '.join(blocks), 'into', ESSAY.name, '| references', base, '+', len(extras))
    return number


if __name__ == '__main__':
    main()
