"""Deep circuit figures for every-line-is-a-loop.html: the switch (lac operon), the clock (the circadian loop) and the
adapter (chemotaxis), each as three panes. The cell pane draws the biochemistry the way cell biology draws it, with
flux shown as dots travelling along each reaction arrow at a speed set by the live model (the convention of
Falstad's circuit simulator). The circuit pane draws the same thing as a loop of arrows with its signs. The signal
pane is a strip chart of the model, driven by one slider. Every pane renders a complete first frame without JavaScript
(the traces are computed here), and the script then runs the same equations live.

Python twins of the three models check what the figures claim before the page is built:
  switch:  the lac model flips on at a higher lactose level than it flips off at (hysteresis), and remembers.
  clock:   with an 8 h round-trip delay the loop ticks with a period near a day; with no delay it sits still.
  adapter: after a step of attractant, activity returns to its set point exactly; with a leak it sags.

Usage: python3 analysis/circuit_figures.py            # regenerates the blocks between <!-- gen:NAME --> markers
       python3 analysis/circuit_figures.py --check    # runs the model checks only
"""
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import bio_figures as BF  # noqa: E402
import interactive as IA  # noqa: E402

PAGE = ROOT / 'every-line-is-a-loop.html'
MINUS = '&#8722;'
PW, PH = 350, 300      # cell and circuit panes
SW_, SH = 720, 220     # signal pane, redrawn by the script at the true pixel width
LIFT = 'filter="url(#fx-lift)"'
SERIF = ' style="font-family: var(--serif)" font-style="italic"'


# ================================================================ models (Python twins of the script)
SW = {'beta': 5.0, 'basal': 0.05, 'n': 3, 'tx': 1.0, 'ty': 0.2, 'dt': 0.01, 'win': 40.0, 'speed': 1.5,
      'L0': 0.5, 'sched': [[0.0, 0.5], [6.0, 1.2], [16.0, 0.5]], 'T0': 34.0}   # hours; speed in model hours per wall second


def sw_h(y):
    return SW['basal'] + (1 - SW['basal']) * y ** SW['n'] / (1 + y ** SW['n'])


def sw_step(x, y, L, dt):
    return x + dt * (SW['beta'] * sw_h(y) - x) / SW['tx'], y + dt * (L * x - y) / SW['ty']


def sw_run(schedule, T, x=None, y=None, dt=SW['dt'], every=10):
    """Run under a schedule [[t, L], ...]; returns samples of (t, L, x)."""
    x = SW['beta'] * SW['basal'] if x is None else x
    y = 0.0 if y is None else y
    out, L, k = [], schedule[0][1], 0
    for i in range(int(T / dt) + 1):
        t = i * dt
        while k + 1 < len(schedule) and schedule[k + 1][0] <= t:
            k += 1
        L = schedule[k][1]
        if i % every == 0:
            out.append((t, L, x, y))
        x, y = sw_step(x, y, L, dt)
    return out


def check_switch():
    # slow ramps: where it flips on, where it flips off
    up = sw_run([[0, 0.0]] + [[t, 1.5 * t / 400] for t in range(1, 401)], 400)
    L_up = next(L for t, L, x, y in up if x > 2.5)
    down = sw_run([[0, 1.5]] + [[t, 1.5 * (1 - t / 400)] for t in range(1, 401)], 400, x=3.5, y=5.0)
    L_down = next(L for t, L, x, y in down if x < 2.5)
    assert L_up > L_down + 0.2, (L_up, L_down)
    # the canned schedule: lactose arrives, leaves again, and the cell stays on
    tr = sw_run(SW['sched'], SW['T0'])
    assert tr[-1][1] == SW['L0'] and tr[-1][2] > 3.0, tr[-1]
    assert tr[int(5 / SW['dt'] / 10)][2] < 0.5
    return L_up, L_down


CK = {'K': 0.3, 'n': 4, 'tm': 1.0, 'tc': 1.0, 'tn': 1.0, 'dt': 0.02, 'T': 72.0, 'D': 9.0, 'Dmax': 12.0, 'sweep': 14.0}


def ck_run(D, T=CK['T'], dt=CK['dt'], every=5):
    m, c, n = 0.6, 0.2, 0.05
    hist = []
    nd = int(round(D / dt))
    out = []
    for i in range(int(T / dt) + 1):
        hist.append(n)
        nlag = hist[i - nd] if i - nd >= 0 else hist[0]
        if i % every == 0:
            out.append((i * dt, m, c, n, 1 / (1 + (nlag / CK['K']) ** CK['n'])))
        dm = (1 / (1 + (nlag / CK['K']) ** CK['n']) - m) / CK['tm']
        dc = (m - c) / CK['tc']
        dn = (c - n) / CK['tn']
        m, c, n = m + dt * dm, c + dt * dc, n + dt * dn
    return out


def ck_period(tr, after=24.0):
    ts = [t for t, m, c, n, a in tr if t >= after]
    ns = [n for t, m, c, n, a in tr if t >= after]
    amp = max(ns) - min(ns)
    peaks = [ts[i] for i in range(1, len(ns) - 1) if ns[i] > ns[i - 1] and ns[i] >= ns[i + 1]]
    period = (peaks[-1] - peaks[0]) / (len(peaks) - 1) if len(peaks) > 1 else None
    return amp, period


def check_clock():
    amp, period = ck_period(ck_run(CK['D']))
    assert amp > 0.2 and period and 20 <= period <= 28, (amp, period)
    amp0, _ = ck_period(ck_run(0.0), after=36.0)
    assert amp0 < 0.01, amp0
    return period


AD = {'a': 2.0, 'm0': 2.0, 'kL': 1.0, 'K': 1.0, 'rR': 0.1, 'rB': 0.3, 'dt': 0.02, 'win': 120.0, 'speed': 4.0,
      'leak': 0.02, 'L0': 0.0, 'step': 5.0, 'tstep': 30.0, 'T0': 100.0, 'Lmax': 10.0}


def ad_act(m, L):
    z = AD['a'] * (m - AD['m0']) - AD['kL'] * math.log(1 + L / AD['K'])
    return 1 / (1 + math.exp(-z))


def ad_run(schedule, T, leak=False, m=None, dt=AD['dt'], every=10):
    rR, rB = AD['rR'], AD['rB']
    if m is None:   # start at the set point for the first lactose level
        m = AD['m0'] + (AD['kL'] * math.log(1 + schedule[0][1] / AD['K']) + math.log(rR / (rB - rR))) / AD['a']
    out, k = [], 0
    for i in range(int(T / dt) + 1):
        t = i * dt
        while k + 1 < len(schedule) and schedule[k + 1][0] <= t:
            k += 1
        L = schedule[k][1]
        A = ad_act(m, L)
        if i % every == 0:
            out.append((t, L, A, m))
        m += dt * (rR - rB * A - (AD['leak'] * m if leak else 0))
        m = max(0.0, min(8.0, m))
    return out


def check_adapter():
    sched = [[0, AD['L0']], [AD['tstep'], AD['step']]]
    tr = ad_run(sched, AD['T0'])
    A0 = AD['rR'] / AD['rB']
    dip = min(A for t, L, A, m in tr if t > AD['tstep'])
    assert dip < A0 - 0.1, dip
    assert abs(tr[-1][2] - A0) < 0.005, tr[-1]
    lk = ad_run(sched, AD['T0'], leak=True, m=tr[0][3])
    assert abs(lk[-1][2] - A0) > 0.03, lk[-1]
    return dip, tr[-1][2], lk[-1][2]


def check_all():
    print('switch: flips on at L =', *('%.2f' % v for v in check_switch()))
    print('clock: period at D = %g h is %.1f h; no delay settles' % (CK['D'], check_clock()))
    print('adapter: dips to %.2f, returns to %.3f; with a leak %.3f' % check_adapter())


