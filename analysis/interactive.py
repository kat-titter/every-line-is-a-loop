"""Interactive figures for count-the-elements.html: plain SVG drawn on the server, updated by small inline
scripts (no libraries, no network). Each renders a complete first frame without JavaScript.

loop_toy:  a three-gene ring; click an arrow to flip it between amplify and brake. The ring is simulated live,
           dx_i/dt = beta f(x_{i-1}) - x_i with f = x^n/(1+x^n) (amplify) or 1/(1+x^n) (brake), beta = 4,
           n = 4, from two starting states. Even brakes: the two starts end in different states (a switch).
           Odd brakes: both keep swinging (a clock).
cruise:    cruise control on a hill of adjustable slope, with and without a running total of the shortfall.
coast:     a coastline measured with rulers of 2 to 64 steps.
"""
import json
import math

SVG = 'font-family="Inter, Helvetica, Arial, sans-serif"'
MINUS = '−'


# ---------------------------------------------------------------- three-gene ring
TOY = {'beta': 4.0, 'n': 4.0, 'hi': 2.5, 'lo': 0.2, 'T': 40.0, 'dt': 0.01}


def starts_for(signs):
    """Two starts, each near one of the two patterns a ring with these signs could hold: X high, and X low.
    Gene g is regulated by gene g-1 with sign signs[g]; a negative ring cannot hold either, and swings."""
    out = []
    for x_high in (True, False):
        hs = [x_high]
        for g in (1, 2):
            hs.append(hs[-1] if signs[g] > 0 else not hs[-1])
        out.append([TOY['hi'] if h else TOY['lo'] for h in hs])
    return out


def simulate_ring(signs, beta=TOY['beta'], n=TOY['n'], T=TOY['T'], dt=TOY['dt']):
    """Python twin of the page's simulation, used to check what the figure claims."""
    out = []
    for x0 in starts_for(signs):
        x = list(x0)
        tr = []
        for i in range(int(T / dt)):
            prev = [x[2], x[0], x[1]]
            f = [(p ** n / (1 + p ** n)) if s > 0 else (1 / (1 + p ** n)) for p, s in zip(prev, signs)]
            x = [xi + dt * (beta * fi - xi) for xi, fi in zip(x, f)]
            if i % 10 == 0:
                tr.append(x[0])
        out.append(tr)
    return out


