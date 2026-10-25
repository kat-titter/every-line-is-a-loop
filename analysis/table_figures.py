"""Figures that draw the loop table itself for count-the-elements.html: the two kinds of loop, element
tiles beside a chemistry tile, the orbital arithmetic, the full table of 30 elements, and both periodic
tables drawn as loops. Nothing here reads the census; build_post.py adds the census on top.

Reading order of the elements. Row nu (n = nu + 1 loops-plus-one) holds every pair (k, j): k braking loops
and j loops through a running total, 0 <= k, j <= nu. Group the pairs by l = max(k, j): each group is an
L-shaped layer of 2l + 1 pairs, the same sizes as the s, p, d and f orbitals of shell n. Inside a layer,
order by m = k - j from -l to +l. Element zero, the counter, has no loop and comes first.
"""
import math

MINUS = '&#8722;'
SVG = 'font-family="Inter, Helvetica, Arial, sans-serif"'
BLOCKS = 'spdf'
LOOPS = {0: 'no loop', 1: 'one loop', 2: 'two loops', 3: 'three loops'}

# The essay's named elements and examples (its Figure 2 and key): (loops, braking, running totals)
ESSAY = {
    (0, 0, 0): ('counter', 'h to gen', ['Am', 'Df', 'Dv', 'Ag', 'Ev']),
    (1, 0, 0): ('switch', '&#181;s to day', ['Al', 'Rs', 'Ck', 'Lc', 'Lh']),
    (1, 1, 1): ('adapter', 's to min', ['Ch', 'Hg']),
    (1, 1, 0): ('clock', 'min to day', ['Gl', 'Hs', 'Kc']),
    (2, 0, 0): ('memory', 'day', ['Pc']),
    (2, 1, 0): ('relaxation oscillator', 'ms to h', ['Ap', 'Cc']),
    (2, 2, 0): ('coupled clocks', 'h', ['Sg']),
    (3, 0, 0): ('multistate memory', 'h to day', ['Pl']),
    (3, 1, 0): ('working memory', 'min to h', ['Eg']),
    (3, 2, 0): ('circadian', 'day', ['Cr']),
    (3, 3, 0): ('clock, no memory', 'h', ['Nf']),
}


def order():
    """Element number -> (nu, k, j)."""
    out = [(0, 0, 0)]
    for nu in (1, 2, 3):
        for l in range(nu + 1):
            for m in range(-l, l + 1):
                k, j = (l, l - m) if m >= 0 else (l + m, l)
                out.append((nu, k, j))
    return out


ELEMENTS = order()
NUMBER = {e: i for i, e in enumerate(ELEMENTS)}
assert len(ELEMENTS) == 30 and len(set(ELEMENTS)) == 30


def signs(nu, k):
    return ' '.join(['+'] * (nu - k) + [MINUS] * k)


def lm(k, j):
    return max(k, j), k - j


def column(k, j):
    l, m = lm(k, j)
    return l * l + l + m          # s: 0, p: 1 to 3, d: 4 to 8, f: 9 to 15


def rings_svg(cx, cy, j, r=3, gap=8):
    return ''.join(f'<circle cx="{cx + (q - (j - 1) / 2) * gap:.1f}" cy="{cy}" r="{r}" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' for q in range(j))


def open_arc(cx, cy, r=9, sw=1.8):
    """Element zero's glyph: a loop that never closes."""
    a0, a1 = math.radians(40), math.radians(320)
    x0, y0 = cx + r * math.sin(a0), cy - r * math.cos(a0)
    x1, y1 = cx + r * math.sin(a1), cy - r * math.cos(a1)
    return f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 1 1 {x1:.1f} {y1:.1f}" fill="none" stroke="var(--ink)" stroke-width="{sw}"/>'