# ================================================================ drawing helpers
def fx(d, kind, key, width=2.2):
    """A reaction arrow that carries flux: the script puts travelling dots on every path.fx."""
    color = 'var(--accent-text)' if kind == 'act' else 'var(--accent2-text)'
    mk = 'fx-arrow' if kind == 'act' else 'fx-bar'
    return f'<path class="fx" data-k="{key}" d="{d}" fill="none" stroke="{color}" stroke-width="{width}" marker-end="url(#{mk})"/>'


def label(x, y, t, anchor='middle', fill='var(--ink)', size=12, extra=''):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"{extra}>{t}</text>'


def mono(x, y, t, anchor='start', fill='var(--muted)', size=12, extra=''):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{fill}" '
            f'style="font-family: var(--code)"{extra}>{t}</text>')


def pill(x, y, w, t, h=28, sub=None):
    """A named node: a rounded box sized to its name."""
    s = (f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="{h / 2}" fill="var(--paper)" '
         f'stroke="var(--muted)" stroke-width="1.4" {LIFT}/>')
    if sub:
        s += label(x, y + 1, t, size=12.5, extra=' font-weight="600"') + label(x, y + 12, sub, size=10.5, fill='var(--muted)')
    else:
        s += label(x, y + 4.5, t, size=12.5, extra=' font-weight="600"')
    return s