def check_ring():
    """Even brakes: the two starts end apart and still. Odd brakes: both keep swinging."""
    import itertools
    for signs in itertools.product((1, -1), repeat=3):
        k = signs.count(-1)
        a, b = simulate_ring(list(signs))
        late = lambda tr: tr[len(tr) // 2:]
        swing = lambda tr: max(late(tr)) - min(late(tr))
        if k % 2 == 0:
            assert swing(a) < 0.01 and swing(b) < 0.01 and abs(a[-1] - b[-1]) > 1.0, (k, a[-1], b[-1])
        else:
            assert swing(a) > 0.5 and swing(b) > 0.5, (k, swing(a), swing(b))
    return True


def loop_toy():
    check_ring()
    pts = [(165, 58), (240, 178), (90, 178)]
    names = ['TetR', 'LacI', 'cI']  # the repressilator's three repressors
    nodes = ''.join(f'<circle cx="{x}" cy="{y}" r="22" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.25"/>'
                    f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="15" fill="var(--ink)">{t}</text>' for (x, y), t in zip(pts, names))
    arrows = ''
    for i in range(3):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % 3]
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        sx, sy, ex, ey = x1 + ux * 25, y1 + uy * 25, x2 - ux * 28, y2 - uy * 28
        mx, my = (sx + ex) / 2, (sy + ey) / 2
        arrows += (f'<g class="arr" data-i="{i}" role="button" tabindex="0" aria-label="arrow from {names[i]} to {names[(i + 1) % 3]}">'
                   f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="transparent" stroke-width="44"/>'
                   f'<circle cx="{mx - uy * 18:.1f}" cy="{my + ux * 18:.1f}" r="22" fill="transparent"/>'
                   f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="var(--accent)" stroke-width="2.4" marker-end="url(#lt-a)"/>'
                   f'<circle cx="{mx - uy * 18:.1f}" cy="{my + ux * 18:.1f}" r="12" fill="var(--paper)" stroke="var(--accent)"/>'
                   f'<text x="{mx - uy * 18:.1f}" y="{my + ux * 18 + 5:.1f}" text-anchor="middle" font-size="15" font-weight="600" fill="var(--accent-text)">+</text></g>')
    defs = ('<defs><marker id="lt-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0L10 5L0 10z" fill="var(--accent)"/></marker><marker id="lt-i" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
            '<path d="M8 0V10" stroke="var(--accent2)" stroke-width="2.4"/></marker></defs>')
    ring = (f'<svg id="lt-ring" viewBox="0 0 330 230" role="img" aria-label="A ring of three genes; click an arrow to flip it" {SVG}>{defs}{arrows}{nodes}'
            '<text id="lt-verdict" x="165" y="222" text-anchor="middle" font-size="15" font-weight="600" fill="var(--accent-text)"></text></svg>')
    plot = (f'<svg id="lt-plot" viewBox="0 0 330 230" role="img" aria-label="Level of X over time from two starts" {SVG}>'
            '<line x1="44" y1="190" x2="316" y2="190" stroke="var(--muted)"/><line x1="44" y1="30" x2="44" y2="190" stroke="var(--muted)"/>'
            '<text x="38" y="36" text-anchor="end" font-size="12.5" fill="var(--muted)">high</text>'
            '<text x="38" y="190" text-anchor="end" font-size="12.5" fill="var(--muted)">low</text>'
            '<text x="180" y="210" text-anchor="middle" font-size="12.5" fill="var(--muted)">time</text>'
            '<text x="44" y="18" font-size="12.5" fill="var(--muted)">level of TetR, from two starts</text>'
            '<polyline id="lt-a0" fill="none" stroke="var(--accent)" stroke-width="2.2"/>'
            '<polyline id="lt-a1" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-dasharray="5 4"/>'
            '<text id="lt-out" x="180" y="226" text-anchor="middle" font-size="13" fill="var(--ink)"></text></svg>')
    js = '''<script>
(function () {
  var P = ''' + json.dumps(TOY) + ''';
  var signs = [1, 1, -1];
  var ring = document.getElementById('lt-ring');
  function starts() {
    var out = [];
    [true, false].forEach(function (xh) {
      var hs = [xh];
      for (var g = 1; g < 3; g++) hs.push(signs[g] > 0 ? hs[g - 1] : !hs[g - 1]);
      out.push(hs.map(function (h) { return h ? P.hi : P.lo; }));
    });
    return out;
  }
  function sim(x0) {
    var x = x0.slice(), tr = [], steps = Math.round(P.T / P.dt);
    for (var i = 0; i < steps; i++) {
      var prev = [x[2], x[0], x[1]], nx = [];
      for (var g = 0; g < 3; g++) {
        var p = Math.pow(prev[g], P.n), f = signs[g] > 0 ? p / (1 + p) : 1 / (1 + p);
        nx.push(x[g] + P.dt * (P.beta * f - x[g]));
      }
      x = nx;
      if (i % 10 === 0) tr.push(x[0]);
    }
    return tr;
  }
  function draw() {
    var k = 0;
    [].forEach.call(ring.querySelectorAll('.arr'), function (g) {
      var s = signs[+g.dataset.i], lines = g.querySelectorAll('line');
      lines[1].setAttribute('marker-end', s > 0 ? 'url(#lt-a)' : 'url(#lt-i)');
      lines[1].setAttribute('stroke', s > 0 ? 'var(--accent)' : 'var(--accent2)');
      g.querySelectorAll('circle')[1].setAttribute('stroke', s > 0 ? 'var(--accent)' : 'var(--accent2)');
      g.querySelector('text').setAttribute('fill', s > 0 ? 'var(--accent-text)' : 'var(--accent2-text)');
      g.querySelector('text').textContent = s > 0 ? '+' : '\\u2212';
      g.setAttribute('aria-pressed', String(s < 0));
      if (s < 0) k++;
    });
    document.getElementById('lt-verdict').textContent = k + (k === 1 ? ' brake: ' : ' brakes: ') + (k % 2 ? 'a braking loop' : 'an amplifying loop');
    var top = P.beta, runs = starts().map(sim), late = function (t) { return t.slice(Math.floor(t.length / 2)); };
    runs.forEach(function (tr, r) {
      var pts = tr.map(function (v, i) { return (44 + 272 * i / (tr.length - 1)).toFixed(1) + ',' + (190 - 160 * Math.min(v, top) / top).toFixed(1); }).join(' ');
      document.getElementById('lt-a' + r).setAttribute('points', pts);
    });
    var swing = function (t) { var l = late(t); return Math.max.apply(null, l) - Math.min.apply(null, l); };
    var still = swing(runs[0]) < 0.01 && swing(runs[1]) < 0.01;
    document.getElementById('lt-out').textContent = still ? (Math.abs(runs[0][runs[0].length - 1] - runs[1][runs[1].length - 1]) > 1 ? 'two starts, two end states: a switch' : 'both settle: one state') : 'keeps swinging: a clock';
  }
  function flip(g) { var i = +g.dataset.i; signs[i] = -signs[i]; draw(); }
  ring.addEventListener('click', function (e) { var g = e.target.closest('.arr'); if (g) flip(g); });
  ring.addEventListener('keydown', function (e) { var g = e.target.closest('.arr'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); flip(g); } });
  draw();
})();
</script>'''
    return f'<div class="pair interactive"><div>{ring}</div><div>{plot}</div></div>' + js


# ---------------------------------------------------------------- cruise control
def cruise_curves(hill, ki):
    v, s, dt, tr = 60.0, 0.0, 0.02, []
    for i in range(int(80 / dt) + 1):
        t = i * dt
        e = 60 - v
        s += e * dt
        u = 1.2 + 0.6 * e + ki * s
        if i % 10 == 0:
            tr.append(v)
        v += dt * (0.5 * (u - 0.02 * v) - (hill if t >= 10 else 0.0))
    return tr


def cruise():
    a, b = cruise_curves(0.6, 0.0), cruise_curves(0.6, 0.06)
    assert abs(b[-1] - 60) < 0.05 and 57 < a[-1] < 59.5
    plot = (f'<svg id="cc-plot" viewBox="0 0 330 240" role="img" aria-label="Speed over time on a hill, with a simple controller and with a running total" {SVG}>'
            '<line x1="56" y1="186" x2="312" y2="186" stroke="var(--muted)"/><line x1="56" y1="34" x2="56" y2="186" stroke="var(--muted)"/>'
            '<line x1="56" y1="55.7" x2="312" y2="55.7" stroke="var(--muted)" stroke-dasharray="4 4"/>'
            '<text x="48" y="59.7" text-anchor="end" font-size="12.5" fill="var(--muted)">60</text>'
            '<text x="48" y="190" text-anchor="end" font-size="12.5" fill="var(--muted)">48</text>'
            '<text x="48" y="24" text-anchor="end" font-size="12.5" fill="var(--muted)">speed</text>'
            '<text x="184" y="208" text-anchor="middle" font-size="12.5" fill="var(--muted)">80 seconds; the hill starts at 10</text>'
            '<polyline id="cc-s" fill="none" stroke="var(--muted)" stroke-width="1.8"/>'
            '<polyline id="cc-t" fill="none" stroke="var(--accent)" stroke-width="2.4"/>'
            '<text id="cc-ls" x="312" y="150" text-anchor="end" font-size="13" fill="var(--muted)"></text>'
            '<text id="cc-lt" x="312" y="46" text-anchor="end" font-size="13" fill="var(--accent-text)">running total: back to 60</text></svg>')
    ctl = ('<div class="ctl"><label for="cc-hill">hill</label>'
           '<input id="cc-hill" type="range" min="0" max="1.4" step="0.1" value="0.6" aria-label="steepness of the hill">'
           '<output id="cc-o" for="cc-hill"></output></div>')
    js = '''<script>
(function () {
  function curve(hill, ki) {
    var v = 60, s = 0, dt = 0.02, tr = [];
    for (var i = 0; i <= 4000; i++) {
      var t = i * dt, e = 60 - v; s += e * dt;
      var u = 1.2 + 0.6 * e + ki * s;
      if (i % 10 === 0) tr.push(v);
      v += dt * (0.5 * (u - 0.02 * v) - (t >= 10 ? hill : 0));
    }
    return tr;
  }
  var Y = function (v) { return 186 - 152 * (v - 48) / 14; };   // 48 at the axis, 60 at the dashed line (y = 55.7)
  function draw() {
    var hill = +document.getElementById('cc-hill').value;
    document.getElementById('cc-o').textContent = hill.toFixed(1);
    var s = curve(hill, 0), t = curve(hill, 0.06);
    var pts = function (tr) { return tr.map(function (v, i) { return (56 + 256 * i / (tr.length - 1)).toFixed(1) + ',' + Math.max(34, Math.min(186, Y(v))).toFixed(1); }).join(' '); };
    document.getElementById('cc-s').setAttribute('points', pts(s));
    document.getElementById('cc-t').setAttribute('points', pts(t));
    var end = s[s.length - 1];
    var ls = document.getElementById('cc-ls');
    ls.textContent = 'simple: settles at ' + end.toFixed(1);
    ls.setAttribute('y', Math.min(178, Y(end) + 18).toFixed(1));
  }
  document.getElementById('cc-hill').addEventListener('input', draw);
  draw();
})();
</script>'''
    return f'<div class="solo interactive">{plot}{ctl}</div>' + js


# ---------------------------------------------------------------- coastline
def coast_points():
    import random
    rnd = random.Random(7)
    pts = [(20.0, 100.0), (310.0, 100.0)]
    for _ in range(7):
        new = []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            L = math.hypot(xb - xa, yb - ya)
            off = rnd.uniform(-0.34, 0.34) * L
            nx, ny = -(yb - ya) / L, (xb - xa) / L
            new += [(xa, ya), (mx + nx * off, my + ny * off)]
        new.append(pts[-1])
        pts = new
    return pts


def coast():
    pts = coast_points()
    lo = min(y for _, y in pts); hi = max(y for _, y in pts)
    pts = [(x, 40 + (y - lo) * 110 / (hi - lo)) for x, y in pts]
    def length(n):
        idx = [round(i * (len(pts) - 1) / n) for i in range(n + 1)]
        sel = [pts[i] for i in idx]
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(sel, sel[1:]))
    L = {n: length(n) for n in (2, 4, 8, 16, 32, 64)}
    assert all(L[a] < L[b] for a, b in ((2, 4), (4, 8), (8, 16), (16, 32), (32, 64))), L
    plot = (f'<svg id="co-plot" viewBox="0 0 330 200" role="img" aria-label="A coastline measured with a ruler of adjustable length" {SVG}>'
            '<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) + '" fill="none" stroke="var(--muted)" stroke-width="1.1"/>'
            '<polyline id="co-r" fill="none" stroke="var(--accent)" stroke-width="2.2"/><g id="co-d"></g>'
            '<text id="co-out" x="165" y="190" text-anchor="middle" font-size="13.5" fill="var(--ink)"></text></svg>')
    ctl = ('<div class="ctl"><label for="co-n">ruler</label>'
           '<input id="co-n" type="range" min="1" max="6" step="1" value="2" aria-label="number of ruler steps, from 2 to 64">'
           '<output id="co-o" for="co-n"></output></div>')
    js = '''<script>
(function () {
  var P = ''' + json.dumps([[round(x, 1), round(y, 1)] for x, y in pts]) + ''';
  function sel(n) { var out = []; for (var i = 0; i <= n; i++) out.push(P[Math.round(i * (P.length - 1) / n)]); return out; }
  function len(s) { var L = 0; for (var i = 1; i < s.length; i++) L += Math.hypot(s[i][0] - s[i - 1][0], s[i][1] - s[i - 1][1]); return L; }
  var base = len(sel(2));
  function draw() {
    var n = Math.pow(2, +document.getElementById('co-n').value), s = sel(n);
    document.getElementById('co-r').setAttribute('points', s.map(function (p) { return p[0] + ',' + p[1]; }).join(' '));
    document.getElementById('co-d').innerHTML = s.map(function (p) { return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="2.6" fill="var(--accent)"/>'; }).join('');
    document.getElementById('co-o').textContent = n + ' steps';
    document.getElementById('co-out').textContent = 'measured length: ' + (len(s) / base).toFixed(2) + ' \\u00d7 the 2-step length';
  }
  document.getElementById('co-n').addEventListener('input', draw);
  draw();
})();
</script>'''
    return f'<div class="solo interactive">{plot}{ctl}</div>' + js, L


