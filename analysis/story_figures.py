"""Small explanatory figures for count-the-elements.html: what a model is, a line closing into a loop, what
amplify and brake mean, the count-the-brakes rule, cruise control (a running total), a two-way street versus
a roundabout (the loops the filters remove), and a coastline measured with two rulers (why a loop count
depends on the drawing). Four colours: ink = content; muted gray = secondary, axes, not found; lavender = amplify in
strokes and text, found in fills; amber = brake. Arrowheads and bars are the page's shared markers (fx-arrow, fx-bar,
fx-arrow-muted, fx-arrow-ink), so every figure draws them at one size.

Reads: nothing.
Writes: nothing; it returns SVG and HTML strings, imported by build_post.py.
Run: imported, not run.
"""

from __future__ import annotations

import math

SVG = ''  # the stylesheet gives every svg the page's sans
MINUS = '&#8722;'


def _node(x, y, t, r=22, fs=14):
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
        f'<text x="{x:.1f}" y="{y + fs * 0.36:.1f}" text-anchor="middle" font-size="{fs}" fill="var(--ink)">{t}</text>'
    )


def _edge(x1, y1, x2, y2, r1, r2, mk, color=None, w=2.2, curve=0):
    """Arrow from circle 1 to circle 2, trimmed to their rims; curve bends it sideways. The stroke takes the
    marker's meaning: amber for a bar (represses), lavender for an arrow (activates), unless a colour is given."""
    color = color or ('var(--accent2-text)' if mk == 'fx-bar' else 'var(--accent-text)')
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
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" {SVG} font-size="14">'
        f'<text x="{w / 2}" y="22" text-anchor="middle" font-weight="600" fill="var(--ink)">{title}</text>{inner}</svg>'
    )


def _wrap(panels, cls='quad'):
    return f'<div class="{cls}">' + ''.join(f'<div>{p}</div>' for p in panels) + '</div>'


# ---------------------------------------------------------------- what a model is
def fig_model() -> str:
    """The story's model figure: four small panels of nodes and arrows."""
    tri = [(100, 70), (148, 150), (52, 150)]
    names = ['lacI', 'tetR', 'cI']
    cell = (
        '<rect x="14" y="40" width="172" height="148" rx="44" fill="var(--tint)" stroke="var(--muted)" stroke-width="1.4"/>'
        + ''.join(_node(x, y, t) for (x, y), t in zip(tri, names))
    )
    p1 = _panel(
        200,
        230,
        'A circuit: three genes inside a cell',
        cell + '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">three genes in a cell</text>',
        'a circuit',
    )
    arrows = ''.join(_edge(*tri[i], *tri[(i + 1) % 3], 22, 22, 'fx-bar') for i in range(3))
    p2 = _panel(
        200,
        230,
        'A diagram: each gene switches off the next',
        arrows
        + ''.join(_node(x, y, t) for (x, y), t in zip(tri, names))
        + '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">who slows whom</text>',
        'a diagram',
    )
    eq = (
        '<text x="100" y="78" text-anchor="middle" font-size="14" fill="var(--ink)">change in tetR</text>'
        '<text x="100" y="104" text-anchor="middle" font-size="14" fill="var(--ink)">= made &#8722; removed</text>'
        '<text x="100" y="140" text-anchor="middle" font-size="14" fill="var(--muted)">made falls</text>'
        '<text x="100" y="160" text-anchor="middle" font-size="14" fill="var(--muted)">as lacI rises</text>'
        '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">one rate per arrow</text>'
    )
    p3 = _panel(
        200,
        230,
        'Equations: the change in tetR is what is made minus what is removed, and making falls as lacI rises',
        eq,
        'equations',
    )
    pts = ' '.join(
        f'{20 + i * 1.6:.1f},{120 - 40 * math.sin(i * 1.6 / 160 * 2 * math.pi * 2.6):.1f}' for i in range(101)
    )
    run = (
        f'<line x1="20" y1="170" x2="180" y2="170" stroke="var(--muted)"/><line x1="20" y1="60" x2="20" y2="170" stroke="var(--muted)"/>'
        f'<polyline points="{pts}" fill="none" stroke="var(--ink)" stroke-width="1.8"/>'
        '<text x="100" y="190" text-anchor="middle" font-size="14" fill="var(--muted)">time</text>'
        '<text x="100" y="218" text-anchor="middle" fill="var(--muted)">it blinks</text>'
    )
    p4 = _panel(
        200,
        230,
        'A run: the computer plays the equations forward and the level of a protein rises and falls',
        run,
        'a run',
    )
    return _wrap([p1, p2, p3, p4])


# ---------------------------------------------------------------- a line becomes a loop


# ---------------------------------------------------------------- amplify and brake


# ---------------------------------------------------------------- count the brakes


# ---------------------------------------------------------------- cruise control
def cruise() -> dict:
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


# ---------------------------------------------------------------- two-way street and roundabout
def fig_street() -> str:
    """Figure of the street-crossing example."""
    road = (
        '<rect x="70" y="72" width="190" height="44" rx="6" fill="var(--tint)" stroke="var(--muted)" stroke-width="1.4"/>'
        '<line x1="80" y1="94" x2="250" y2="94" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="10 8"/>'
    )
    road += (
        '<line x1="96" y1="83" x2="232" y2="83" stroke="var(--muted)" stroke-width="2.2" marker-end="url(#fx-arrow-muted)"/>'
        '<line x1="234" y1="105" x2="98" y2="105" stroke="var(--muted)" stroke-width="2.2" marker-end="url(#fx-arrow-muted)"/>'
    )
    road += _node(46, 94, 'E') + _node(284, 94, 'ES')
    a = _panel(
        330,
        190,
        'A two-way street between E and ES: out and back, not a loop',
        road + '<text x="165" y="168" text-anchor="middle" fill="var(--muted)">out and back: filtered out</text>',
        'a two-way street',
    )
    ring = '<circle cx="165" cy="98" r="48" fill="none" stroke="var(--tint)" stroke-width="22"/><circle cx="165" cy="98" r="48" fill="none" stroke="var(--muted)" stroke-width="1.4"/>'
    for a0 in (20, 140, 260):
        a1 = a0 + 95
        x0_, y0_ = 165 + 48 * math.sin(math.radians(a0)), 98 - 48 * math.cos(math.radians(a0))
        x1_, y1_ = 165 + 48 * math.sin(math.radians(a1)), 98 - 48 * math.cos(math.radians(a1))
        ring += f'<path d="M{x0_:.1f} {y0_:.1f}A48 48 0 0 1 {x1_:.1f} {y1_:.1f}" fill="none" stroke="var(--ink)" stroke-width="2.2" marker-end="url(#fx-arrow-ink)"/>'
    b = _panel(
        330,
        190,
        'A roundabout: traffic goes all the way round, a real loop',
        ring + '<text x="165" y="168" text-anchor="middle" fill="var(--muted)">all the way round: kept</text>',
        'a roundabout',
    )
    return f'<div class="pair"><div>{a}</div><div>{b}</div></div>'


# ---------------------------------------------------------------- coastline