def trim(x1, y1, w1, h1, x2, y2, w2, h2, pad=4):
    """Start and end of a straight edge between two pills, trimmed to their rims."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L

    def exit_dist(w, h):
        tx = (w / 2 + pad) / abs(ux) if ux else 1e9
        ty = (h / 2 + pad) / abs(uy) if uy else 1e9
        return min(tx, ty)
    e1, e2 = exit_dist(w1, h1), exit_dist(w2, h2) + 4
    return x1 + ux * e1, y1 + uy * e1, x2 - ux * e2, y2 - uy * e2, ux, uy


def edge(a, b, kind, key, curve=0, muted=False):
    """a, b = (x, y, w, h). kind act or rep. curve bends the edge sideways (positive = right of travel)."""
    sx, sy, ex, ey, ux, uy = trim(*a, *b)
    if curve:
        mx, my = (sx + ex) / 2 - uy * curve, (sy + ey) / 2 + ux * curve
        d = f'M{sx:.1f} {sy:.1f}Q{mx:.1f} {my:.1f} {ex:.1f} {ey:.1f}'
    else:
        d = f'M{sx:.1f} {sy:.1f}L{ex:.1f} {ey:.1f}'
    if muted:
        return f'<path d="{d}" fill="none" stroke="var(--muted)" stroke-width="1.4" marker-end="url(#fx-arrow-muted)"/>'
    return fx(d, kind, key)


def pane(svg_inner, w, h, aria, extra=''):
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}"{extra}>{svg_inner}</svg>'


def pane_html(kind, title, readout_id, readout_initial, svg):
    """A pane: mono header (what it is | live readout), then the drawing."""
    return (f'<div class="pane pane-{kind}"><div class="pane-h"><span class="pane-k">{title}</span>'
            f'<output class="pane-r" id="{readout_id}" aria-live="off">{readout_initial}</output></div>{svg}</div>')


def sugar(x, y, r=5.2):
    """A disaccharide: two fused hexagons, drawn large enough to read at pane scale."""
    def hexagon(cx, cy):
        pts_ = ' '.join(f'{cx + r * math.cos(math.radians(60 * i)):.1f},{cy + r * math.sin(math.radians(60 * i)):.1f}' for i in range(6))
        return f'<polygon points="{pts_}" fill="var(--paper)" stroke="var(--ink)" stroke-width="1"/>'
    return hexagon(x, y) + hexagon(x + r * 1.75, y)


# ================================================================ the switch (lac operon)
def cell_switch():
    p = 'csw'
    s = BF.defs(p)
    # the cell: a rounded outline with the bilayer along its top edge
    s += '<rect x="22" y="70" width="306" height="212" rx="52" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
    s += BF.bilayer(90, 63, 170, p)
    # LacY, a helix bundle through the membrane
    s += ''.join(f'<rect x="{x}" y="56" width="4.4" height="28" rx="2" fill="url(#{p}ga)"/>' for x in (164, 170.5, 177, 183.5, 190))
    s += label(154, 92, 'LacY', anchor='end', size=12, extra=' font-weight="600"')
    # lactose outside, flowing in through the pump
    s += '<g class="pool" data-k="out">' + ''.join(sugar(x, y) for x, y in ((34, 28), (58, 16), (80, 32), (104, 18), (126, 34))) + '</g>'
    s += label(14, 50, 'lactose outside', anchor='start', fill='var(--muted)', size=12)
    s += fx('M120 34 L160 52', 'act', 'in')
    s += fx('M177 86 L177 118', 'act', 'pump')
    # lactose inside: the pool that the loop fills
    s += '<g class="pool" data-k="y">' + ''.join(sugar(x, y) for x, y in ((170, 130), (194, 140), (166, 152), (190, 162), (214, 152))) + '</g>'
    s += label(190, 182, 'inside', fill='var(--muted)', size=12)
    # LacI, a tetramer; lactose disables it; it blocks the genes at the operator
    s += ''.join(f'<circle cx="{x}" cy="{y}" r="9.5" fill="url(#{p}gb)" {LIFT}/>' for x, y in ((92, 164), (110, 164), (92, 182), (110, 182)))
    s += label(101, 208, 'LacI', size=12, extra=' font-weight="600"')
    s += fx('M164 150 L128 164', 'rep', 'free')
    s += BF.gene(178, 244, 80, p) + '<rect x="166" y="237" width="8" height="14" rx="1.5" fill="var(--accent2)"/>' + BF.helix(60, 300, 244)
    s += label(218, 270, '<tspan font-style="italic">lacZYA</tspan>', size=12)
    s += fx('M116 196 L162 232', 'rep', 'block')
    s += fx('M232 230 C262 170 236 110 200 78', 'act', 'make')
    s += label(246, 118, '(' + MINUS + ')(' + MINUS + ') = (+)', anchor='start', fill='var(--muted)', size=11.5, extra=SERIF)
    return pane(s, PW, PH, 'The lac operon drawn as a cell: lactose outside enters through the LacY pump, lactose inside '
                'disables the repressor LacI, LacI blocks the lacZYA genes, and the genes make more LacY. Two repressions in '
                'one loop cancel: an amplifying loop.', ' data-sim="sw"')


def circuit_switch():
    A, B, C, D = (90, 70, 84, 28), (260, 70, 110, 28), (260, 200, 70, 28), (90, 200, 92, 28)
    s = ''
    s += edge(A, B, 'act', 'pump')
    s += edge(B, C, 'rep', 'free')
    s += edge(C, D, 'rep', 'block')
    s += edge(D, A, 'act', 'make')
    s += pill(*A[:2], A[2], 'LacY') + pill(*B[:2], B[2], 'lactose in') + pill(*C[:2], C[2], 'LacI') + pill(*D[:2], D[2], '<tspan font-style="italic">lacZYA</tspan>')
    s += '<path d="M150 107 a28 28 0 1 1 0.1 0" fill="none" stroke="var(--accent)" stroke-width="1.4" stroke-dasharray="3 3"/>'
    s += label(150, 141, '+', size=16, fill='var(--accent-text)', extra=' font-weight="600"')
    s += mono(20, 276, '1 loop  0 brakes', size=12, fill='var(--ink)')
    return pane(s, PW, PH, 'The same circuit as a loop of four arrows: LacY activates lactose inside, which represses LacI, '
                'which represses lacZYA, which activates LacY. Two repressions cancel: one amplifying loop, no brake.')


def axes(w, h, x0, x1, y0, y1, xlab, ylab, ticks_x, ticks_y, grid=True):
    s = ''
    if grid:
        for tx, _ in ticks_x:
            X = x0 + (x1 - x0) * tx
            s += f'<line x1="{X:.1f}" y1="{y1}" x2="{X:.1f}" y2="{y0}" stroke="var(--rule)" stroke-width="0.8"/>'
        for ty, _ in ticks_y:
            Y = y0 - (y0 - y1) * ty
            s += f'<line x1="{x0}" y1="{Y:.1f}" x2="{x1}" y2="{Y:.1f}" stroke="var(--rule)" stroke-width="0.8"/>'
    s += f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="var(--muted)" stroke-width="1.4"/>'
    s += f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="var(--muted)" stroke-width="1.4"/>'
    for tx, t in ticks_x:
        X = x0 + (x1 - x0) * tx
        s += mono(X, y0 + 15, t, anchor='middle')
    for ty, t in ticks_y:
        Y = y0 - (y0 - y1) * ty
        s += mono(x0 - 6, Y + 4, t, anchor='end')
    s += mono(x1, y0 + 32, xlab, anchor='end')
    s += mono(x0, y1 - 8, ylab, anchor='start', fill='var(--ink)')
    return s


def legend(items, x, y):
    """A key row: each item is (label, colour, width, dash); the swatch is drawn exactly as the series is. Each item is
    a group with its row offset in data-x, so the script can lay the items out again on a narrow pane (positions are
    absolute, not transforms, so every overlap checker sees them where they are)."""
    out, cx = [], x
    for label_, color, width, dash in items:
        d = f' stroke-dasharray="{dash}"' if dash else ''
        out.append(f'<g class="li" data-x="{cx - x:.0f}">'
                   f'<line x1="{cx:.0f}" y1="{y - 4}" x2="{cx + 22:.0f}" y2="{y - 4}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{d}/>'
                   + mono(cx + 28, y, label_, fill='var(--muted)') + '</g>')
        cx += 28 + len(label_) * 7.3 + 18
    return '<g class="legend">' + ''.join(out) + '</g>'


def pts(samples, x0, x1, y0, y1, tmin, tmax, vmin, vmax, ti=0, vi=2):
    out = []
    for sm in samples:
        t, v = sm[ti], sm[vi]
        if t < tmin or t > tmax:
            continue
        X = x0 + (x1 - x0) * (t - tmin) / (tmax - tmin)
        Y = y0 - (y0 - y1) * (v - vmin) / (vmax - vmin)
        out.append(f'{X:.1f},{Y:.1f}')
    return ' '.join(out)


SIG = {'x0': 56, 'x1': SW_ - 16, 'y0': 160, 'y1': 28}


def signal_switch():
    tr = sw_run(SW['sched'], SW['T0'])
    x0, x1, y0, y1 = SIG['x0'], SIG['x1'], SIG['y0'], SIG['y1']
    tmin, tmax = SW['T0'] - SW['win'], SW['T0']
    s = '<g class="ax">' + axes(SW_, SH, x0, x1, y0, y1, 'time, h (the last 40 h)', 'level, relative',
                                [(i / 4, '') for i in range(5)], [(0, '0'), (2.5 / 5.8, '2.5'), (5 / 5.8, '5')]) + '</g>'
    s += f'<polyline class="tr-in" points="{pts(tr, x0, x1, y0, y1, tmin, tmax, 0, 1.6, vi=1)}" fill="none" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="5 4"/>'
    s += f'<polyline class="tr" points="{pts(tr, x0, x1, y0, y1, tmin, tmax, 0, 5.8)}" fill="none" stroke="var(--accent-text)" stroke-width="2.2" stroke-linejoin="round"/>'
    s += f'<circle class="now" cx="{x1}" cy="{y0 - (y0 - y1) * tr[-1][2] / 5.8:.1f}" r="4" fill="var(--accent-text)"/>'
    s += legend([('LacY, the pump', 'var(--accent-text)', 2.2, ''), ('lactose outside (slider)', 'var(--muted)', 1.4, '5 4')], x0, y0 + 32)
    return pane(s, SW_, SH, 'Strip chart of the pump level over the last forty hours: lactose rose at hour 6 and fell back '
                'at hour 16, the pump switched on and has stayed on.', ' data-chart="sw" preserveAspectRatio="none"')


def fig_switch():
    end = sw_run(SW['sched'], SW['T0'])[-1]
    panes = (pane_html('cell', 'cell', 'sw-r1', f'lactose in  {end[3]:.2f}', cell_switch())
             + pane_html('circuit', 'circuit', 'sw-r2', 'shape: 1 loop, 0 brakes', circuit_switch())
             + pane_html('signal', 'signal', 'sw-r3', f'LacY  {end[2]:.2f}  on', signal_switch()))
    ctl = ('<div class="ctl"><label for="sw-L">lactose outside</label>'
           f'<input id="sw-L" type="range" min="0" max="150" value="{int(SW["L0"] * 100)}" aria-label="Lactose outside the cell" style="--p: {SW["L0"] / 1.5 * 100:.0f}%">'
           f'<output for="sw-L" id="sw-Lv">{SW["L0"]:.2f}</output></div>')
    chain = chain_html('1 loop, 0 brakes', 'holds two states', 'commits to a food', brakes=0)
    return f'<div class="deep">{panes}</div>{ctl}{chain}'


# ================================================================ the clock (the circadian loop)
def cell_clock():
    p = 'cck'
    s = BF.defs(p)
    s += '<ellipse cx="175" cy="150" rx="138" ry="92" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
    s += '<ellipse cx="175" cy="150" rx="132" ry="86" fill="none" stroke="var(--muted)" stroke-width="1.4"/>'
    s += label(175, 226, 'nucleus', fill='var(--muted)', size=12)
    s += BF.gene(186, 150, 76, p) + BF.helix(66, 286, 150)
    s += label(224, 180, '<tspan font-style="italic">Per, Cry</tspan>', size=12)
    s += BF.lobe(136, 118, 16, 12, p) + BF.lobe(160, 114, 15, 11, p)
    s += label(146, 92, 'CLOCK:BMAL1', size=12, extra=' font-weight="600"')
    s += fx('M174 122 Q186 124 190 136', 'act', 'on')
    # the mRNA leaves, a ribosome reads it, PER and CRY are made in the cytoplasm
    s += fx('M262 150 C292 150 306 184 300 214 C294 240 272 252 246 258', 'act', 'out', width=1.6)
    s += '<circle cx="262" cy="150" r="2.6" fill="var(--accent-text)"/>'
    s += label(344, 140, 'mRNA', anchor='end', fill='var(--muted)', size=12)
    s += '<circle cx="258" cy="256" r="7.5" fill="var(--muted)" opacity="0.45"/><circle cx="264" cy="245" r="5" fill="var(--muted)" opacity="0.45"/>'
    s += BF.lobe(200, 268, 15, 11, p, 'b') + BF.lobe(224, 272, 14, 10, p, 'b')
    s += label(212, 294, 'PER:CRY', size=12, extra=' font-weight="600"')
    # the pool in the nucleus: PER:CRY that has come back in, sitting on CLOCK:BMAL1
    s += '<g class="pool" data-k="n">' + BF.lobe(96, 136, 12, 9, p, 'b') + BF.lobe(114, 142, 11, 8, p, 'b') + '</g>'
    # back into the nucleus, where they switch CLOCK:BMAL1 off
    s += fx('M184 266 C96 262 70 196 112 132', 'rep', 'back')
    s += label(334, 22, 'one trip round: about a day', anchor='end', fill='var(--muted)', size=12)
    return pane(s, PW, PH, 'The circadian clock drawn as a cell: in the nucleus CLOCK and BMAL1 switch on the Per and Cry '
                'genes; the mRNA leaves, PER and CRY are made in the cytoplasm, return and switch CLOCK and BMAL1 off. '
                'One braking loop, about a day round.', ' data-sim="ck"')


def circuit_clock():
    A, B, C = (90, 80, 118, 28), (270, 80, 90, 28), (180, 200, 96, 28)
    s = edge(A, B, 'act', 'on') + edge(B, C, 'act', 'make') + edge(C, A, 'rep', 'back')
    s += pill(*A[:2], A[2], 'CLOCK:BMAL1') + pill(*B[:2], B[2], '<tspan font-style="italic">Per, Cry</tspan>') + pill(*C[:2], C[2], 'PER:CRY')
    s += '<path d="M180 104 a24 24 0 1 1 0.1 0" fill="none" stroke="var(--accent2)" stroke-width="1.4" stroke-dasharray="3 3"/>'
    s += label(180, 134, MINUS, size=16, fill='var(--accent2-text)', extra=' font-weight="600"')
    s += mono(20, 276, '1 loop  1 brake', size=12, fill='var(--ink)')
    return pane(s, PW, PH, 'The same circuit as a loop of three arrows: CLOCK:BMAL1 activates Per and Cry, which make '
                'PER:CRY, which represses CLOCK:BMAL1. One braking loop.')


def signal_clock():
    tr = ck_run(CK['D'])
    x0, x1, y0, y1 = SIG['x0'], SIG['x1'], SIG['y0'], SIG['y1']
    s = '<g class="ax">' + axes(SW_, SH, x0, x1, y0, y1, 'time, h', 'level, fraction of peak',
                                [(i / 6, str(i * 12)) for i in range(7)], [(0, '0'), (1 / 1.15, '1')]) + '</g>'
    s += f'<polyline class="tr-in" points="{pts(tr, x0, x1, y0, y1, 0, CK["T"], 0, 1.15, vi=4)}" fill="none" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="5 4"/>'
    s += f'<polyline class="tr" points="{pts(tr, x0, x1, y0, y1, 0, CK["T"], 0, 1.15, vi=3)}" fill="none" stroke="var(--accent2-text)" stroke-width="2.2" stroke-linejoin="round"/>'
    s += f'<circle class="now" cx="{x0}" cy="{y0 - (y0 - y1) * tr[0][3] / 1.15:.1f}" r="4" fill="var(--accent2-text)"/>'
    s += legend([('PER:CRY in the nucleus', 'var(--accent2-text)', 2.2, ''), ('CLOCK:BMAL1 activity', 'var(--muted)', 1.4, '5 4')], x0, y0 + 32)
    return pane(s, SW_, SH, 'Three days of the model: PER:CRY in the nucleus rises and falls with a period near a day, '
                'and CLOCK:BMAL1 activity runs opposite to it.', ' data-chart="ck" preserveAspectRatio="none"')


def fig_clock():
    period = check_clock()
    panes = (pane_html('cell', 'cell', 'ck-r1', 'PER:CRY in  0.05', cell_clock())
             + pane_html('circuit', 'circuit', 'ck-r2', 'shape: 1 loop, 1 brake', circuit_clock())
             + pane_html('signal', 'signal', 'ck-r3', f'period  {period:.0f} h', signal_clock()))
    ctl = ('<div class="ctl"><label for="ck-D">the extra wait</label>'
           f'<input id="ck-D" type="range" min="0" max="{int(CK["Dmax"] * 10)}" value="{int(CK["D"] * 10)}" aria-label="Extra delay before PER:CRY acts, in hours" style="--p: 75%">'
           f'<output for="ck-D" id="ck-Dv">{CK["D"]:.1f} h</output></div>')
    chain = chain_html('1 loop, 1 brake', 'keeps time', 'anticipates the day', brakes=1)
    return f'<div class="deep">{panes}</div>{ctl}{chain}'


# ================================================================ the adapter (chemotaxis)
def cell_adapter():
    p = 'cad'
    s = BF.defs(p)
    s += BF.bilayer(20, 66, 310, p)
    # the receptor, a dimer through the membrane with its ligand bulb outside
    s += ''.join(f'<rect x="{x}" y="48" width="9" height="128" rx="4" fill="url(#{p}gg)" stroke="var(--muted)" stroke-width="0.8"/>' for x in (160, 173))
    s += BF.lobe(164, 42, 7, 6, p, 'g') + BF.lobe(178, 42, 7, 6, p, 'g')
    s += '<g class="pool" data-k="L">' + ''.join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="var(--muted)"/>' for x, y in ((214, 30), (226, 22), (238, 32), (250, 24), (262, 34), (224, 40), (246, 42))) + '</g>'
    s += label(272, 50, 'attractant', anchor='start', fill='var(--muted)', size=12)
    # methyl groups on the receptor: the running total
    s += '<g class="pool" data-k="m">' + ''.join(BF.tagged(148, y, 'Me') for y in (92, 112, 132, 152)) + '</g>'
    s += label(18, 126, 'methyl', anchor='start', fill='var(--muted)', size=12) + label(18, 142, 'groups', anchor='start', fill='var(--muted)', size=12)
    s += label(60, 102, 'CheR', size=12, extra=' font-weight="600"') + fx('M80 100 L136 95', 'act', 'add')
    s += label(66, 166, 'CheB', size=12, extra=' font-weight="600"') + fx('M86 160 L136 150', 'rep', 'remove')
    # CheA below the receptor, with its phosphate; it drives the motor and switches CheB on
    s += BF.lobe(168, 206, 14, 10, p) + BF.lobe(188, 210, 13, 9, p) + BF.tagged(208, 196, 'P', r=8)
    s += label(224, 224, 'CheA', anchor='start', size=12, extra=' font-weight="600"')
    s += fx('M170 178 L170 194', 'act', 'act')
    s += fx('M152 208 C120 208 98 196 80 174', 'act', 'cheb')
    s += fx('M176 220 L176 248', 'act', 'motor')
    s += label(176, 266, 'run or tumble', fill='var(--muted)', size=12)
    s += '<path d="M226 258 q6 -6 12 0 t12 0 t12 0" fill="none" stroke="var(--muted)" stroke-width="1.1"/>'
    s += label(176, 288, 'methyl count &#8776; &#8747; (set point ' + MINUS + ' activity) dt', fill='var(--muted)', size=11.5, extra=SERIF)
    return pane(s, PW, PH, 'Bacterial chemotaxis drawn as a cell: attractant lowers the activity of the receptor and its '
                'kinase CheA; CheR adds methyl groups to the receptor at a steady rate and CheB, switched on by CheA, '
                'removes them, so the methyl count keeps a running total and activity returns exactly.', ' data-sim="ad"')


def circuit_adapter():
    A, B, C = (175, 70, 92, 28), (270, 190, 80, 28), (90, 190, 92, 28)
    s = edge(A, B, 'act', 'cheb') + edge(B, C, 'rep', 'remove') + edge(C, A, 'act', 'act')
    s += '<path d="M30 110 L52 176" fill="none" stroke="var(--muted)" stroke-width="1.4" marker-end="url(#fx-arrow-muted)"/>'
    s += label(26, 100, 'CheR, steady', anchor='start', fill='var(--muted)', size=12)
    s += pill(*A[:2], A[2], 'activity') + pill(*B[:2], B[2], 'CheB') + pill(*C[:2], C[2], 'methyl &#8747;')
    s += '<path d="M178 136 a24 24 0 1 1 0.1 0" fill="none" stroke="var(--accent2)" stroke-width="1.4" stroke-dasharray="3 3"/>'
    s += label(178, 166, MINUS, size=16, fill='var(--accent2-text)', extra=' font-weight="600"')
    s += mono(20, 276, '1 loop  1 brake  1 running total', size=12, fill='var(--ink)')
    return pane(s, PW, PH, 'The same circuit as a loop: activity activates CheB, CheB represses the methyl count, the '
                'methyl count activates activity; CheR feeds the count steadily from outside the loop. One braking '
                'loop through a running total.')


def signal_adapter():
    sched = [[0, AD['L0']], [AD['tstep'], AD['step']]]
    tr = ad_run(sched, AD['T0'])
    x0, x1, y0, y1 = SIG['x0'], SIG['x1'], SIG['y0'], SIG['y1']
    tmin, tmax = 0, AD['win']
    s = '<g class="ax">' + axes(SW_, SH, x0, x1, y0, y1, 'time, s (the last 120 s)', 'activity, 0 to 1',
                                [(i / 4, '') for i in range(5)], [(0, '0'), (1 / 3 / 1.15, 'set'), (1 / 1.15, '1')]) + '</g>'
    s += f'<polyline class="tr-in" points="{pts(tr, x0, x1, y0, y1, tmin, tmax, 0, 10.5, vi=1)}" fill="none" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="5 4"/>'
    s += f'<polyline class="tr2" points="{pts(tr, x0, x1, y0, y1, tmin, tmax, 0, 8.4, vi=3)}" fill="none" stroke="var(--accent-text)" stroke-width="1.4"/>'
    s += f'<polyline class="tr" points="{pts(tr, x0, x1, y0, y1, tmin, tmax, 0, 1.15, vi=2)}" fill="none" stroke="var(--accent2-text)" stroke-width="2.2" stroke-linejoin="round"/>'
    s += f'<circle class="now" cx="{x0 + (x1 - x0) * tr[-1][0] / AD["win"]:.1f}" cy="{y0 - (y0 - y1) * tr[-1][2] / 1.15:.1f}" r="4" fill="var(--accent2-text)"/>'
    s += legend([('activity', 'var(--accent2-text)', 2.2, ''), ('methyl count', 'var(--accent-text)', 1.4, ''), ('attractant (slider)', 'var(--muted)', 1.4, '5 4')], x0, y0 + 32)
    return pane(s, SW_, SH, 'Strip chart: attractant steps up at 30 s, receptor activity dips and climbs back to its set '
                'point exactly, while the methyl count ramps to a new level and stays there.', ' data-chart="ad" preserveAspectRatio="none"')


def fig_adapter():
    panes = (pane_html('cell', 'cell', 'ad-r1', 'methyl  2.0', cell_adapter())
             + pane_html('circuit', 'circuit', 'ad-r2', 'shape: 1 loop, 1 brake, &#8747;', circuit_adapter())
             + pane_html('signal', 'signal', 'ad-r3', 'activity  0.333  at set point', signal_adapter()))
    ctl = ('<div class="ctl ctl-2"><label for="ad-L">attractant</label>'
           f'<input id="ad-L" type="range" min="0" max="{int(AD["Lmax"] * 10)}" value="{int(AD["step"] * 10)}" aria-label="Attractant outside the cell" style="--p: 50%">'
           f'<output for="ad-L" id="ad-Lv">{AD["step"]:.1f}</output>'
           '<button type="button" class="chip tog" id="ad-leak" aria-pressed="false">let the count leak</button></div>')
    chain = chain_html('1 loop, 1 brake, &#8747;', 'adapts exactly', 'steers up a gradient', brakes=1, integ=True)
    return f'<div class="deep">{panes}</div>{ctl}{chain}'


# ================================================================ shared pieces
def glyph(word, color='var(--ink)', dashed=False):
    dash = ' stroke-dasharray="3 2"' if dashed else ''
    return (f'<svg class="gl" width="32" height="16" viewBox="0 0 32 16" aria-hidden="true"><path d="{IA.TRACE[word]}" fill="none" '
            f'stroke="{color}" stroke-width="1.6" stroke-linecap="round"{dash}/></svg>')


def shape_glyph(brakes, integ=False):
    """A ring in the loop's colour with its sign, and the integral sign when the loop runs through a running total."""
    color = 'var(--accent2-text)' if brakes else 'var(--accent-text)'
    sign = MINUS if brakes else '+'
    extra = f'<text x="29" y="13" font-size="10" fill="var(--ink)" style="font-family: var(--serif)" font-style="italic">&#8747;</text>' if integ else ''
    return (f'<svg class="gl gl-w" width="44" height="18" viewBox="0 0 44 18" aria-hidden="true"><circle cx="9" cy="9" r="5.6" fill="none" stroke="{color}" stroke-width="1.6"/>'
            f'<text x="19" y="13.5" font-size="12" font-weight="600" fill="{color}">{sign}</text>{extra}</svg>')