# ---------------------------------------------------------------- amplify and brake, with a slider
def gauges():
    def panel(pid, title, label, arrow):
        nodes = ''.join(f'<circle cx="{x}" cy="62" r="18" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.25"/>'
                        f'<text x="{x}" y="67" text-anchor="middle" font-size="14" fill="var(--ink)">{t}</text>' for x, t in ((95, 'A'), (235, 'B')))
        col = 'var(--accent)' if arrow == 'ga-a' else 'var(--accent2)'
        mk = f'<line x1="116" y1="62" x2="209" y2="62" stroke="{col}" stroke-width="2.2" marker-end="url(#{arrow})"/>'
        bars = ''.join(f'<rect x="{x - 14}" y="96" width="28" height="70" rx="4" fill="none" stroke="var(--muted)"/>'
                       f'<rect id="{pid}-{t}" x="{x - 14}" y="131" width="28" height="35" rx="4" fill="var(--accent)"/>'
                       f'<text x="{x}" y="186" text-anchor="middle" font-size="12.5" fill="var(--muted)">level of {t}</text>' for x, t in ((95, 'A'), (235, 'B')))
        return (f'<svg viewBox="0 0 330 222" role="img" aria-label="{title}: {label}" {SVG}>'
                '<defs><marker id="ga-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--accent)"/></marker>'
                '<marker id="ga-i" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M8 0V10" stroke="var(--accent2)" stroke-width="2.4"/></marker></defs>'
                f'<text x="165" y="22" text-anchor="middle" font-size="14" font-weight="600" fill="var(--ink)">{title}</text>{mk}{nodes}{bars}'
                f'<text x="165" y="212" text-anchor="middle" font-size="14" fill="var(--ink)">{label}</text></svg>')
    a = panel('gp', 'amplify (+)', 'more A, more B', 'ga-a')
    b = panel('gm', f'brake ({MINUS})', 'more A, less B', 'ga-i')
    ctl = ('<div class="ctl"><label for="ga-s">level of A</label>'
           '<input id="ga-s" type="range" min="0" max="1" step="0.05" value="0.5" aria-label="level of A"><output id="ga-o" for="ga-s"></output></div>')
    js = '''<script>
(function () {
  function bar(id, f) { var r = document.getElementById(id), h = 4 + 62 * f; r.setAttribute('height', h.toFixed(1)); r.setAttribute('y', (166 - h).toFixed(1)); }
  function draw() {
    var a = +document.getElementById('ga-s').value;
    document.getElementById('ga-o').textContent = Math.round(a * 100) + '%';
    bar('gp-A', a); bar('gm-A', a);
    bar('gp-B', a); bar('gm-B', 1 - a);
  }
  document.getElementById('ga-s').addEventListener('input', draw);
  draw();
})();
</script>'''
    return f'<div class="interactive"><div class="pair"><div>{a}</div><div>{b}</div></div>{ctl}</div>' + js


