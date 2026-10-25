"""Three real circuits drawn the way cell biology draws them, one for each count of the table: a braking loop (the
circadian clock), an amplifying loop made of two brakes (the lac operon) and a running total (receptor methylation in
chemotaxis), plus a key. Conventions: DNA as a double helix with the gene banded and a bent promoter arrow; membranes as
lipid bilayers; proteins with shape (dimers as paired lobes, LacI as a tetramer, LacY as a helix bundle, the receptor
as a transmembrane dimer with a ligand bulb); methyl and phosphate groups as small lettered circles; activation as an
arrow, repression as a bar; lavender for amplify, amber for brake. Plain SVG, 11 px minimum text, local gradients and
the page's shared lift shadow for depth.
"""
import math

SVG = 'font-family="Inter, Helvetica, Arial, sans-serif"'
W, H = 300, 280
LIFT = 'filter="url(#fx-lift)"'


def defs(p):
    def grad(i, hi, mid, lo):
        return (f'<radialGradient id="{p}{i}" cx="36%" cy="30%" r="72%"><stop offset="0" style="stop-color: {hi}"/>'
                f'<stop offset="0.55" style="stop-color: {mid}"/><stop offset="1" style="stop-color: {lo}"/></radialGradient>')
    return ('<defs>'
            f'<marker id="{p}a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--accent-text)"/></marker>'
            f'<marker id="{p}i" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M8 0V10" stroke="var(--accent2-text)" stroke-width="2.2"/></marker>'
            f'<marker id="{p}k" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--ink)"/></marker>'
            + grad('ga', 'var(--orb-hi)', 'var(--accent)', 'var(--orb-lo)')
            + grad('gb', 'var(--orb-hi)', 'var(--accent2)', 'var(--orb2-lo)')
            + grad('gg', 'var(--paper)', 'var(--rule)', 'var(--muted)')
            + f'<pattern id="{p}bl" width="6" height="14" patternUnits="userSpaceOnUse">'
              '<circle cx="3" cy="2.6" r="2.2" fill="var(--muted)"/><circle cx="3" cy="11.4" r="2.2" fill="var(--muted)"/>'
              '<path d="M1.9 4.8V9.2M4.1 4.8V9.2" stroke="var(--muted)" stroke-width="0.7"/></pattern>'
            '</defs>')


def head(title, sub):
    return (f'<text x="{W / 2}" y="14" text-anchor="middle" font-size="12" font-weight="600" fill="var(--ink)">{title}</text>'
            f'<text x="{W / 2}" y="28" text-anchor="middle" font-size="11" fill="var(--muted)">{sub}</text>')


def act(d, p, width=1.6):
    return f'<path d="{d}" fill="none" stroke="var(--accent-text)" stroke-width="{width}" marker-end="url(#{p}a)"/>'


def rep(d, p, width=1.6):
    return f'<path d="{d}" fill="none" stroke="var(--accent2-text)" stroke-width="{width}" marker-end="url(#{p}i)"/>'


def label(x, y, t, anchor='middle', fill='var(--ink)', size=11, extra=''):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"{extra}>{t}</text>'


def lobe(x, y, rx, ry, p, kind='a'):
    return f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="url(#{p}g{kind})" {LIFT}/>'


def helix(x0, x1, y, amp=7, period=32):
    """A double helix: two crossing strands with base-pair rungs that shorten toward the crossings."""
    a, b, rungs = [], [], []
    x = x0
    while x <= x1:
        s = amp * math.sin(2 * math.pi * (x - x0) / period)
        a.append(f'{x:.1f},{y + s:.1f}')
        b.append(f'{x:.1f},{y - s:.1f}')
        x += 2
    for k in range(int((x1 - x0) / 8) + 1):
        xr = x0 + 8 * k + 4
        if xr > x1:
            break
        s = amp * math.sin(2 * math.pi * (xr - x0) / period)
        if abs(s) > 1.5:
            rungs.append(f'<line x1="{xr:.1f}" y1="{y + s:.1f}" x2="{xr:.1f}" y2="{y - s:.1f}" stroke="var(--muted)" stroke-width="0.9" opacity="0.8"/>')
    pa, pb = ' '.join(a), ' '.join(b)
    return (''.join(rungs) + f'<polyline points="{pa}" fill="none" stroke="var(--muted)" stroke-width="1.3"/>'
            f'<polyline points="{pb}" fill="none" stroke="var(--muted)" stroke-width="1.3"/>')


def gene(x, y, w, p):
    """A banded gene region under the helix, with the bent promoter arrow at its start."""
    return (f'<rect x="{x}" y="{y - 12}" width="{w}" height="24" rx="4" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1"/>'
            f'<path d="M{x - 6} {y - 12}V{y - 24}H{x + 4}" fill="none" stroke="var(--ink)" stroke-width="1.2" marker-end="url(#{p}k)"/>')


def bilayer(x, y, w, p):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="14" fill="var(--paper)"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="14" fill="url(#{p}bl)"/>')


