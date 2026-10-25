"""Small explanatory figures for count-the-elements.html: what a model is, a line closing into a loop, what
amplify and brake mean, the count-the-brakes rule, cruise control (a running total), a two-way street versus
a roundabout (the loops the filters remove), and a coastline measured with two rulers (why a loop count
depends on the drawing). Three colours only: ink, muted gray, lavender accent."""
import math

SVG = 'font-family="Inter, Helvetica, Arial, sans-serif"'
MINUS = '&#8722;'


def _defs(p):
    return (f'<defs><marker id="{p}a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0 0L10 5L0 10z" fill="var(--accent)"/></marker>'
            f'<marker id="{p}i" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
            f'<path d="M8 0V10" stroke="var(--accent)" stroke-width="2.4"/></marker>'
            f'<marker id="{p}m" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0 0L10 5L0 10z" fill="var(--muted)"/></marker></defs>')


def _node(x, y, t, r=17, fs=13):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.25"/>'
            f'<text x="{x:.1f}" y="{y + fs * 0.36:.1f}" text-anchor="middle" font-size="{fs}" fill="var(--ink)">{t}</text>')


def _edge(x1, y1, x2, y2, r1, r2, mk, color='var(--accent)', w=2, curve=0):
    """Arrow from circle 1 to circle 2, trimmed to their rims; curve bends it sideways."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    sx, sy = x1 + ux * (r1 + 2), y1 + uy * (r1 + 2)
    ex, ey = x2 - ux * (r2 + 4), y2 - uy * (r2 + 4)
    if curve:
        mx, my = (sx + ex) / 2 - uy * curve, (sy + ey) / 2 + ux * curve
        return f'<path d="M{sx:.1f} {sy:.1f}Q{mx:.1f} {my:.1f} {ex:.1f} {ey:.1f}" fill="none" stroke="{color}" stroke-width="{w}" marker-end="url(#{mk})"/>'
    return f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{color}" stroke-width="{w}" marker-end="url(#{mk})"/>'


def _panel(w, h, label, inner, title):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" {SVG} font-size="14">'
            f'<text x="{w / 2}" y="22" text-anchor="middle" font-weight="600" fill="var(--ink)">{title}</text>{inner}</svg>')


def _wrap(panels, cls='quad'):
    return f'<div class="{cls}">' + ''.join(f'<div>{p}</div>' for p in panels) + '</div>'


# ---------------------------------------------------------------- what a model is
def fig_model():
    tri = [(100, 70), (148, 150), (52, 150)]
    names = ['lacI', 'tetR', 'cI']
    cell = ('<rect x="14" y="40" width="172" height="148" rx="44" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1.3"/>'
            + ''.join(_node(x, y, t, 21, 14) for (x, y), t in zip(tri, names)))
    p1 = _panel(200, 230, 'A circuit: three genes inside a cell', cell + '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">three genes in a cell</text>', 'a circuit')
    arrows = ''.join(_edge(*tri[i], *tri[(i + 1) % 3], 21, 21, 'mdi') for i in range(3))
    p2 = _panel(200, 230, 'A diagram: each gene switches off the next', _defs('md') + arrows + ''.join(_node(x, y, t, 21, 14) for (x, y), t in zip(tri, names))
                + '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">who slows whom</text>', 'a diagram')
    eq = ('<text x="100" y="78" text-anchor="middle" font-size="14" fill="var(--ink)">change in tetR</text>'
          '<text x="100" y="104" text-anchor="middle" font-size="14" fill="var(--ink)">= made &#8722; removed</text>'
          '<text x="100" y="140" text-anchor="middle" font-size="14" fill="var(--muted)">made falls</text>'
          '<text x="100" y="160" text-anchor="middle" font-size="14" fill="var(--muted)">as lacI rises</text>'
          '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">one rate per arrow</text>')
    p3 = _panel(200, 230, 'Equations: the change in tetR is what is made minus what is removed, and making falls as lacI rises', eq, 'equations')
    pts = ' '.join(f'{20 + i * 1.6:.1f},{120 - 40 * math.sin(i * 1.6 / 160 * 2 * math.pi * 2.6):.1f}' for i in range(101))
    run = (f'<line x1="20" y1="170" x2="180" y2="170" stroke="var(--muted)"/><line x1="20" y1="60" x2="20" y2="170" stroke="var(--muted)"/>'
           f'<polyline points="{pts}" fill="none" stroke="var(--ink)" stroke-width="1.8"/>'
           '<text x="100" y="190" text-anchor="middle" font-size="14" fill="var(--muted)">time</text>'
           '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">it blinks</text>')
    p4 = _panel(200, 230, 'A run: the computer plays the equations forward and the level of a protein rises and falls', run, 'a run')
    return _wrap([p1, p2, p3, p4])


# ---------------------------------------------------------------- a line becomes a loop
def fig_line_loop():
    d = _defs('ll')
    line = d + ''.join(_node(x, 90, t) for x, t in ((55, 'A'), (165, 'B'), (275, 'C')))
    line += _edge(55, 90, 165, 90, 17, 17, 'llm', 'var(--muted)') + _edge(165, 90, 275, 90, 17, 17, 'llm', 'var(--muted)')
    a = _panel(330, 170, 'A line: A acts on B, B acts on C, and nothing comes back', line + '<text x="165" y="150" text-anchor="middle" fill="var(--muted)">cause, then effect</text>', 'a line')
    pts = [(165, 50), (225, 120), (105, 120)]
    loop = _defs('lk') + _edge(*pts[0], *pts[1], 17, 17, 'lkm', 'var(--muted)', curve=-10) + _edge(*pts[1], *pts[2], 17, 17, 'lkm', 'var(--muted)', curve=-10)
    loop += _edge(*pts[2], *pts[0], 17, 17, 'lka', 'var(--accent)', 2.4, curve=-10)
    loop += ''.join(_node(x, y, t) for (x, y), t in zip(pts, 'ABC'))
    b = _panel(330, 170, 'A loop: C acts back on A, so the effect returns to its cause', loop + '<text x="165" y="160" text-anchor="middle" fill="var(--muted)">the effect comes back</text>', 'a loop')
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'


# ---------------------------------------------------------------- amplify and brake
def _gauges(x, ha, hb, mk, label, title):
    inner = _defs(mk[:2]) + _node(95, 66, 'A') + _node(235, 66, 'B') + _edge(95, 66, 235, 66, 17, 17, mk)
    for gx, h, t in ((95, ha, 'A'), (235, hb, 'B')):
        inner += (f'<rect x="{gx - 14}" y="100" width="28" height="64" rx="4" fill="none" stroke="var(--muted)"/>'
                  f'<rect x="{gx - 14}" y="{164 - h}" width="28" height="{h}" rx="4" fill="var(--accent)"/>'
                  f'<text x="{gx}" y="184" text-anchor="middle" font-size="12.5" fill="var(--muted)">level of {t}</text>')
    inner += f'<text x="165" y="212" text-anchor="middle" fill="var(--ink)">{label}</text>'
    return _panel(330, 224, f'{title}: {label}', inner, title)


def fig_arrows():
    a = _gauges(0, 56, 52, 'gaa', 'more A, more B', 'amplify (+)')
    b = _gauges(0, 56, 12, 'gbi', 'more A, less B', f'brake ({MINUS})')
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'


# ---------------------------------------------------------------- count the brakes
def fig_parity():
    panels = []
    for k in range(4):
        pts = [(100, 62), (152, 148), (48, 148)]
        inner = _defs(f'p{k}')
        for i in range(3):
            mk = f'p{k}i' if i < k else f'p{k}a'
            inner += _edge(*pts[i], *pts[(i + 1) % 3], 17, 17, mk)
        inner += ''.join(_node(x, y, '') for x, y in pts)
        verdict = 'brakes' if k % 2 else 'amplifies'
        inner += (f'<text x="100" y="196" text-anchor="middle" fill="var(--muted)">{k} brake{"" if k == 1 else "s"}</text>'
                  f'<text x="100" y="218" text-anchor="middle" font-weight="600" fill="var(--accent-text)">loop {verdict}</text>')
        panels.append(_panel(200, 230, f'A loop with {k} brakes {verdict}', inner, ['no brakes', 'one brake', 'two brakes', 'three brakes'][k]))
    return _wrap(panels)


# ---------------------------------------------------------------- cruise control
def cruise():
    """Car on a hill from t = 10 s: dv/dt = 0.5 (u - 0.02 v) - hill. Proportional control settles short;
    adding a running total of the shortfall brings it back to the set speed exactly."""
    out = {}
    for name, ki in (('simple', 0.0), ('total', 0.06)):
        v, s, dt, tr = 60.0, 0.0, 0.02, []
        for i in range(int(80 / dt) + 1):
            t = i * dt
            e = 60 - v
            s += e * dt
            u = 1.2 + 0.6 * e + ki * s
            hill = 0.6 if t >= 10 else 0.0
            if i % 10 == 0:
                tr.append((t, v))
            v += dt * (0.5 * (u - 0.02 * v) - hill)
        out[name] = tr
    return out


def fig_cruise():
    tr = cruise()
    x0, x1, y0, y1 = 56, 312, 40, 186
    X = lambda t: x0 + (x1 - x0) * t / 80
    Y = lambda v: y1 - (y1 - y0) * (v - 54) / (62 - 54)
    inner = (f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--muted)"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="var(--muted)"/>'
             f'<line x1="{x0}" y1="{Y(60):.1f}" x2="{x1}" y2="{Y(60):.1f}" stroke="var(--muted)" stroke-dasharray="4 4"/>')
    for v in (56, 58, 60):
        inner += f'<text x="{x0 - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="12.5" fill="var(--muted)">{v}</text>'
    for t in (0, 20, 40, 60, 80):
        inner += f'<text x="{X(t):.1f}" y="{y1 + 18}" text-anchor="middle" font-size="12.5" fill="var(--muted)">{t}</text>'
    inner += (f'<text x="{(x0 + x1) / 2}" y="{y1 + 38}" text-anchor="middle" font-size="12.5" fill="var(--muted)">seconds (the hill starts at 10)</text>'
              f'<text x="{x0 - 8}" y="{y0 - 10}" text-anchor="end" font-size="12.5" fill="var(--muted)">speed</text>')
    for name, color, w in (('simple', 'var(--muted)', 1.8), ('total', 'var(--accent)', 2.4)):
        pts = ' '.join(f'{X(t):.1f},{Y(v):.1f}' for t, v in tr[name])
        inner += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{w}"/>'
    ends = {k: tr[k][-1][1] for k in tr}
    inner += (f'<text x="{x1}" y="{Y(ends["simple"]) + 18:.1f}" text-anchor="end" font-size="13" fill="var(--muted)">simple: settles short</text>'
              f'<text x="{x1}" y="{Y(60) - 8:.1f}" text-anchor="end" font-size="13" fill="var(--accent-text)">running total: back to 60</text>')
    svg = (f'<svg viewBox="0 0 330 240" role="img" aria-label="Cruise control on a hill: a simple controller settles a little under the set speed; one that keeps a running total of the shortfall returns exactly to it" {SVG} font-size="14">{inner}</svg>')
    assert abs(ends['total'] - 60) < 0.05 and 57 < ends['simple'] < 59.5, ends
    return f'<div class="solo">{svg}</div>', ends


# ---------------------------------------------------------------- two-way street and roundabout
def fig_street():
    d = _defs('st')
    road = ('<rect x="70" y="72" width="190" height="44" rx="6" fill="var(--tint)" stroke="var(--muted)"/>'
            '<line x1="80" y1="94" x2="250" y2="94" stroke="var(--muted)" stroke-dasharray="10 8"/>')
    road += (f'<line x1="96" y1="83" x2="232" y2="83" stroke="var(--accent)" stroke-width="2" marker-end="url(#sta)"/>'
             f'<line x1="234" y1="105" x2="98" y2="105" stroke="var(--accent)" stroke-width="2" marker-end="url(#sta)"/>')
    road += _node(46, 94, 'E', 17) + _node(284, 94, 'ES', 19)
    a = _panel(330, 190, 'A two-way street between E and ES: out and back, not a loop', d + road + '<text x="165" y="168" text-anchor="middle" fill="var(--muted)">out and back: filtered out</text>', 'a two-way street')
    ring = '<circle cx="165" cy="98" r="48" fill="none" stroke="var(--tint)" stroke-width="22"/><circle cx="165" cy="98" r="48" fill="none" stroke="var(--muted)" stroke-width="1"/>'
    for a0 in (20, 140, 260):
        a1 = a0 + 95
        x0_, y0_ = 165 + 48 * math.sin(math.radians(a0)), 98 - 48 * math.cos(math.radians(a0))
        x1_, y1_ = 165 + 48 * math.sin(math.radians(a1)), 98 - 48 * math.cos(math.radians(a1))
        ring += f'<path d="M{x0_:.1f} {y0_:.1f}A48 48 0 0 1 {x1_:.1f} {y1_:.1f}" fill="none" stroke="var(--accent)" stroke-width="2.2" marker-end="url(#sta)"/>'
    b = _panel(330, 190, 'A roundabout: traffic goes all the way round, a real loop', d + ring + '<text x="165" y="168" text-anchor="middle" fill="var(--muted)">all the way round: kept</text>', 'a roundabout')
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'


# ---------------------------------------------------------------- coastline
def _coast():
    pts = [(20.0, 100.0), (310.0, 100.0)]
    import random
    rnd = random.Random(7)
    for depth in range(6):
        new = []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            L = math.hypot(xb - xa, yb - ya)
            off = rnd.uniform(-0.36, 0.36) * L
            nx, ny = -(yb - ya) / L, (xb - xa) / L
            new += [(xa, ya), (mx + nx * off, my + ny * off)]
        new.append(pts[-1])
        pts = new
    return pts


def fig_coast():
    pts = _coast()
    path = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    def ruler(n):
        idx = [round(i * (len(pts) - 1) / n) for i in range(n + 1)]
        sel = [pts[i] for i in idx]
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(sel, sel[1:]))
        return ' '.join(f'{x:.1f},{y:.1f}' for x, y in sel), L
    coarse, Lc = ruler(4)
    fine, Lf = ruler(32)
    def panel(rp, title, label, color):
        inner = (f'<polyline points="{path}" fill="none" stroke="var(--muted)" stroke-width="1.2"/>'
                 f'<polyline points="{rp}" fill="none" stroke="{color}" stroke-width="2.2"/>'
                 + ''.join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="2.6" fill="{color}"/>' for p in rp.split()))
        return _panel(330, 168, f'{title}: {label}', inner + f'<text x="165" y="158" text-anchor="middle" fill="var(--muted)">{label}</text>', title)
    a = panel(coarse, 'a long ruler', 'skips the bays: a short coast', 'var(--ink)')
    b = panel(fine, 'a short ruler', 'follows the bays: a longer coast', 'var(--accent)')
    assert Lf > Lc * 1.25, (Lc, Lf)
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'