# ---------------------------------------------------------------- the data, step by step
def funnel(stages):
    """stages: list of (count, total, title, what, why). Rows are buttons; the panel explains the chosen step."""
    rows = ''.join(f'<button type="button" class="f-row" data-i="{i}" aria-pressed="{str(i == 0).lower()}">'
                   f'<span class="f-n">{c:,}</span><span class="f-bar"><span style="width:{max(2, 100 * c / tot):.1f}%"></span></span>'
                   f'<span class="f-t">{t}</span></button>' for i, (c, tot, t, _, _) in enumerate(stages))
    data = [{'what': w, 'why': y} for _, _, _, w, y in stages]
    js = '''<script>
(function () {
  var D = ''' + json.dumps(data) + ''';
  var root = document.getElementById('funnel'), panel = document.getElementById('f-panel');
  function show(i) {
    [].forEach.call(root.querySelectorAll('.f-row'), function (b) { b.setAttribute('aria-pressed', String(+b.dataset.i === i)); });
    panel.innerHTML = '<p><b>What.</b> ' + D[i].what + '</p><p><b>Why.</b> ' + D[i].why + '</p>';
  }
  root.addEventListener('click', function (e) { var b = e.target.closest('.f-row'); if (b) show(+b.dataset.i); });
  show(0);
})();
</script>'''
    first = stages[0]
    return (f'<div class="interactive" id="funnel">{rows}<div class="f-panel" id="f-panel" aria-live="polite">'
            f'<p><b>What.</b> {first[3]}</p><p><b>Why.</b> {first[4]}</p></div></div>' + js)


# ---------------------------------------------------------------- explore the census
def explorer(rows, picks):
    """rows: list of dicts (id, name, loops, pattern, element, does). Search by name; quick picks are chips."""
    chips = ''.join(f'<button type="button" class="pick" data-q="{q}">{lab}</button>' for lab, q in picks)
    js = '''<script>
(function () {
  var R = ''' + json.dumps(rows, separators=(',', ':')) + ''';
  var q = document.getElementById('ex-q'), list = document.getElementById('ex-list'), count = document.getElementById('ex-count');
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]; }); }
  function draw() {
    var term = q.value.trim().toLowerCase();
    var hit = R.filter(function (r) { return !term || r.name.toLowerCase().indexOf(term) >= 0 || r.id.indexOf(term) >= 0; });
    var cap = term ? 12 : 6;
    count.textContent = hit.length + ' of ' + R.length + ' models' + (hit.length > cap ? ', first ' + cap + ' shown' : '');
    list.innerHTML = hit.slice(0, cap).map(function (r) {
      var bits = r.element === null ? [r.loops] : [r.loops, r.pattern, 'element ' + r.element];
      bits.push(r.does);
      return '<li><span class="ex-name">' + esc(r.name) + '</span><span class="ex-meta">' + bits.map(function (b) { return '<span>' + esc(b) + '</span>'; }).join('') + '</span></li>';
    }).join('');
  }
  q.addEventListener('input', draw);
  document.getElementById('ex-picks').addEventListener('click', function (e) { var b = e.target.closest('.pick'); if (b) { q.value = b.dataset.q; draw(); } });
  draw();
})();
</script>'''
    return ('<div class="interactive explorer"><label class="ex-lab" for="ex-q">search 613 models by name</label>'
            '<input id="ex-q" type="search" placeholder="for example: clock, toggle, calcium" autocomplete="off">'
            f'<div class="ex-picks" id="ex-picks">{chips}</div><p class="ex-count" id="ex-count" aria-live="polite"></p>'
            '<ol class="ex-list" id="ex-list"></ol></div>' + js)