def chain_html(shape, pattern, function, brakes=0, integ=False):
    return ('<div class="chain" aria-label="Shape, pattern, function">'
            f'<span class="ch"><span class="ch-k">shape</span><span class="ch-v">{shape_glyph(brakes, integ)}{shape}</span></span>'
            '<span class="ch-a" aria-hidden="true">&#8594;</span>'
            f'<span class="ch"><span class="ch-k">pattern</span><span class="ch-v">{glyph(pattern)}{pattern}</span></span>'
            '<span class="ch-a" aria-hidden="true">&#8594;</span>'
            f'<span class="ch"><span class="ch-k">function</span><span class="ch-v">{function}</span></span></div>')


def defs_html():
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
            '<filter id="fx-lift" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="1.6" stdDeviation="2.2" style="flood-color: var(--lift)"/></filter>'
            '<radialGradient id="fx-orb" cx="36%" cy="30%" r="72%"><stop offset="0" style="stop-color: var(--orb-hi)"/><stop offset="0.5" style="stop-color: var(--accent)"/><stop offset="1" style="stop-color: var(--orb-lo)"/></radialGradient>'
            '<marker id="fx-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--accent-text)"/></marker>'
            '<marker id="fx-arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--muted)"/></marker>'
            '<marker id="fx-arrow-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--ink)"/></marker>'
            '<marker id="fx-bar" viewBox="0 0 3 10" refX="2" refY="5" markerWidth="3" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M1.5 0V10" stroke="var(--accent2-text)" stroke-width="2.2"/></marker>'
            '<marker id="fx-bar-muted" viewBox="0 0 3 10" refX="2" refY="5" markerWidth="3" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M1.5 0V10" stroke="var(--muted)" stroke-width="2.2"/></marker>'
            '</defs></svg>')