def tagged(x, y, t, r=9):
    """A small lettered circle: Me for a methyl group, P for a phosphate."""
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.1"/>'
            + label(x, y + 4, t, size=11))


def sugar(x, y):
    """A disaccharide: two fused hexagons."""
    def hexagon(cx, cy, r=3.6):
        pts = ' '.join(f'{cx + r * math.cos(math.radians(60 * i)):.1f},{cy + r * math.sin(math.radians(60 * i)):.1f}' for i in range(6))
        return f'<polygon points="{pts}" fill="var(--paper)" stroke="var(--ink)" stroke-width="0.9"/>'
    return hexagon(x, y) + hexagon(x + 6.3, y)


SERIF = ' font-family="Iowan Old Style, Charter, Georgia, serif" font-style="italic"'


def panel_clock():
    p = 'bfc'
    s = head('braking loop', 'the circadian clock')
    s += '<ellipse cx="150" cy="152" rx="118" ry="82" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.1"/>'
    s += '<ellipse cx="150" cy="152" rx="113" ry="77" fill="none" stroke="var(--muted)" stroke-width="1.1"/>'
    s += label(150, 218, 'nucleus', fill='var(--muted)')
    s += gene(160, 152, 66, p) + helix(60, 240, 152)
    s += label(193, 181, '<tspan font-style="italic">Per, Cry</tspan>')
    # CLOCK:BMAL1, a dimer sitting upstream of the gene, switching it on
    s += lobe(118, 126, 15, 11, p) + lobe(140, 122, 14, 10, p)
    s += label(128, 101, 'CLOCK:BMAL1')
    s += act('M152 128 Q162 128 167 138', p)
    # mRNA leaves through the envelope; a ribosome reads it; PER and CRY are made outside
    s += ('<path d="M226 152 C250 150 262 176 258 200 C254 222 236 230 214 236" fill="none" stroke="var(--accent-text)" '
          'stroke-width="1.6" stroke-dasharray="5 3"/>')
    s += '<circle cx="226" cy="152" r="2.6" fill="var(--accent-text)"/>'
    s += label(280, 186, 'mRNA', fill='var(--muted)')
    s += '<circle cx="243" cy="224" r="7" fill="var(--muted)" opacity="0.45"/><circle cx="248" cy="214" r="4.5" fill="var(--muted)" opacity="0.45"/>'
    s += lobe(178, 246, 14, 10, p, 'b') + lobe(200, 250, 13, 9, p, 'b')
    s += label(189, 272, 'PER:CRY')
    # back into the nucleus, where they switch CLOCK:BMAL1 off
    s += rep('M164 244 C90 240 70 180 98 136', p)
    s += label(14, 272, '1 brake: period &#8776; 24 h', anchor='start', fill='var(--muted)')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The circadian clock: in the nucleus, CLOCK and BMAL1 switch on the Per and Cry genes; '
            f'the mRNA leaves, PER and CRY are made in the cytoplasm, return and switch CLOCK and BMAL1 off. One braking loop, about a day round." {SVG}>'
            f'{defs(p)}{s}</svg>')


def panel_lac():
    p = 'bfl'
    s = head('amplifying loop', 'the lac operon')
    s += '<rect x="16" y="58" width="268" height="210" rx="48" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.1"/>'
    s += bilayer(70, 51, 160, p)
    # LacY, a helix bundle through the membrane, pumping lactose in
    s += ''.join(f'<rect x="{x}" y="44" width="4.2" height="28" rx="2" fill="url(#{p}ga)"/>' for x in (140, 146, 152, 158, 164))
    s += label(130, 80, 'LacY', anchor='end')
    s += sugar(24, 24) + sugar(44, 18) + sugar(62, 27)
    s += label(14, 44, 'lactose', anchor='start', fill='var(--muted)')
    s += act('M74 28 L136 46', p)
    s += act('M153 73 L153 98', p)
    s += sugar(150, 108)
    # LacI, a tetramer; lactose disables it, it blocks the genes at the operator
    s += ''.join(f'<circle cx="{x}" cy="{y}" r="9" fill="url(#{p}gb)" {LIFT}/>' for x, y in ((96, 150), (112, 150), (96, 166), (112, 166)))
    s += label(104, 192, 'LacI')
    s += rep('M146 114 L124 140', p)
    s += gene(170, 226, 72, p) + '<rect x="158" y="219" width="8" height="14" rx="1.5" fill="var(--accent2)"/>' + helix(60, 250, 226)
    s += label(206, 254, '<tspan font-style="italic">lacZYA</tspan>')
    s += rep('M118 176 L157 216', p)
    s += act('M212 212 C236 150 200 96 172 70', p)
    s += label(190, 150, '(&#8722;)(&#8722;) = (+)', fill='var(--muted)', extra=SERIF)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The lac operon: lactose disables the repressor LacI, LacI blocks the lac genes at the operator, '
            f'and one of those genes makes LacY, the pump that brings lactose in. Two brakes in one loop cancel: an amplifying loop." {SVG}>{defs(p)}{s}</svg>')