# ---------------------------------------------------------------- two kinds of loop
def fig_loop_kinds():
    defs = ('<defs><marker id="lka" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0L10 5L0 10z" fill="var(--accent)"/></marker><marker id="lki" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
            '<path d="M8 0V10" stroke="var(--accent)" stroke-width="2.4"/></marker></defs>')

    def panel(title, second, trace, label):
        nodes = ''.join(f'<circle cx="{x}" cy="78" r="20" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.25"/>'
                        f'<text x="{x}" y="83" text-anchor="middle" fill="var(--ink)">{t}</text>' for x, t in ((115, 'X'), (215, 'Y')))
        arcs = (f'<line x1="137" y1="70" x2="191" y2="70" stroke="var(--accent)" stroke-width="2.2" marker-end="url(#lka)"/>'
                f'<line x1="193" y1="88" x2="139" y2="88" stroke="var(--accent)" stroke-width="2.2" marker-end="url(#{second})"/>')
        return (f'<svg viewBox="0 0 330 250" role="img" aria-label="{title}: {label}" {SVG} font-size="14">{defs}'
                f'<text x="165" y="26" text-anchor="middle" font-weight="600" fill="var(--ink)">{title}</text>{arcs}{nodes}'
                f'<line x1="50" y1="170" x2="280" y2="170" stroke="var(--rule)"/>{trace}'
                f'<text x="165" y="238" text-anchor="middle" fill="var(--muted)">{label}</text></svg>')
    switch = ('<path d="M50 168C100 166 120 140 170 136L280 136" fill="none" stroke="var(--ink)" stroke-width="1.6"/>'
              '<path d="M50 172C100 174 120 200 170 204L280 204" fill="none" stroke="var(--ink)" stroke-width="1.6"/>')
    pts = ' '.join(f'{50 + i * 2.3:.1f},{170 - 30 * math.sin(i * 2.3 / 230 * 2 * math.pi * 3.2) * (1 if i else 0):.1f}' for i in range(101))
    clock = f'<polyline points="{pts}" fill="none" stroke="var(--ink)" stroke-width="1.6"/>'
    a = panel('Amplifying loop', 'lka', switch, 'a nudge grows: a switch')
    b = panel('Braking loop', 'lki', clock, 'a nudge is undone: a clock, given delay')
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'


# ---------------------------------------------------------------- tiles
def tile_html(e):
    nu, k, j = e
    name, period, ex = ESSAY[e]
    if nu == 0:
        glyph = f'<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">{open_arc(20, 20, 13, 2.2)}</svg>'
        counts = '0'
    else:
        rings = ''.join('<i class="ring"></i>' for _ in range(j))
        glyph = f'{signs(nu, k)}<span class="rings">{rings}</span>'
        counts = f'{nu} {k} {j}'
    return (f'<div class="tile"><span class="z">{NUMBER[e]}</span><span class="cnt">{counts}</span>'
            f'<span class="sym">{glyph}</span><span class="nm">{name}</span><span class="ms">{period}</span>'
            f'<span class="ex">{" ".join(ex)}</span></div>')


def fig_tiles():
    carbon = ('<div class="tile chem"><span class="z">6</span><span class="cnt">2 4</span><span class="sym">C</span>'
              '<span class="nm">carbon</span><span class="ms">12.011</span><span class="ex">&#160;</span></div>')
    return '<div class="tiles">' + carbon + ''.join(tile_html(e) for e in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)]) + '</div>'