# ================================================================ the frame figure (shape, pattern, function)
def fig_frame():
    """Three small panes: a shape (a loop of two arrows), a pattern (its trace), a function (what the cell gets)."""
    w, h = 230, 150

    def p(inner, aria):
        return f'<div>{pane(inner, w, h, aria)}</div>'
    a = (edge((70, 60, 40, 26), (160, 60, 40, 26), 'act', 'x', curve=-22) + edge((160, 60, 40, 26), (70, 60, 40, 26), 'rep', 'x', curve=-22)
         + pill(70, 60, 40, 'A') + pill(160, 60, 40, 'B'))
    a = a.replace('class="fx" ', '')
    a += mono(115, 128, 'shape', anchor='middle', fill='var(--ink)', size=12)
    b = (f'<path d="{IA.trace_path("keeps time", 60, 50)}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-linecap="round" transform="translate(-60 -50) scale(1) translate(60 50)"/>')
    b = (f'<g transform="translate(40 32) scale(4.8 3.2)"><path d="{IA.TRACE["keeps time"]}" fill="none" stroke="var(--ink)" stroke-width="0.6" stroke-linecap="round"/></g>')
    b += mono(115, 128, 'pattern', anchor='middle', fill='var(--ink)', size=12)
    c = ('<rect x="62" y="22" width="106" height="72" rx="30" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
         + label(115, 54, 'keep time', size=12.5, extra=' font-weight="600"') + label(115, 72, 'remember', size=12.5, extra=' font-weight="600"'))
    c = ('<rect x="62" y="20" width="106" height="76" rx="32" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
         + label(115, 50, 'remember', size=12, extra=' font-weight="600"') + label(115, 66, 'keep time', size=12, extra=' font-weight="600"')
         + label(115, 82, 'steer', size=12, extra=' font-weight="600"'))
    c += mono(115, 128, 'function', anchor='middle', fill='var(--ink)', size=12)
    return ('<div class="trio-f">' + p(a, 'Shape: two molecules in a loop, one arrow activates, one represses')
            + '<div class="trio-a" aria-hidden="true">&#8594;</div>' + p(b, 'Pattern: the level traces a wave in time')
            + '<div class="trio-a" aria-hidden="true">&#8594;</div>' + p(c, 'Function: the cell remembers, keeps time or steers') + '</div>'
            + '<div class="keyrow"><span><svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true"><path d="M2 6H31" stroke="var(--accent-text)" stroke-width="2.2" marker-end="url(#fx-arrow)"/></svg>activates, amplifies</span>'
            '<span><svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true"><path d="M2 6H30" stroke="var(--accent2-text)" stroke-width="2.2" marker-end="url(#fx-bar)"/></svg>represses, brakes</span>'
            '<span><svg width="34" height="12" viewBox="0 0 34 12" aria-hidden="true"><path d="M2 6H30" stroke="var(--accent2-text)" stroke-width="2.2" stroke-dasharray="4 4" marker-end="url(#fx-bar)"/></svg>a brake that is lost (Figure 7)</span></div>')