def panel_chemotaxis():
    p = 'bfm'
    s = head('running total', 'chemotaxis')
    s += bilayer(20, 60, 260, p)
    # the receptor, a dimer through the membrane with a ligand-binding bulb outside
    s += ''.join(f'<rect x="{x}" y="44" width="9" height="122" rx="4" fill="url(#{p}gg)" stroke="var(--accent)" stroke-width="0.8"/>' for x in (138, 151))
    s += lobe(142, 38, 7, 6, p, 'g') + lobe(156, 38, 7, 6, p, 'g')
    s += ''.join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="var(--accent)"/>' for x, y in ((198, 30), (208, 24), (218, 30)))
    s += label(214, 48, 'attractant', anchor='start', fill='var(--muted)')
    # methyl groups on the receptor: the running total. CheR adds them steadily; CheB, switched on by CheA, removes them
    s += ''.join(tagged(126, y, 'Me') for y in (92, 112, 132))
    s += label(14, 118, 'methyl groups', anchor='start', fill='var(--muted)')
    s += '<line x1="86" y1="116" x2="114" y2="114" stroke="var(--muted)" stroke-width="0.9"/>'
    s += label(54, 86, 'CheR') + act('M72 88 L116 92', p)
    s += label(54, 160, 'CheB') + rep('M72 156 L116 134', p)
    # CheA below the receptor, with its phosphate; it drives the motor and switches CheB on
    s += lobe(146, 196, 13, 9, p) + lobe(164, 200, 12, 8, p) + tagged(182, 186, 'P', r=8)
    s += label(196, 214, 'CheA', anchor='start')
    s += act('M149 168 L149 184', p)
    s += act('M130 198 C100 198 80 190 64 168', p)
    s += act('M152 210 L152 238', p)
    s += label(152, 256, 'run or tumble', fill='var(--muted)')
    s += '<path d="M200 250 q6 -6 12 0 t12 0 t12 0" fill="none" stroke="var(--muted)" stroke-width="1.1"/>'
    s += label(150, 274, 'methyl count &#8776; &#8747; (set point &#8722; activity) dt', fill='var(--muted)', extra=SERIF)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Bacterial chemotaxis: attractant lowers the activity of the receptor and its kinase CheA; '
            f'CheR adds methyl groups to the receptor at a steady rate and CheB, switched on by CheA, removes them, so the methyl count keeps a running total '
            f'of the difference between activity and its set point, and activity returns exactly." {SVG}>{defs(p)}{s}</svg>')


def key():
    arrow = '<svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true"><path d="M2 6H26" stroke="var(--accent-text)" stroke-width="1.6"/><path d="M24 1L32 6L24 11z" fill="var(--accent-text)"/></svg>'
    bar = '<svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true"><path d="M2 6H28" stroke="var(--accent2-text)" stroke-width="1.6"/><path d="M30 1V11" stroke="var(--accent2-text)" stroke-width="2.2"/></svg>'
    dna = '<svg width="34" height="14" viewBox="0 0 34 14" aria-hidden="true">' + helix(2, 32, 7, amp=4, period=16) + '</svg>'
    mem = ('<svg width="34" height="14" viewBox="0 0 34 14" aria-hidden="true"><defs><pattern id="bfkbl" width="6" height="14" patternUnits="userSpaceOnUse">'
           '<circle cx="3" cy="2.6" r="2.2" fill="var(--muted)"/><circle cx="3" cy="11.4" r="2.2" fill="var(--muted)"/>'
           '<path d="M1.9 4.8V9.2M4.1 4.8V9.2" stroke="var(--muted)" stroke-width="0.7"/></pattern></defs><rect width="34" height="14" fill="url(#bfkbl)"/></svg>')
    me = ('<svg width="40" height="20" viewBox="0 0 40 20" aria-hidden="true"><circle cx="10" cy="10" r="9" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.1"/>'
          '<text x="10" y="14" text-anchor="middle" font-size="11" fill="var(--ink)">Me</text><circle cx="31" cy="10" r="8" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.1"/>'
          '<text x="31" y="14" text-anchor="middle" font-size="11" fill="var(--ink)">P</text></svg>')
    rows = [(arrow, 'activates: an amplifying arrow'), (bar, 'represses: a braking arrow'), (dna, 'DNA, a gene banded, its promoter arrow'),
            (mem, 'lipid bilayer'), (me, 'methyl group, phosphate'), ('<span class="bk-int">&#8747;</span>', 'a running total: the integral of what flows in')]
    return ('<div class="bio-key"><p class="pt-h"><b>how to read</b></p>'
            + ''.join(f'<div><span class="bk-g">{g}</span><span>{t}</span></div>' for g, t in rows) + '</div>')


def fig_real_circuits():
    return ('<div class="bio">' + ''.join(f'<div>{x}</div>' for x in (panel_clock(), panel_lac(), panel_chemotaxis()))
            + f'<div>{key()}</div></div>')