# ---------------------------------------------------------------- science is a loop
def science_loop(stages):
    """stages: list of (name, this_round, next_round). Drawn as a loop of nodes; click one to read it."""
    n = len(stages)
    cx, cy, r = 165, 150, 96
    pts = [(cx + r * math.sin(2 * math.pi * i / n), cy - r * math.cos(2 * math.pi * i / n)) for i in range(n)]
    arcs = ''
    for i in range(n):
        a0, a1 = 360 * i / n + 16, 360 * (i + 1) / n - 16
        x0, y0 = cx + r * math.sin(math.radians(a0)), cy - r * math.cos(math.radians(a0))
        x1, y1 = cx + r * math.sin(math.radians(a1)), cy - r * math.cos(math.radians(a1))
        arcs += f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" stroke="var(--accent)" stroke-width="2" marker-end="url(#sl-a)"/>'
    nodes = ''.join(f'<g class="sl-node" data-i="{i}" role="button" tabindex="0" aria-label="{name}">'
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="27" fill="var(--paper)" stroke="var(--accent)" stroke-width="1.6"/>'
                    f'<text x="{x:.1f}" y="{y + 4.5:.1f}" text-anchor="middle" font-size="12.5" fill="var(--ink)">{name}</text></g>'
                    for i, ((x, y), (name, _, _)) in enumerate(zip(pts, stages)))
    svg = (f'<svg id="sl" viewBox="0 0 330 300" role="img" aria-label="The research loop: {", ".join(s[0] for s in stages)}, and back again" {SVG}>'
           '<defs><marker id="sl-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--accent)"/></marker></defs>'
           f'{arcs}{nodes}<text x="{cx}" y="{cy + 5}" text-anchor="middle" font-size="14" font-weight="600" fill="var(--accent-text)">round two</text></svg>')
    data = [{'name': a, 'now': b, 'next': c} for a, b, c in stages]
    js = '''<script>
(function () {
  var D = ''' + json.dumps(data) + ''';
  var svg = document.getElementById('sl'), panel = document.getElementById('sl-panel');
  function show(i) {
    [].forEach.call(svg.querySelectorAll('.sl-node'), function (g) {
      var on = +g.dataset.i === i, c = g.querySelector('circle');
      c.setAttribute('fill', on ? 'var(--accent-soft)' : 'var(--paper)'); c.setAttribute('stroke-width', on ? '2.6' : '1.6');
      g.setAttribute('aria-pressed', String(on));
    });
    panel.innerHTML = '<p class="label">' + D[i].name + '</p><p><b>This round.</b> ' + D[i].now + '</p><p><b>Next round.</b> ' + D[i].next + '</p>';
  }
  svg.addEventListener('click', function (e) { var g = e.target.closest('.sl-node'); if (g) show(+g.dataset.i); });
  svg.addEventListener('keydown', function (e) { var g = e.target.closest('.sl-node'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); show(+g.dataset.i); } });
  show(0);
})();
</script>'''
    first = stages[0]
    return (f'<div class="interactive sl-wrap"><div class="solo">{svg}</div><div class="f-panel" id="sl-panel" aria-live="polite">'
            f'<p class="label">{first[0]}</p><p><b>This round.</b> {first[1]}</p><p><b>Next round.</b> {first[2]}</p></div></div>' + js)


# ---------------------------------------------------------------- hero: the loop table as a 3D spiral
# The spiral of Figure S6 (one turn per row, elements from 30 to 330 degrees) lifted into a cone: each turn
# drops by HERO['hs'], so the line that starts at element 0 winds into one loop per row. Orthographic view,
# turned by phi about the vertical axis and tilted by 'tilt' radians; depth sorts and shades.
HERO = {'th0': 30.0, 'th1': 330.0, 'r0': 0.30, 'b': 0.235, 'hs': 0.36, 'apex': -0.30, 'tilt': 0.5, 'phi': -18.0,
        'lab': 60, 'smax': 230}


def hero_world(elements):
    """elements: dicts with n, i (index in row), L (row length). Returns (r, theta, y) per element and the spiral."""
    H = HERO
    pts = []
    for e in elements:
        if e['n'] == 0:
            pts.append((0.0, 0.0, H['apex']))
            continue
        th = H['th0'] + (H['th1'] - H['th0']) * e['i'] / (e['L'] - 1)
        u = e['n'] - 1 + th / 360
        pts.append((H['r0'] + H['b'] * u, th, H['hs'] * u))
    line = [(0.0, 0.0, H['apex']), (0.0, 0.0, H['apex'] / 2)]
    t = H['th0']
    while t <= 2 * 360 + H['th1'] + 0.01:
        u = t / 360
        line.append((H['r0'] + H['b'] * u, t % 360, H['hs'] * u))
        t += 4
    return pts, line


def hero_layout(W):
    H = HERO
    e = H['tilt']
    cx = (W - H['lab'] - 8) / 2 if W < 560 else W / 2
    S = min((min(cx, W - cx - H['lab'] - 8) - 14) / 1.05, H['smax'])
    top = -H['apex'] * math.cos(e) * S + 26
    height = top + (H['hs'] * 2.92 * math.cos(e) + (H['r0'] + H['b'] * 2.92) * math.sin(e)) * S + 28
    return S, cx, top, height


def hero_proj(p, phi, S, cx, top):
    r, th, y = p
    e = HERO['tilt']
    a = math.radians(th + phi)
    X, Z = r * math.sin(a), -r * math.cos(a)
    return cx + X * S, top + (y * math.cos(e) + Z * math.sin(e)) * S, Z * math.cos(e) - y * math.sin(e), Z


def hero_frame(elements, W, phi):
    """SVG body for one view: spiral segments and element orbs, painted back to front, plus row labels."""
    pts, line = hero_world(elements)
    S, cx, top, height = hero_layout(W)
    rmax = HERO['r0'] + HERO['b'] * 2.92
    items = []
    proj = [hero_proj(p, phi, S, cx, top) for p in line]
    for (x0, y0, d0, z0), (x1, y1, d1, z1) in zip(proj, proj[1:]):
        f = ((z0 + z1) / 2 / rmax + 1) / 2
        items.append(((d0 + d1) / 2, f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="var(--accent)" '
                                     f'stroke-width="{(1.1 + 1.4 * f) * S / 200:.2f}" stroke-linecap="round" opacity="{0.22 + 0.73 * f:.2f}"/>'))
    for el, p in zip(elements, pts):
        x, y, d, z = hero_proj(p, phi, S, cx, top)
        f = (z / rmax + 1) / 2 if p[0] else 1.0
        k = 0.9 + 0.2 * f
        if el['status'] == 'found':
            rr = (2.4 + 1.15 * math.sqrt(min(el['count'], 100))) * S / 200 * k
            body = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" fill="url(#fx-orb)" filter="url(#fx-lift)" opacity="{0.62 + 0.38 * f:.2f}"/>'
        else:
            rr = max(2.6, 3.2 * S / 200) * k
            body = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.2" opacity="{0.5 + 0.5 * f:.2f}"/>'
        items.append((d + 0.001, body))
    items.sort(key=lambda t: t[0])
    labels = ''.join(f'<text x="{W - 4:.1f}" y="{top + (HERO["apex"] if n == 0 else HERO["hs"] * (n - 0.5)) * math.cos(HERO["tilt"]) * S + 4:.1f}" '
                     f'text-anchor="end" fill="var(--muted)">{lab}</text>'
                     for n, lab in ((0, 'no loop'), (1, '1 loop'), (2, '2 loops'), (3, '3 loops')))
    return ''.join(b for _, b in items) + labels, height


TRACE = {
    'keeps time': 'M1 8Q4 1 7 8T13 8T19 8T25 8T31 8',
    'holds two states': 'M1 8C8 8 10 2.5 31 2.5M1 8C8 8 10 13.5 31 13.5',
    'settles': 'M1 2C7 13 14 12.5 31 12.5',
    'rings, then settles': 'M1 8Q3.5 0 6 8T11 8Q13.5 3.5 16 8T21 8Q23 6.5 25 8L31 8',
    'settles anywhere': 'M1 3H31M1 8H31M1 13H31',
    'grows without limit': 'M1 14C14 14 24 10 31 1',
    'driven from outside': 'M1 13H7V3H13V13H19V3H25V13H31',
    'counts': 'M1 14L31 2',
    'fires and resets': 'M1 13Q6 12 8 3L9 13Q14 12 16 3L17 13Q22 12 24 3L25 13',
    'holds, then fades': 'M1 13H5V3H17C23 3 25 13 31 13',
    'adapts exactly': 'M1 12H8V3C13 3 17 12 31 12',
    'adds up, commits': 'M1 14L17 9L19 2H31',
}


def trace_svg(word, dashed=False):
    dash = ' stroke-dasharray="3 2.5"' if dashed else ''
    return (f'<svg width="32" height="16" viewBox="0 0 32 16" aria-hidden="true"><path d="{TRACE.get(word, "M1 8H31")}" fill="none" '
            f'stroke="var(--accent-text)" stroke-width="1.7" stroke-linecap="round"{dash}/></svg>')


def element_card_js():
    """One card renderer shared by the hero and the table: what an element does, drawn.
    window.ElCard.html(el) builds the card; window.ElCard.place(card, x, y, r, w, h) puts it beside a point."""
    return """<script>
window.ElCard = (function () {
  var TRACE = """ + json.dumps(TRACE) + """;
  function esc(x) { return String(x).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function trace(w, dashed) {
    return '<svg width="32" height="16" viewBox="0 0 32 16" aria-hidden="true"><path d="' + (TRACE[w] || 'M1 8H31') +
      '" fill="none" stroke="var(--accent-text)" stroke-width="1.7" stroke-linecap="round"' + (dashed ? ' stroke-dasharray="3 2.5"' : '') + '/></svg>';
  }
  // the circuit in the field's notation: X, Y, Z are genes or proteins; -> activates, -| represses;
  // a square marked with an integral sign keeps a running total. Each loop pairs the hub X with one partner.
  function edge(x1, y1, x2, y2, bend, kind) {
    var mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
    var cx = mx + nx * bend, cy = my + ny * bend;
    function toward(px, py, qx, qy, d) { var ux = qx - px, uy = qy - py, l = Math.hypot(ux, uy); return [px + ux / l * d, py + uy / l * d]; }
    var s = toward(x1, y1, cx, cy, 12.5), e = toward(x2, y2, cx, cy, 13.5), tx = e[0] - cx, ty = e[1] - cy, tl = Math.hypot(tx, ty);
    tx /= tl; ty /= tl;
    var head = kind === 'act'
      ? '<path d="M' + (e[0] + tx * 1.5).toFixed(1) + ' ' + (e[1] + ty * 1.5).toFixed(1) + 'L' + (e[0] - tx * 6 - ty * 3.6).toFixed(1) + ' ' + (e[1] - ty * 6 + tx * 3.6).toFixed(1) +
        'L' + (e[0] - tx * 6 + ty * 3.6).toFixed(1) + ' ' + (e[1] - ty * 6 - tx * 3.6).toFixed(1) + 'z" fill="var(--accent-text)"/>'
      : '<path d="M' + (e[0] - ty * 5.5).toFixed(1) + ' ' + (e[1] + tx * 5.5).toFixed(1) + 'L' + (e[0] + ty * 5.5).toFixed(1) + ' ' + (e[1] - tx * 5.5).toFixed(1) + '" stroke="var(--accent2-text)" stroke-width="2"/>';
    return '<path d="M' + s[0].toFixed(1) + ' ' + s[1].toFixed(1) + 'Q' + cx.toFixed(1) + ' ' + cy.toFixed(1) + ' ' + e[0].toFixed(1) + ' ' + e[1].toFixed(1) +
      '" fill="none" stroke="' + (kind === 'act' ? 'var(--accent-text)' : 'var(--accent2-text)') + '" stroke-width="1.4"/>' + head;
  }
  function node(x, y, lab, integ) {
    return integ
      ? '<rect x="' + (x - 11) + '" y="' + (y - 11) + '" width="22" height="22" rx="4" fill="var(--accent-tint)" stroke="var(--ink)" stroke-width="1.3"/>' +
        '<text x="' + x + '" y="' + (y + 5) + '" text-anchor="middle" font-size="16" font-style="italic" style="font-family: var(--serif)" fill="var(--ink)">∫</text>'
      : '<circle cx="' + x + '" cy="' + y + '" r="11" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.3"/>' +
        '<text x="' + x + '" y="' + (y + 4.5) + '" text-anchor="middle" font-size="12" font-weight="600" fill="var(--ink)">' + lab + '</text>';
  }
  function glyph(n, k, j) {
    var out = '', H, i;
    if (!n) {
      H = 30;
      out = edge(18, 15, 70, 15, 0, 'act') + edge(70, 15, 122, 15, 0, 'act') + node(18, 15, 'X') + node(70, 15, 'Y') + node(122, 15, 'Z');
      return '<svg width="140" height="' + H + '" viewBox="0 0 140 ' + H + '" aria-hidden="true">' + out + '</svg>';
    }
    H = n === 1 ? 44 : n === 2 ? 80 : 112;
    var ys = n === 1 ? [H / 2] : n === 2 ? [H / 2 - 20, H / 2 + 20] : [H / 2 - 38, H / 2, H / 2 + 38], hx = 18, sx = 112, nodes = node(hx, H / 2, 'X');
    for (i = 0; i < n; i++) {
      var brake = i >= n - k, integ = i >= n - j;
      out += edge(hx, H / 2, sx, ys[i], 9, 'act') + edge(sx, ys[i], hx, H / 2, 9, brake ? 'rep' : 'act');
      nodes += node(sx, ys[i], 'YZW'[i], integ);
    }
    return '<svg width="140" height="' + H + '" viewBox="0 0 140 ' + H + '" aria-hidden="true">' + out + nodes + '</svg>';
  }
  var STATUS = {found: function (e) { return e.count + (e.count === 1 ? ' curated model' : ' curated models'); },
                known: function () { return 'known from experiments'; }, candidate: function () { return 'candidates to check'; },
                blank: function () { return 'not found yet'; }};
  function html(e) {
    var h = '<div class="ec-top"><span class="ec-k">element ' + e.num + '</span><span class="ec-s ec-' + e.status + '">' + STATUS[e.status](e) + '</span></div>' +
      '<p class="ec-t"><span class="ec-sym">' + e.symHtml + '</span>' + esc(e.name) + '</p><div class="ec-glyph" role="img" aria-label="' + esc(e.sig) + '">' + glyph(e.n, e.k, e.j) +
      '<p class="ec-key"><span class="sp">\u2192 amplifies</span><span class="sn">\u22a3 brakes</span>' + (e.j ? '<span>\u222b running total</span>' : '') + '</p></div>' +
      '<p class="ec-d">' + esc(e.does) + '</p><ul class="ec-tr">' + e.traces.map(function (w, i) {
        var pred = e.predicted && i > 0;
        return '<li>' + trace(w, pred) + '<span>' + esc(w) + (pred ? ' <i>predicted</i>' : '') + '</span></li>';
      }).join('') + '</ul>';
    if (e.observed.length) h += '<p class="ec-h">what its curated models do</p><ul class="ec-tr ec-obs">' + e.observed.map(function (d) {
      return '<li>' + trace(d[0]) + '<span>' + esc(d[0]) + '</span><b>' + d[1] + '</b></li>'; }).join('') + '</ul>';
    var ex = e.essay.concat(e.examples.filter(function (x) { return e.essay.indexOf(x) < 0; })).slice(0, 4);
    if (ex.length) h += '<p class="ec-h">examples</p><p class="ec-x">' + ex.map(esc).join(', ') + '</p>';
    if (e.status !== 'found' && e.look) h += '<p class="ec-h">where to look</p><p class="ec-l">' + esc(e.look) + '</p>';
    if (e.candidates.length) h += '<p class="ec-h">candidates in this census, loose reading</p><p class="ec-l">' + e.candidates.map(esc).join('; ') + '</p>';
    return h;
  }
  // beside the point, never over it: right, left, below, above, whichever fits first
  function place(card, x, y, r, w, h) {
    var cw = card.offsetWidth, ch = card.offsetHeight;
    var cx = function (v) { return Math.min(Math.max(0, v), Math.max(0, w - cw)); }, cy = function (v) { return Math.min(Math.max(0, v), Math.max(0, h - ch)); };
    var spots = [[x + r, cy(y - ch / 2)], [x - r - cw, cy(y - ch / 2)], [cx(x - cw / 2), y + r], [cx(x - cw / 2), y - r - ch]];
    var fit = spots.filter(function (s) { return s[0] >= 0 && s[0] + cw <= w && s[1] >= 0 && s[1] + ch <= h; })[0] || [cx(x - cw / 2), y + r];
    card.style.left = fit[0] + 'px'; card.style.top = fit[1] + 'px';
  }
  return {html: html, place: place, trace: trace};
})();
</script>"""


def periodic_table(elements, found_top, found_rest):
    """The loop table as one figure: a k-by-j block per loop count (k across: loops that brake; j down: loops
    through a running total), each element a tile showing what it does; point at one for its card."""
    by = {(e['n'], e['k'], e['j']): e for e in elements}
    blocks = []
    for n in range(4):
        tiles = []
        for j in range(n + 1):
            for k in range(n + 1):
                e = by[(n, k, j)]
                bottom = str(e['count']) if e['status'] == 'found' else '?'
                tiles.append(f'<button type="button" class="pt-el pt-{e["status"]}" data-i="{elements.index(e)}" '
                             f'aria-label="element {e["num"]}, {e["name"]}, {e["statusText"]}">'
                             f'<span class="pt-n">{e["num"]}</span><span class="pt-sig">{e["sigShort"]}</span><span class="pt-sym">{e["symHtml"]}</span>'
                             f'<span class="pt-tr" aria-hidden="true">{trace_svg(e["traces"][-1] if e["predicted"] and e["status"] != "found" else e["traces"][0], e["predicted"] and e["status"] != "found")}</span>'
                             f'<span class="pt-c">{bottom}</span></button>')
        head = 'no loop' if n == 0 else f'{n} loop{"s" if n > 1 else ""}'
        blocks.append(f'<div class="pt-block"><p class="pt-h"><b>{head}</b> <span>{n + 1} &#215; {n + 1} = {(n + 1) ** 2}</span></p>'
                      f'<div class="pt-grid" style="grid-template-columns: repeat({n + 1}, var(--tile))">{"".join(tiles)}</div></div>')
    s8 = by[(2, 1, 0)]
    keybox = ('<div class="pt-keybox"><p class="pt-h"><b>how to read a tile</b></p><div class="pt-anat">'
              f'<span class="pt-el pt-found pt-big" aria-hidden="true"><span class="pt-n">{s8["num"]}</span><span class="pt-sig">{s8["sigShort"]}</span>'
              f'<span class="pt-sym pt-sample">{s8["symHtml"]}</span><span class="pt-tr">{trace_svg(s8["traces"][0])}</span><span class="pt-c">{s8["count"]}</span></span>'
              '<span class="pt-a" style="top: 0">element number</span>'
              '<span class="pt-a" style="top: 18px"><span class="sp">+</span> amplifies, <span class="sn">&#8722;</span> brakes, &#8747; running total</span>'
              f'<span class="pt-a" style="top: 42px">symbol: {s8["sym"]}, {s8["name"]}</span>'
              '<span class="pt-a" style="top: 74px">what it does (dashed: predicted)</span>'
              '<span class="pt-a" style="top: 108px">curated models found (? if none yet)</span></div></div>')
    blocks.insert(3, keybox)
    html_ = ''.join(blocks)
    data = json.dumps(elements, separators=(',', ':'))
    js = """<script>
(function () {
  var E = """ + data + """, box = document.getElementById('ptable'), card = document.getElementById('pt-card'), pinned = -1;
  function show(b) {
    if (!b) { card.classList.remove('on'); return; }
    card.innerHTML = ElCard.html(E[+b.dataset.i]);
    card.classList.add('on');
    var br = box.getBoundingClientRect(), r = b.getBoundingClientRect();
    ElCard.place(card, r.left - br.left + r.width / 2, r.top - br.top + r.height / 2, r.width / 2 + 8, box.clientWidth, Math.max(box.clientHeight, card.offsetHeight));
  }
  box.addEventListener('pointerover', function (ev) { var b = ev.target.closest('.pt-el'); if (b && pinned < 0) show(b); });
  box.addEventListener('pointerleave', function () { if (pinned < 0) show(null); });
  box.addEventListener('focusin', function (ev) { var b = ev.target.closest('.pt-el'); if (b) show(b); });
  box.addEventListener('click', function (ev) {
    var b = ev.target.closest('.pt-el');
    if (!b) { pinned = -1; show(null); return; }
    pinned = pinned === +b.dataset.i ? -1 : +b.dataset.i; show(pinned < 0 ? null : b);
    [].forEach.call(box.querySelectorAll('.pt-el'), function (x) { x.setAttribute('aria-pressed', String(+x.dataset.i === pinned)); });
  });
  box.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { pinned = -1; show(null); } });
})();
</script>"""
    tile = lambda cls: f'<span class="pt-key pt-{cls}" aria-hidden="true"></span>'
    key = (f'<div class="pt-legend"><span>{tile("found")}found in curated models, with how many</span>'
           f'<span>{tile("known")}known from experiments, not in this census</span>'
           f'<span>{tile("candidate")}candidates from a looser running-total reading</span>'
           f'<span>{tile("blank")}not found yet: a prediction</span></div>')
    axes = ('<p class="pt-axes"><span>across: loops that brake (k)</span><span>down: loops through a running total (j)</span></p>')
    gaps = (f'<p class="pt-gap"><span><b>{found_top[0]} of {found_top[1]}</b> found with no running total (top rows)</span>'
            f'<span><b>{found_rest[0]} of {found_rest[1]}</b> found with one or more (rows below)</span></p>')
    return (f'<div class="interactive ptable" id="ptable">{axes}<div class="pt-blocks">{html_}</div>{gaps}{key}'
            f'<div class="pt-card ecard" id="pt-card" role="status" aria-live="polite"></div></div>' + js)


def hero(elements):
    """elements: dicts as for periodic_table, plus i (index in row) and L (row length). Returns the hero figure."""
    W = 720
    body, height = hero_frame(elements, W, HERO['phi'])
    pts, line = hero_world(elements)
    data = {'el': elements, 'pts': pts, 'line': line, 'H': HERO}
    svg = (f'<svg id="hero-svg" viewBox="0 0 {W} {height:.0f}" role="img" tabindex="0" '
           f'aria-label="The loop table drawn as a spiral cone, one turn per row of 4, 9 and 16 elements, with the elements that curated models occupy filled and sized by count" '
           f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="12"><g id="hero-g">{body}</g></svg>')
    js = """<script>
(function () {
  var D = """ + json.dumps(data, separators=(',', ':')) + """;
  var H = D.H, svg = document.getElementById('hero-svg'), g = document.getElementById('hero-g'), card = document.getElementById('hero-card');
  var W = 0, S, cx, top, height, phi = H.phi, hover = -1, pinned = -1, drag = null, vel = 0, speed = 0, seen = true, last = null, lastMove = 0;
  var still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var e = H.tilt, ce = Math.cos(e), se = Math.sin(e), rmax = H.r0 + H.b * 2.92, P = [];
  function layout() {
    cx = W < 560 ? (W - H.lab - 8) / 2 : W / 2; S = Math.min((Math.min(cx, W - cx - H.lab - 8) - 14) / 1.05, H.smax); top = -H.apex * ce * S + 26;
    height = top + (H.hs * 2.92 * ce + rmax * se) * S + 28;
  }
  function proj(p) {
    var a = (p[1] + phi) * Math.PI / 180, X = p[0] * Math.sin(a), Z = -p[0] * Math.cos(a);
    return [cx + X * S, top + (p[2] * ce + Z * se) * S, Z * ce - p[2] * se, Z];
  }
  function draw() {
    var items = [], i, q = D.line.map(proj), on = pinned >= 0 ? pinned : hover;
    for (i = 0; i + 1 < q.length; i++) {
      var f = ((q[i][3] + q[i + 1][3]) / 2 / rmax + 1) / 2;
      items.push([(q[i][2] + q[i + 1][2]) / 2, '<line x1="' + q[i][0].toFixed(1) + '" y1="' + q[i][1].toFixed(1) + '" x2="' + q[i + 1][0].toFixed(1) + '" y2="' + q[i + 1][1].toFixed(1) +
        '" stroke="var(--accent)" stroke-width="' + ((1.1 + 1.4 * f) * S / 200).toFixed(2) + '" stroke-linecap="round" opacity="' + (0.22 + 0.73 * f).toFixed(2) + '"/>']);
    }
    P = [];
    D.pts.forEach(function (p, j) {
      var c = proj(p), f = p[0] ? (c[3] / rmax + 1) / 2 : 1, k = 0.9 + 0.2 * f, el = D.el[j], n = el.status === 'found' ? el.count : 0, rr, body;
      if (n) {
        rr = (2.4 + 1.15 * Math.sqrt(Math.min(n, 100))) * S / 200 * k;
        body = '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + rr.toFixed(1) + '" fill="url(#fx-orb)" filter="url(#fx-lift)" opacity="' + (0.62 + 0.38 * f).toFixed(2) + '"/>';
      } else {
        rr = Math.max(2.6, 3.2 * S / 200) * k;
        body = '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + rr.toFixed(1) + '" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.2" opacity="' + (0.5 + 0.5 * f).toFixed(2) + '"/>';
      }
      if (j === on) body += '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + (rr + 4).toFixed(1) + '" fill="none" stroke="var(--ink)" stroke-width="1.6"/>';
      P.push([c[0], c[1], rr]);
      items.push([c[2] + 0.001, body]);
    });
    items.sort(function (a, b) { return a[0] - b[0]; });
    var labs = [[0, 'no loop'], [1, '1 loop'], [2, '2 loops'], [3, '3 loops']].map(function (r) {
      var y = top + (r[0] ? H.hs * (r[0] - 0.5) : H.apex) * ce * S + 4;
      return '<text x="' + (W - 4).toFixed(1) + '" y="' + y.toFixed(1) + '" text-anchor="end" fill="var(--muted)">' + r[1] + '</text>';
    }).join('');
    g.innerHTML = items.map(function (t) { return t[1]; }).join('') + labs;
    if (on >= 0) placeCard(on);
  }
  function placeCard(j) { var k = svg.getBoundingClientRect().width / W; ElCard.place(card, P[j][0] * k, P[j][1] * k, P[j][2] * k + 13, svg.clientWidth, svg.clientHeight); }
  function say(j) {
    if (j < 0 || !P[j]) { card.classList.remove('on'); return; }
    card.innerHTML = ElCard.html(D.el[j]); card.classList.add('on'); placeCard(j);
  }
  function size() {
    var w = Math.round(svg.parentNode.getBoundingClientRect().width);
    if (!w || w === W) return;
    W = w; layout(); svg.setAttribute('viewBox', '0 0 ' + W + ' ' + Math.round(height)); svg.style.height = Math.round(height) + 'px'; draw();
  }
  function pick(ev) {
    var b = svg.getBoundingClientRect(), x = (ev.clientX - b.left) * W / b.width, y = (ev.clientY - b.top) * W / b.width, best = -1, bd = 1e9;
    P.forEach(function (p, j) { var d = Math.hypot(p[0] - x, p[1] - y); if (d < Math.max(16, p[2] + 7) && d < bd) { bd = d; best = j; } });
    return best;
  }
  // drag turns the cone and lets it coast; a tap on an element pins its card; hovering shows it
  var downX = 0, moved = false;
  svg.addEventListener('pointerdown', function (ev) { drag = ev.clientX; downX = ev.clientX; moved = false; vel = 0; lastMove = ev.timeStamp; svg.setPointerCapture(ev.pointerId); });
  svg.addEventListener('pointermove', function (ev) {
    if (drag !== null) {
      var dx = ev.clientX - drag, dt = Math.max(1, ev.timeStamp - lastMove);
      if (Math.abs(ev.clientX - downX) > 4) moved = true;
      phi += dx * 0.5; vel = dx * 0.5 / dt; drag = ev.clientX; lastMove = ev.timeStamp; draw(); return;
    }
    if (pinned >= 0) return;
    var j = pick(ev); if (j !== hover) { hover = j; draw(); say(j); }
  });
  svg.addEventListener('pointerup', function (ev) {
    drag = null;
    if (!moved) { var j = pick(ev); pinned = j === pinned ? -1 : j; hover = -1; draw(); say(pinned); vel = 0; }
  });
  svg.addEventListener('pointerleave', function () { if (drag === null && pinned < 0) { hover = -1; draw(); say(-1); } });
  svg.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') { ev.preventDefault(); phi += ev.key === 'ArrowLeft' ? -12 : 12; draw(); }
    else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); pinned = ((pinned < 0 ? (ev.key === 'ArrowDown' ? -1 : 0) : pinned) + (ev.key === 'ArrowDown' ? 1 : D.el.length - 1)) % D.el.length; draw(); say(pinned); }
    else if (ev.key === 'Escape') { pinned = -1; hover = -1; draw(); say(-1); }
  });
  svg.addEventListener('blur', function () { pinned = -1; hover = -1; draw(); say(-1); });
  if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { seen = es[0].isIntersecting; }).observe(svg);
  function tick(t) {
    var dt = last === null ? 0 : Math.min(50, t - last); last = t;
    if (seen && drag === null && !document.hidden) {
      var idle = hover < 0 && pinned < 0 && !still;
      speed += ((idle ? 0.006 : 0) - speed) * Math.min(1, dt / 400);
      vel *= Math.pow(0.995, dt);
      if (Math.abs(vel) > 0.0005 || Math.abs(speed) > 0.0002) { phi += (vel + speed) * dt; draw(); }
    }
    requestAnimationFrame(tick);
  }
  if ('ResizeObserver' in window) new ResizeObserver(size).observe(svg.parentNode); else window.addEventListener('resize', size);
  size();
  requestAnimationFrame(tick);
})();
</script>"""
    orb = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7" fill="url(#fx-orb)"/></svg>'
    ring = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="3.6" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.2"/></svg>'
    return (f'<figure class="hero" id="hero"><div class="hero-stage">{svg}<div class="hero-card ecard" id="hero-card" role="status" aria-live="polite"></div></div>'
            f'<figcaption class="hero-key"><b>The table this post tests, one turn per row of 4, 9 and 16 kinds of circuit</b>'
            f'<span class="key">{orb}found in real circuits, sized by how many</span>'
            f'<span class="key">{ring}not found yet</span><span class="key">drag to turn, tap an element to read it</span></figcaption></figure>' + js)