# ================================================================ three diseases, one algebra
def fig_disease():
    w, h = 230, 236

    def panel(title, a_name, b_name, foot, aria):
        A, B = (60, 70, 62, 26), (170, 70, 62, 26)
        s = label(115, 22, title, size=13, extra=' font-weight="600"')
        s += edge(A, B, 'act', 'x', curve=-22).replace('class="fx" ', '')
        s += (f'<path d="M150 90 Q115 122 80 90" fill="none" stroke="var(--accent2)" stroke-width="2.2" stroke-dasharray="4 4" marker-end="url(#fx-bar)"/>')
        s += pill(*A[:2], A[2], a_name) + pill(*B[:2], B[2], b_name)
        s += label(115, 44, '+ held on', size=12, fill='var(--accent-text)')
        s += label(115, 134, MINUS + ' lost', size=12, fill='var(--accent2-text)')
        s += f'<line x1="20" y1="196" x2="210" y2="196" stroke="var(--muted)" stroke-width="1.4"/>'
        s += '<path d="M20 194 H60 C100 192 150 164 210 142" fill="none" stroke="var(--accent-text)" stroke-width="2.2"/>'
        s += mono(210, 212, 'time', anchor='end')
        s += label(115, 230, foot, fill='var(--muted)', size=12)
        return f'<div>{pane(s, w, h, aria)}</div>'
    return ('<div class="trio-f trio-d">'
            + panel('Cancer', 'grow', 'p53', 'divisions count up and never return',
                    'Cancer: a growth switch held on, its brake p53 lost; divisions ramp without return')
            + panel('Autoimmunity', 'T eff', 'T reg', 'a memory with no brake',
                    'Autoimmunity: effector T cells held on, regulatory T cells lost; the response ramps')
            + panel('Neurodegeneration', 'seed', 'clear', 'and neurons never divide it away',
                    'Neurodegeneration: seeded aggregation held on, clearance lost, no reset; the response ramps')
            + '</div>')


# ================================================================ hero: three live traces
def hero():
    sw = sw_run(SW['sched'], SW['T0'])
    ck = ck_run(CK['D'])
    ad = ad_run([[0, AD['L0']], [AD['tstep'], AD['step']]], AD['T0'])
    w, h = 230, 70

    def strip(name, word, points, color, after):
        return (f'<div class="hs"><svg viewBox="0 0 {w} {h}" role="img" aria-label="{name}: {after}">'
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" pathLength="1" class="hs-tr"/>'
                f'</svg><div class="hs-l"><span class="hs-n">{name}</span><span class="hs-w">{glyph(word, color)}{after}</span></div></div>')
    a = pts(sw, 8, w - 8, h - 8, 10, 0, SW['T0'], 0, 4.2)
    b = pts(ck, 8, w - 8, h - 8, 10, 0, CK['T'], 0, 1.05, vi=3)
    c = pts(ad, 8, w - 8, h - 8, 10, 0, AD['T0'], 0, 1.05, vi=2)
    return ('<div class="hero-row">' + strip('switch', 'holds two states', a, 'var(--accent-text)', 'flips once, stays')
            + strip('clock', 'keeps time', b, 'var(--accent2-text)', 'one brake, ticks')
            + strip('adapter', 'adapts exactly', c, 'var(--accent2-text)', 'returns exactly') + '</div>')