# ---------------------------------------------------------------- orbitals
def fig_orbitals():
    rows = ''
    for l, y in zip(range(4), (62, 102, 142, 182)):
        n = 2 * l + 1
        x0 = 165 - (n * 28 - 4) / 2 + 18
        rows += f'<text x="{x0 - 16}" y="{y + 17}" text-anchor="end" fill="var(--ink)" font-weight="600">{BLOCKS[l]}</text>'
        for q in range(n):
            rows += (f'<rect x="{x0 + q * 28:.1f}" y="{y}" width="24" height="24" rx="4" fill="{"var(--tint)" if l % 2 else "var(--paper)"}" '
                     f'stroke="var(--muted)"/>')
    atom = (f'<svg viewBox="0 0 330 250" role="img" aria-label="Shell four of an atom: one s, three p, five d and seven f orbitals, sixteen in all" {SVG} font-size="14">'
            f'<text x="165" y="26" text-anchor="middle" font-weight="600" fill="var(--ink)">Shell 4 of an atom</text>{rows}'
            f'<text x="165" y="236" text-anchor="middle" fill="var(--muted)">1 + 3 + 5 + 7 = 16 orbitals</text></svg>')
    cells = ''
    x0, y0, c = 117, 72, 36
    for k in range(4):
        cells += f'<text x="{x0 + k * c + c / 2}" y="{y0 - 8}" text-anchor="middle" fill="var(--muted)">{k}</text>'
    for j in range(4):
        cells += f'<text x="{x0 - 10}" y="{y0 + j * c + c / 2 + 5}" text-anchor="end" fill="var(--muted)">{j}</text>'
        for k in range(4):
            l = max(k, j)
            cells += (f'<rect x="{x0 + k * c}" y="{y0 + j * c}" width="{c - 4}" height="{c - 4}" rx="4" fill="{"var(--tint)" if l % 2 else "var(--paper)"}" stroke="var(--muted)"/>'
                      f'<text x="{x0 + k * c + (c - 4) / 2}" y="{y0 + j * c + (c - 4) / 2 + 5}" text-anchor="middle" fill="var(--ink)">{BLOCKS[l]}</text>')
    loop = (f'<svg viewBox="0 0 330 250" role="img" aria-label="Row three of the loop table as a square of braking loops by running totals, peeling into L-shaped layers of one, three, five and seven" {SVG} font-size="14">'
            f'<text x="165" y="26" text-anchor="middle" font-weight="600" fill="var(--ink)">Row 3 of the loop table</text>'
            f'<text x="{x0 + 2 * c - 2}" y="46" text-anchor="middle" fill="var(--muted)">braking loops</text>{cells}'
            f'<text x="165" y="236" text-anchor="middle" fill="var(--muted)">down: loops keeping a running total</text></svg>')
    return f'<div class="pair"><div>{atom}</div><div>{loop}</div></div>'


# ---------------------------------------------------------------- the full table
def small_tile(x, y, e, named, w=40, h=50):
    nu, k, j = e
    if nu == 0:
        box = f'<rect data-el="0" x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="var(--tint)" stroke="var(--muted)" stroke-dasharray="4 3"/>'
        glyph = open_arc(x + w / 2, y + 31, 8, 1.6)
    else:
        box = (f'<rect data-el="{NUMBER[e]}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1.3"/>' if named else
               f'<rect data-el="{NUMBER[e]}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="none" stroke="var(--muted)" stroke-dasharray="3 3"/>')
        glyph = (f'<text x="{x + w / 2}" y="{y + 33}" text-anchor="middle" font-size="13.5" fill="var(--ink)">{signs(nu, k).replace(" ", "")}</text>'
                 + rings_svg(x + w / 2, y + 42, j, r=2.6, gap=7))
    return box + f'<text x="{x + 5}" y="{y + 15}" font-size="12.5" fill="var(--muted)">{NUMBER[e]}</text>' + glyph


def fig_full_table(narrow=False):
    out = []
    W_, H_, G = 40, 50, 3
    if not narrow:
        X0, Y0 = 48, 34
        out.append(f'<text x="{X0 - 10}" y="{Y0 - 12}" text-anchor="end" fill="var(--muted)">loops</text>')
        for l in range(4):
            c0, c1 = l * l, l * l + 2 * l
            out.append(f'<text x="{X0 + (c0 + c1) / 2 * (W_ + G) + W_ / 2 + l * 6}" y="{Y0 - 12}" text-anchor="middle" font-weight="600" fill="var(--ink)">{BLOCKS[l]}</text>')
        for nu in range(4):
            y = Y0 + nu * (H_ + 8)
            out.append(f'<text x="{X0 - 10}" y="{y + 30}" text-anchor="end" fill="var(--muted)">{nu}</text>')
        for e in ELEMENTS:
            nu, k, j = e
            col = column(k, j)
            l = max(k, j)
            out.append(small_tile(X0 + col * (W_ + G) + l * 6, Y0 + nu * (H_ + 8), e, e in ESSAY))
        W, H = X0 + 16 * (W_ + G) + 18 + 4, Y0 + 4 * (H_ + 8)
    else:
        y, X0 = 0, 40
        parts = [((0, 1), range(0, 4)), ((2,), range(2, 4)), ((3,), range(3, 4))]
        for blocks, nus in parts:
            cols = [c for l in blocks for c in range(l * l, l * l + 2 * l + 1)]
            first = cols[0]
            y += 22
            for l in blocks:
                c0, c1 = l * l, l * l + 2 * l
                out.append(f'<text x="{X0 + ((c0 + c1) / 2 - first) * (W_ + G) + W_ / 2 + (l - blocks[0]) * 6}" y="{y}" text-anchor="middle" font-weight="600" fill="var(--ink)">{BLOCKS[l]}</text>')
            y += 10
            for nu in nus:
                out.append(f'<text x="{X0 - 8}" y="{y + 30}" text-anchor="end" fill="var(--muted)">{nu}</text>')
                for e in ELEMENTS:
                    if e[0] == nu and max(e[1], e[2]) in blocks:
                        l = max(e[1], e[2])
                        out.append(small_tile(X0 + (column(e[1], e[2]) - first) * (W_ + G) + (l - blocks[0]) * 6, y, e, e in ESSAY))
                y += H_ + 8
            y += 6
        out.append('<text x="2" y="16" fill="var(--muted)">loops</text>')
        W, H = X0 + 7 * (W_ + G) + 4, y
    return f'''<svg viewBox="0 0 {W:.0f} {H}" role="img" aria-label="All thirty elements of the loop table, rows by number of loops and blocks s, p, d and f" {SVG} font-size="14">
  {''.join(out)}
</svg>'''


# ---------------------------------------------------------------- both tables as loops
TH0, TH1 = 30.0, 330.0


def _pt(cx, cy, r, th):
    a = math.radians(th)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def _shape(x, y, l, s, fill):
    if l == 0:
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s:.1f}" fill="{fill}"/>'
    if l == 1:
        return f'<rect x="{x - s * 0.9:.1f}" y="{y - s * 0.9:.1f}" width="{1.8 * s:.1f}" height="{1.8 * s:.1f}" fill="{fill}"/>'
    if l == 2:
        return f'<path d="M{x:.1f} {y - 1.25 * s:.1f}L{x + 1.25 * s:.1f} {y:.1f}L{x:.1f} {y + 1.25 * s:.1f}L{x - 1.25 * s:.1f} {y:.1f}z" fill="{fill}"/>'
    return f'<path d="M{x:.1f} {y - 1.2 * s:.1f}L{x + 1.15 * s:.1f} {y + 0.9 * s:.1f}L{x - 1.15 * s:.1f} {y + 0.9 * s:.1f}z" fill="{fill}"/>'


def _legend(y, s):
    out = []
    for l in range(4):
        x = 165 - 96 + l * 64
        out.append(_shape(x, y - 4, l, s, 'var(--ink)') + f'<text x="{x + 10}" y="{y + 1}" fill="var(--muted)">{BLOCKS[l]}</text>')
    return ''.join(out)


def _spiral(cx, cy, r0, b, turns_from, turns_to, th_start=TH0):
    pts = []
    t = turns_from * 360 + th_start
    while t <= turns_to * 360 + TH1 + 0.1:
        r = r0 + b * (t - turns_from * 360) / 360
        pts.append('%.1f,%.1f' % _pt(cx, cy, r, t % 360))
        t += 4
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="var(--accent)" stroke-width="1.4"/>'