# ================================================================ the script
def script():
    P = {'sw': SW, 'ck': CK, 'ad': AD, 'sig': SIG}
    return '<script>\n(function () {\n  var P = ' + json.dumps(P) + ''';
  var NS = 'http://www.w3.org/2000/svg';
  var RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function $(id) { return document.getElementById(id); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function setP(input) { var r = (input.value - input.min) / (input.max - input.min); input.style.setProperty('--p', (r * 100).toFixed(1) + '%'); }

  // ---- flux: dots travelling along every reaction arrow of a cell pane, at a speed set by the model
  function Flux(svg) {
    this.items = [];
    var self = this;
    svg.querySelectorAll('path.fx').forEach(function (p) {
      var len = p.getTotalLength(), n = Math.max(2, Math.round(len / 24)), g = document.createElementNS(NS, 'g');
      g.setAttribute('class', 'dots');
      var dots = [];
      for (var i = 0; i < n; i++) {
        var c = document.createElementNS(NS, 'circle'), p0 = p.getPointAtLength(0);
        c.setAttribute('r', '2.4'); c.setAttribute('fill', p.getAttribute('stroke')); c.setAttribute('cx', p0.x.toFixed(1)); c.setAttribute('cy', p0.y.toFixed(1)); c.setAttribute('opacity', '0');
        g.appendChild(c); dots.push(c);
      }
      p.parentNode.insertBefore(g, p.nextSibling);
      self.items.push({ k: p.getAttribute('data-k'), p: p, len: len, n: n, dots: dots, off: 0 });
    });
    this.pools = {};
    svg.querySelectorAll('g.pool').forEach(function (g) { self.pools[g.getAttribute('data-k')] = Array.prototype.slice.call(g.children); });
  }
  Flux.prototype.draw = function (rates, pools, dtWall) {
    this.items.forEach(function (f) {
      var r = clamp(rates[f.k] || 0, 0, 1), sp = f.len / f.n;
      if (!RM) f.off = (f.off + dtWall * 70 * r) % sp;
      for (var i = 0; i < f.n; i++) {
        var s = (f.off + i * sp) % f.len, d = f.dots[i];
        if (s > f.len - 9) { d.setAttribute('opacity', '0'); continue; }
        var pt = f.p.getPointAtLength(s);
        d.setAttribute('cx', pt.x.toFixed(1)); d.setAttribute('cy', pt.y.toFixed(1));
        d.setAttribute('opacity', (0.18 + 0.82 * r).toFixed(2));
      }
    });
    for (var k in pools) {
      var els = this.pools[k]; if (!els) continue;
      var v = clamp(pools[k], 0, 1) * els.length;
      els.forEach(function (e, i) { e.setAttribute('opacity', clamp(v - i, 0, 1).toFixed(2)); });
    }
  };

  // ---- a strip chart redrawn at the pane's true pixel width
  function Chart(svg, win, ymax, ymax2, inmax) {
    this.svg = svg; this.win = win; this.ymax = ymax; this.ymax2 = ymax2; this.inmax = inmax;
    this.tr = svg.querySelector('.tr'); this.tr2 = svg.querySelector('.tr2'); this.trin = svg.querySelector('.tr-in'); this.now = svg.querySelector('.now');
    this.ax = svg.querySelector('.ax'); this.buf = [];
    this.fit();
  }
  Chart.prototype.fit = function () {
    var w = Math.max(300, this.svg.clientWidth || 720), S = P.sig;
    this.svg.setAttribute('viewBox', '0 0 ' + w + ' 220'); this.svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
    this.x0 = S.x0; this.x1 = w - 16; this.y0 = S.y0; this.y1 = S.y1;
    var self = this, ticks = this.ax.querySelectorAll('text');
    // x ticks were placed at fractions of the old width: re-place them, and the axis line, and the x label
    this.ax.querySelectorAll('line').forEach(function (l) {
      var x1 = +l.getAttribute('x1'), x2 = +l.getAttribute('x2');
      if (x1 === x2 && x1 > S.x0) { var f = (x1 - S.x0) / (704 - S.x0); l.setAttribute('x1', (self.x0 + (self.x1 - self.x0) * f).toFixed(1)); l.setAttribute('x2', l.getAttribute('x1')); }
      else if (x1 !== x2) l.setAttribute('x2', (x2 > 100 ? self.x1 : x2));
    });
    ticks.forEach(function (t) {
      var x = +t.getAttribute('x');
      if (t.getAttribute('text-anchor') === 'end' && x > 100) t.setAttribute('x', self.x1);
      else if (t.getAttribute('text-anchor') === 'middle') { var f = (x - S.x0) / (704 - S.x0); t.setAttribute('x', (self.x0 + (self.x1 - self.x0) * f).toFixed(1)); }
    });
    // on a narrow pane the note drops under the axis label instead of running into it
    var items = this.svg.querySelectorAll('.legend .li'), narrow = w < 600, ly = S.y0 + 32;
    items.forEach(function (g, i) {
      var lx = narrow ? S.x0 : S.x0 + (+g.getAttribute('data-x')), y = narrow ? ly + 16 + 14 * i : ly, ln = g.querySelector('line'), tx = g.querySelector('text');
      ln.setAttribute('x1', lx); ln.setAttribute('x2', lx + 22); ln.setAttribute('y1', y - 4); ln.setAttribute('y2', y - 4);
      tx.setAttribute('x', lx + 28); tx.setAttribute('y', y);
    });
    this.svg.setAttribute('viewBox', '0 0 ' + w + ' ' + (narrow ? 220 + 14 * items.length : 220));
  };
  Chart.prototype.push = function (t, v, v2, vin) { this.buf.push([t, v, v2, vin]); var t0 = t - this.win; while (this.buf.length && this.buf[0][0] < t0) this.buf.shift(); };
  Chart.prototype.draw = function (tNow, fixed) {
    var x0 = this.x0, x1 = this.x1, y0 = this.y0, y1 = this.y1, win = this.win, ymax = this.ymax, ymax2 = this.ymax2, inmax = this.inmax;
    var tmin = fixed ? 0 : tNow - win, a = [], b = [], c = [];
    for (var i = 0; i < this.buf.length; i++) {
      var s = this.buf[i], X = (x0 + (x1 - x0) * (s[0] - tmin) / win).toFixed(1);
      a.push(X + ',' + (y0 - (y0 - y1) * s[1] / ymax).toFixed(1));
      if (this.tr2 && s[2] != null) b.push(X + ',' + (y0 - (y0 - y1) * s[2] / ymax2).toFixed(1));
      if (this.trin && s[3] != null) c.push(X + ',' + (y0 - (y0 - y1) * s[3] / inmax).toFixed(1));
    }
    this.tr.setAttribute('points', a.join(' '));
    if (this.tr2) this.tr2.setAttribute('points', b.join(' '));
    if (this.trin) this.trin.setAttribute('points', c.join(' '));
    var last = this.buf[this.buf.length - 1];
    if (last && this.now) { this.now.setAttribute('cx', (x0 + (x1 - x0) * (last[0] - tmin) / win).toFixed(1)); this.now.setAttribute('cy', (y0 - (y0 - y1) * last[1] / ymax).toFixed(1)); }
  };

  // ---- the switch: the lac operon
  var sw = (function () {
    var Q = P.sw, el = $('sw-L'); if (!el) return null;
    var st = { x: Q.beta * Q.basal, y: 0, L: Q.L0, t: 0 }, chart = new Chart(document.querySelector('svg[data-chart="sw"]'), Q.win, 4.2, null, 1.6);
    var flux = new Flux(document.querySelector('svg[data-sim="sw"]'));
    function h(y) { var p = Math.pow(y, Q.n); return Q.basal + (1 - Q.basal) * p / (1 + p); }
    function step(dt) { var hx = h(st.y); st.x += dt * (Q.beta * hx - st.x) / Q.tx; st.y += dt * (st.L * st.x - st.y) / Q.ty; st.t += dt; }
    function advance(hours) { var n = Math.round(hours / Q.dt); for (var i = 0; i < n; i++) { step(Q.dt); if (i % 10 === 0) chart.push(st.t, st.x, null, st.L); } }
    // replay the recorded history so the chart starts where the first frame left it
    var k = 0; for (var t = 0; t < Q.T0; t += 1) { while (k + 1 < Q.sched.length && Q.sched[k + 1][0] <= t) k++; st.L = Q.sched[k][1]; advance(1); }
    st.L = Q.L0; chart.draw(st.t);
    function readouts() {
      $('sw-r1').textContent = 'lactose in  ' + st.y.toFixed(2);
      $('sw-r3').textContent = 'LacY  ' + st.x.toFixed(2) + (st.x > 2 ? '  on' : st.x < 0.6 ? '  off' : '  deciding');
    }
    function paint(dtWall) {
      var hx = h(st.y);
      flux.draw({ 'in': st.L / 1.5, pump: clamp(st.L * st.x / 4, 0, 1), free: hx, block: 1 - hx, make: hx }, { out: st.L / 1.5, y: st.y / 4 }, dtWall);
      chart.draw(st.t);
    }
    el.addEventListener('input', function () {
      st.L = el.value / 100; $('sw-Lv').textContent = st.L.toFixed(2); setP(el);
      if (RM) { advance(20); paint(0); readouts(); }
    });
    paint(0); readouts();
    return { tick: function (dtWall) { advance(dtWall * Q.speed); paint(dtWall); }, readouts: readouts, chart: chart, box: el.closest('figure') };
  })();

  // ---- the clock: the circadian loop, recomputed for three days whenever the delay moves; a playhead sweeps it
  var ck = (function () {
    var Q = P.ck, el = $('ck-D'); if (!el) return null;
    var chart = new Chart(document.querySelector('svg[data-chart="ck"]'), Q.T, 1.15, null, 1.15);
    var flux = new Flux(document.querySelector('svg[data-sim="ck"]'));
    var run = [], D = Q.D, ph = 0, period = null;
    function compute() {
      var m = 0.6, c = 0.2, n = 0.05, hist = [], nd = Math.round(D / Q.dt), N = Math.round(Q.T / Q.dt);
      run = []; chart.buf = [];
      for (var i = 0; i <= N; i++) {
        hist.push(n);
        var nlag = i - nd >= 0 ? hist[i - nd] : hist[0], act = 1 / (1 + Math.pow(nlag / Q.K, Q.n));
        if (i % 5 === 0) { run.push([i * Q.dt, m, c, n, act]); chart.push(i * Q.dt, n, null, act); }
        var dm = (act - m) / Q.tm, dc = (m - c) / Q.tc, dn = (c - n) / Q.tn;
        m += Q.dt * dm; c += Q.dt * dc; n += Q.dt * dn;
      }
      // period from the peaks after the first day
      var ts = [], ns = [];
      run.forEach(function (r) { if (r[0] >= 24) { ts.push(r[0]); ns.push(r[3]); } });
      var peaks = [], lo = Math.min.apply(null, ns), hi = Math.max.apply(null, ns);
      for (var j = 1; j < ns.length - 1; j++) if (ns[j] > ns[j - 1] && ns[j] >= ns[j + 1]) peaks.push(ts[j]);
      period = (hi - lo > 0.02 && peaks.length > 1) ? (peaks[peaks.length - 1] - peaks[0]) / (peaks.length - 1) : null;
      chart.draw(0, true);
      $('ck-r3').textContent = period ? 'period  ' + period.toFixed(0) + ' h' : 'settles  no tick';
      $('ck-r2').textContent = 'shape: 1 loop, 1 brake' + (period ? '' : ', too quick');
    }
    function at(t) { var i = clamp(Math.round(t / Q.dt / 5), 0, run.length - 1); return run[i]; }
    function paint(dtWall) {
      var r = at(ph), act = r[4];
      flux.draw({ on: act, out: r[1], make: r[1], back: Math.pow(r[3] / Q.K, Q.n) / (1 + Math.pow(r[3] / Q.K, Q.n)) }, { n: r[3] / 0.9 }, dtWall);
      if (chart.now) { chart.now.setAttribute('cx', (chart.x0 + (chart.x1 - chart.x0) * ph / Q.T).toFixed(1)); chart.now.setAttribute('cy', (chart.y0 - (chart.y0 - chart.y1) * r[3] / 1.15).toFixed(1)); }
    }
    function readouts() { $('ck-r1').textContent = 'PER:CRY in  ' + at(ph)[3].toFixed(2); }
    el.addEventListener('input', function () { D = el.value / 10; $('ck-Dv').textContent = D.toFixed(1) + ' h'; setP(el); compute(); paint(0); readouts(); });
    compute(); ph = RM ? 30 : 0; paint(0); readouts();
    return { tick: function (dtWall) { ph = (ph + dtWall * Q.T / Q.sweep) % Q.T; paint(dtWall); }, readouts: readouts, chart: chart, box: el.closest('figure') };
  })();

  // ---- the adapter: chemotaxis
  var ad = (function () {
    var Q = P.ad, el = $('ad-L'); if (!el) return null;
    var leak = false, tog = $('ad-leak');
    var chart = new Chart(document.querySelector('svg[data-chart="ad"]'), Q.win, 1.15, 8.4, 10.5);
    var flux = new Flux(document.querySelector('svg[data-sim="ad"]'));
    var A0 = Q.rR / Q.rB;
    var st = { m: Q.m0 + (Q.kL * Math.log(1 + Q.L0 / Q.K) + Math.log(Q.rR / (Q.rB - Q.rR))) / Q.a, L: Q.L0, t: 0 };
    function act(m, L) { var z = Q.a * (m - Q.m0) - Q.kL * Math.log(1 + L / Q.K); return 1 / (1 + Math.exp(-z)); }
    function step(dt) { var A = act(st.m, st.L); st.m += dt * (Q.rR - Q.rB * A - (leak ? Q.leak * st.m : 0)); st.m = clamp(st.m, 0, 8); st.t += dt; }
    function advance(sec) { var n = Math.round(sec / Q.dt); for (var i = 0; i < n; i++) { step(Q.dt); if (i % 10 === 0) chart.push(st.t, act(st.m, st.L), st.m, st.L); } }
    st.L = Q.L0; advance(Q.tstep); st.L = Q.step; advance(Q.T0 - Q.tstep); chart.draw(st.t);
    function readouts() {
      var A = act(st.m, st.L), d = A - A0;
      $('ad-r1').textContent = 'methyl  ' + st.m.toFixed(1);
      $('ad-r3').textContent = 'activity  ' + A.toFixed(3) + (Math.abs(d) < 0.004 ? '  at set point' : d < 0 ? '  below' : '  above');
    }
    function paint(dtWall) {
      var A = act(st.m, st.L);
      flux.draw({ add: Q.rR / Q.rR * 0.5, remove: Q.rB * A / Q.rR * 0.5, act: A, cheb: A, motor: A }, { m: st.m / 6, L: st.L / Q.Lmax }, dtWall);
      chart.draw(st.t);
    }
    el.addEventListener('input', function () { st.L = el.value / 10; $('ad-Lv').textContent = st.L.toFixed(1); setP(el); if (RM) { advance(60); paint(0); readouts(); } });
    tog.addEventListener('click', function () { leak = !leak; tog.setAttribute('aria-pressed', leak ? 'true' : 'false'); if (RM) { advance(60); paint(0); readouts(); } });
    paint(0); readouts();
    return { tick: function (dtWall) { advance(dtWall * Q.speed); paint(dtWall); }, readouts: readouts, chart: chart, box: el.closest('figure') };
  })();

  // ---- one loop for all three; a figure runs only while it is on screen
  var sims = [sw, ck, ad].filter(Boolean), last = null, frame = 0;
  sims.forEach(function (s) { s.on = !('IntersectionObserver' in window); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { sims.forEach(function (s) { if (s.box === e.target) s.on = e.isIntersecting; }); }); }, { rootMargin: '80px' });
    sims.forEach(function (s) { if (s.box) io.observe(s.box); });
  }
  function loop(now) {
    var dt = last == null ? 0 : clamp((now - last) / 1000, 0, 0.05); last = now; frame++;
    sims.forEach(function (s) { if (!s.on) return; s.tick(dt); if (frame % 6 === 0) s.readouts(); });
    requestAnimationFrame(loop);
  }
  if (!RM) requestAnimationFrame(loop);
  var ro = 'ResizeObserver' in window ? new ResizeObserver(function () { sims.forEach(function (s) { s.chart.fit(); s.chart.draw(s.chart.buf.length ? s.chart.buf[s.chart.buf.length - 1][0] : 0, s === ck); }); }) : null;
  if (ro) sims.forEach(function (s) { ro.observe(s.chart.svg); });
  document.querySelectorAll('.ctl input[type=range]').forEach(setP);
})();
</script>'''


# ================================================================ injection
BLOCKS = {'defs': defs_html, 'hero': hero, 'frame': fig_frame, 'switch': fig_switch, 'clock': fig_clock,
          'adapter': fig_adapter, 'disease': fig_disease, 'script': script}


def inject(page=PAGE):
    s = page.read_text(encoding='utf-8')
    for name, fn in BLOCKS.items():
        pat = re.compile(r'(<!-- gen:' + name + r' -->).*?(<!-- /gen:' + name + r' -->)', re.S)
        assert pat.search(s), name
        body = fn()
        s = pat.sub(lambda m: m.group(1) + '\n' + body + '\n' + m.group(2), s, count=1)
    page.write_text(s, encoding='utf-8')
    print('injected', ', '.join(BLOCKS), 'into', page.name)


if __name__ == '__main__':
    check_all()
    if '--check' not in sys.argv:
        inject()