def fig_spirals():
    periods = [2, 8, 8, 18, 18, 32, 32]
    g1 = ['H', 'Li', 'Na', 'K', 'Rb', 'Cs', 'Fr']
    g18 = ['He', 'Ne', 'Ar', 'Kr', 'Xe', 'Rn', 'Og']
    cx, cy, r0, b = 165, 170, 22, 15
    chem = [_spiral(cx, cy, r0, b, 0, 6)]
    for p, L in enumerate(periods):
        blocks = (['s'] * 2 if L == 2 else ['s'] * 2 + ['f'] * (14 if L == 32 else 0) + ['d'] * (10 if L >= 18 else 0) + ['p'] * 6)
        for i, blk in enumerate(blocks):
            th = TH0 + (TH1 - TH0) * i / (L - 1)
            x, y = _pt(cx, cy, r0 + b * (p + th / 360), th)
            fam = i == 0 or i == L - 1
            chem.append(_shape(x, y, BLOCKS.index(blk), 3.6 if fam else 2.9, 'var(--accent)' if fam else 'var(--ink)'))
    for th, lab, anchor in ((TH0, 'group 1', 'start'), (TH1, 'noble gases', 'end')):
        x, y = _pt(cx, cy, r0 + b * (6 + th / 360) + 16, th)
        chem.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="var(--accent-text)">{lab}</text>')
    for p, (a, z) in enumerate(zip(g1, g18)):
        if p == 0:
            for th, t, anchor, dx in ((TH0, a, 'start', 7), (TH1, z, 'end', -7)):
                x, y = _pt(cx, cy, r0 + b * (p + th / 360), th)
                chem.append(f'<text x="{x + dx:.1f}" y="{y + 15:.1f}" text-anchor="{anchor}" font-size="12" fill="var(--muted)">{t}</text>')
    chem_svg = (f'<svg viewBox="0 0 330 350" role="img" aria-label="The chemical periodic table as a spiral: 118 elements, one turn per period; group 1 and the noble gases line up on two rays" {SVG} font-size="13">'
                f'<text x="165" y="22" text-anchor="middle" font-weight="600" font-size="14" fill="var(--ink)">Chemistry</text>{"".join(chem)}{_legend(334, 4)}</svg>')

    cx, cy, r0, b = 165, 172, 40, 32
    bio = [f'<line x1="{cx}" y1="{cy}" x2="{_pt(cx, cy, r0 + b * TH0 / 360, TH0)[0]:.1f}" y2="{_pt(cx, cy, r0 + b * TH0 / 360, TH0)[1]:.1f}" stroke="var(--accent)" stroke-width="1.4"/>',
           _spiral(cx, cy, r0, b, 0, 2)]
    bio.append(open_arc(cx, cy, 7, 1.8))
    bio.append(f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="12" fill="var(--muted)">0</text>')
    for nu in (1, 2, 3):
        row = [e for e in ELEMENTS if e[0] == nu]
        L = len(row)
        for i, e in enumerate(row):
            th = TH0 + (TH1 - TH0) * i / (L - 1)
            r = r0 + b * (nu - 1 + th / 360)
            x, y = _pt(cx, cy, r, th)
            fam = i == 0 or i == L - 1
            bio.append(_shape(x, y, max(e[1], e[2]), 5.2, 'var(--accent)' if fam else 'var(--ink)'))
            lx, ly = _pt(cx, cy, r + 17, th)
            bio.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" font-size="11.5" fill="var(--muted)">{NUMBER[e]}</text>')
    for th, lab, anchor in ((TH0, 'memories', 'start'), (TH1, 'clocks', 'end')):
        x, y = _pt(cx, cy, r0 + b * (2 + th / 360) + 30, th)
        bio.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="var(--accent-text)">{lab}</text>')
    bio_svg = (f'<svg viewBox="0 0 330 350" role="img" aria-label="The loop table as a spiral: element zero at the centre, then one turn per row of 4, 9 and 16 elements; memories and clocks line up on two rays" {SVG} font-size="13">'
               f'<text x="165" y="22" text-anchor="middle" font-weight="600" font-size="14" fill="var(--ink)">The loop table</text>{"".join(bio)}{_legend(334, 4)}</svg>')
    return f'<div class="pair"><div>{chem_svg}</div><div>{bio_svg}</div></div>'


def builder_html():
    """Controls and script that build an element from loops and light it up in the full table."""
    import json
    data = {'order': [list(e) for e in ELEMENTS],
            'names': {f'{a},{b},{c}': [v[0], ' '.join(v[2])] for (a, b, c), v in ESSAY.items()}}
    return ('''<div class="builder" id="builder" aria-label="Build an element">
<div class="b-row"><span class="b-lab">loops</span><span class="seg" id="b-n">''' +
            ''.join(f'<button type="button" data-n="{n}">{n}</button>' for n in range(4)) +
            '''</span></div>
<div id="b-loops"></div>
<p class="b-out" id="b-out" aria-live="polite"></p>
</div>
<script>
(function () {
  var D = ''' + json.dumps(data) + ''';
  var MINUS = '\u2212';
  var st = {n: 2, loops: [{brake: false, total: false}, {brake: true, total: false}, {brake: false, total: false}]};
  var nEl = document.getElementById('b-n'), loopsEl = document.getElementById('b-loops'), out = document.getElementById('b-out');
  function number(nu, k, j) {
    for (var i = 0; i < D.order.length; i++) { var e = D.order[i]; if (e[0] === nu && e[1] === k && e[2] === j) return i; }
    return -1;
  }
  function render() {
    [].forEach.call(nEl.querySelectorAll('button'), function (b) { b.setAttribute('aria-pressed', String(+b.dataset.n === st.n)); });
    loopsEl.innerHTML = '';
    for (var i = 0; i < st.n; i++) {
      var L = st.loops[i], row = document.createElement('div');
      row.className = 'b-row';
      row.innerHTML = '<span class="b-lab">loop ' + (i + 1) + '</span>' +
        '<span class="seg"><button type="button" data-i="' + i + '" data-k="brake" data-v="0" aria-pressed="' + !L.brake + '">+ amplifies</button>' +
        '<button type="button" data-i="' + i + '" data-k="brake" data-v="1" aria-pressed="' + L.brake + '">' + MINUS + ' brakes</button></span>' +
        '<button type="button" class="tog" data-i="' + i + '" data-k="total" aria-pressed="' + L.total + '">&#9675; running total</button>';
      loopsEl.appendChild(row);
    }
    var k = 0, j = 0;
    for (var q = 0; q < st.n; q++) { k += st.loops[q].brake ? 1 : 0; j += st.loops[q].total ? 1 : 0; }
    var num = number(st.n, k, j), key = st.n + ',' + k + ',' + j, nm = D.names[key];
    var glyph = st.n === 0 ? 'no loop' : (new Array(st.n - k + 1).join('+') + new Array(k + 1).join(MINUS)) + (j ? ' ' + new Array(j + 1).join('&#9675;') : '');
    out.innerHTML = '<span class="b-glyph">' + glyph + '</span> element ' + num + ': ' +
      (nm ? '<b>' + nm[0] + '</b> <span class="b-ex">' + nm[1] + '</span>' : 'a blank, with no example yet');
    [].forEach.call(document.querySelectorAll('rect[data-el]'), function (r) { r.classList.toggle('on', +r.dataset.el === num); });
  }
  nEl.addEventListener('click', function (ev) { var b = ev.target.closest('button'); if (!b) return; st.n = +b.dataset.n; render(); });
  loopsEl.addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    var L = st.loops[+b.dataset.i];
    if (b.dataset.k === 'brake') L.brake = b.dataset.v === '1'; else L.total = !L.total;
    render();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render); else render();
})();
</script>''')
