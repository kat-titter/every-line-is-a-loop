"""The punchline figure for every-line-is-a-loop.html: both periodic tables drawn as the grids everyone knows, then
wound one turn per row into the loops they are. Chemistry's 118 elements sit in the long form (s, f, d and p blocks
as columns); the loop table's 30 elements sit one row per loop count in orbital order. A slider winds the rows: every
mark moves on a straight line from its grid position to its place on the spiral, the row guides fade out and the
spiral with its family rays fades in. The figure plays itself once when it scrolls into view (still under reduced
motion, where it starts wound), and the slider lets the reader unwind it.

Both layouts are computed here, so the first frame is complete without JavaScript (drawn wound, the reveal).
"""
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import table_figures as TF  # noqa: E402

TH0, TH1 = TF.TH0, TF.TH1
W = 330
SHAPE_SIZE = {'chem': 2.9, 'bio': 5.2}


def pt(cx, cy, r, th):
    return TF._pt(cx, cy, r, th)


def chem_layout():
    """Marks for chemistry: grid position (long form, 32 columns), spiral position, block index."""
    periods = [2, 8, 8, 18, 18, 32, 32]
    cx, cy, r0, b = 170, 190, 22, 15
    gx0, gdx, gy0, gdy = 20, 9.35, 46, 19
    marks, guides = [], []
    for p, L in enumerate(periods):
        if L == 2:
            cols, blocks = [0, 31], ['s', 's']
        elif L == 8:
            cols, blocks = [0, 1] + list(range(26, 32)), ['s', 's'] + ['p'] * 6
        elif L == 18:
            cols, blocks = [0, 1] + list(range(16, 26)) + list(range(26, 32)), ['s', 's'] + ['d'] * 10 + ['p'] * 6
        else:
            cols, blocks = [0, 1] + list(range(2, 16)) + list(range(16, 26)) + list(range(26, 32)), ['s', 's'] + ['f'] * 14 + ['d'] * 10 + ['p'] * 6
        for i, (c, blk) in enumerate(zip(cols, blocks)):
            th = TH0 + (TH1 - TH0) * i / (L - 1)
            sx, sy = pt(cx, cy, r0 + b * (p + th / 360), th)
            marks.append({'g': [round(gx0 + c * gdx, 1), round(gy0 + p * gdy, 1)], 's': [round(sx, 1), round(sy, 1)], 'l': 'spdf'.index(blk)})
        guides.append(round(gy0 + p * gdy, 1))
    spiral = TF._spiral(cx, cy, r0, b, 0, 6) + TF._rays(cx, cy, r0, b, 6, 8)
    labels_s = ''
    for th, lab, anchor, dx in ((TH0, 'group 1', 'start', 4), (TH1, 'noble gases', 'end', -4)):
        x, y = pt(cx, cy, r0 + b * (6 + th / 360) + 24, th)
        labels_s += f'<text x="{x + dx:.1f}" y="{y - 8:.1f}" text-anchor="{anchor}" font-size="12" fill="var(--muted)">{lab}</text>'
    labels_g = ''.join(f'<text x="{gx0 - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="var(--muted)" style="font-family: var(--code)">{p + 1}</text>' for p, y in enumerate(guides))
    labels_g += f'<text x="{gx0}" y="{gy0 + 7 * gdy + 4}" text-anchor="start" font-size="12" fill="var(--muted)" style="font-family: var(--code)">period, down</text>'
    labels_g += f'<text x="{gx0}" y="{gy0 - 14}" text-anchor="start" font-size="12" fill="var(--muted)" style="font-family: var(--code)">group 1</text>'
    labels_g += f'<text x="{gx0 + 31 * gdx}" y="{gy0 - 14}" text-anchor="end" font-size="12" fill="var(--muted)" style="font-family: var(--code)">18</text>'
    grid_guides = ''.join(f'<line x1="{gx0 - 4}" y1="{y:.1f}" x2="{gx0 + 31 * gdx + 4:.1f}" y2="{y:.1f}" stroke="var(--rule)" stroke-width="1"/>' for y in guides)
    return marks, grid_guides, labels_g, spiral, labels_s


def bio_layout():
    """Marks for the loop table: one row per loop count in orbital order; element zero at the centre of the spiral."""
    cx, cy, r0, b = 170, 196, 40, 32
    gy0, gdy, gdx = 60, 34, 14
    marks, guides = [], []
    zero = {'g': [165.0, 40.0], 's': [float(cx), float(cy)], 'l': 0, 'n': 0}
    marks.append(zero)
    for nu in (1, 2, 3):
        row = [e for e in TF.ELEMENTS if e[0] == nu]
        L = len(row)
        for i, e in enumerate(row):
            th = TH0 + (TH1 - TH0) * i / (L - 1)
            sx, sy = pt(cx, cy, r0 + b * (nu - 1 + th / 360), th)
            gx = 165 + (i - (L - 1) / 2) * gdx
            marks.append({'g': [round(gx, 1), round(gy0 + (nu - 1) * gdy, 1)], 's': [round(sx, 1), round(sy, 1)], 'l': max(e[1], e[2]), 'n': TF.NUMBER[e]})
        guides.append((nu, L, round(gy0 + (nu - 1) * gdy, 1)))
    spiral = TF._spiral(cx, cy, r0, b, 0, 2) + TF._rays(cx, cy, r0, b, 2, 22)
    labels_s = ''
    for th, lab, anchor, dx in ((TH0, 'memories', 'start', 4), (TH1, 'clocks', 'end', -4)):
        x, y = pt(cx, cy, r0 + b * (2 + th / 360) + 36, th)
        labels_s += f'<text x="{x + dx:.1f}" y="{y - 8:.1f}" text-anchor="{anchor}" font-size="12" fill="var(--muted)">{lab}</text>'
    labels_g = ''.join(f'<text x="{165 - (L - 1) / 2 * gdx - 12:.1f}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="var(--muted)" style="font-family: var(--code)">&nu; = {nu}</text>' for nu, L, y in guides)
    labels_g += '<text x="150" y="44" text-anchor="end" font-size="12" fill="var(--muted)" style="font-family: var(--code)">&nu; = 0</text>'
    grid_guides = ''.join(f'<line x1="{165 - (L - 1) / 2 * gdx - 6:.1f}" y1="{y:.1f}" x2="{165 + (L - 1) / 2 * gdx + 6:.1f}" y2="{y:.1f}" stroke="var(--rule)" stroke-width="1"/>' for nu, L, y in guides)
    return marks, grid_guides, labels_g, spiral, labels_s


def panel(key, title, aria, layout, size):
    marks, grid_guides, labels_g, spiral, labels_s = layout
    s = f'<text x="165" y="22" text-anchor="middle" font-weight="600" font-size="14" fill="var(--ink)">{title}</text>'
    s += f'<g class="mo-grid" opacity="0" display="none">{grid_guides}{labels_g}</g>'
    s += f'<g class="mo-loop" opacity="1">{spiral}{labels_s}</g>'
    s += '<g class="mo-marks">' + ''.join(
        f'<g class="mk" transform="translate({m["s"][0]} {m["s"][1]})">{TF._shape(0, 0, m["l"], size, "var(--ink)")}</g>' for m in marks) + '</g>'
    return (f'<svg class="morph" data-key="{key}" viewBox="0 0 {W} {W}" role="img" aria-label="{aria}" font-size="13">{s}</svg>')


def fig_morph():
    chem, bio = chem_layout(), bio_layout()
    data = {'chem': [[m['g'], m['s']] for m in chem[0]], 'bio': [[m['g'], m['s']] for m in bio[0]]}
    legend = ''.join(f'<span><svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">{TF._shape(0, 0, l, 5.2, "var(--ink)")}</svg> {TF.BLOCKS[l]}</span>' for l in range(4))
    html = ('<div class="pair">'
            f'<div>{panel("chem", "Chemistry", "The chemical periodic table: 118 elements as the long-form grid, wound one turn per period into a spiral where group 1 and the noble gases line up on two rays", chem, SHAPE_SIZE["chem"])}</div>'
            f'<div>{panel("bio", "The loop table", "The loop table: 30 elements, one row per loop count, wound one turn per row into a spiral where memories and clocks line up on two rays", bio, SHAPE_SIZE["bio"])}</div>'
            '</div>'
            f'<p class="keyrow pt-legend">{legend}<span class="mo-note">block, by the subshell it fills: s, p, d, f</span></p>'
            '<div class="ctl"><label for="mo-t">wind the rows</label>'
            '<input id="mo-t" type="range" min="0" max="100" value="100" aria-label="Wind the rows of both tables into loops" style="--p: 100%">'
            '<output for="mo-t" id="mo-tv">loop</output></div>')
    js = '<script>\n(function () {\n  var M = ' + json.dumps(data) + ''';
  var RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var el = document.getElementById('mo-t'), out = document.getElementById('mo-tv'); if (!el) return;
  var panels = Array.prototype.map.call(document.querySelectorAll('svg.morph'), function (svg) {
    return { key: svg.getAttribute('data-key'), marks: svg.querySelectorAll('.mk'), grid: svg.querySelector('.mo-grid'), loop: svg.querySelector('.mo-loop') };
  });
  function ease(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
  function draw(t) {
    panels.forEach(function (p) {
      var L = M[p.key];
      for (var i = 0; i < L.length; i++) {
        var g = L[i][0], s = L[i][1], x = g[0] + (s[0] - g[0]) * t, y = g[1] + (s[1] - g[1]) * t;
        p.marks[i].setAttribute('transform', 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')');
      }
      p.grid.setAttribute('opacity', (1 - t).toFixed(2)); p.grid.setAttribute('display', t >= 0.995 ? 'none' : 'inline');
      p.loop.setAttribute('opacity', t.toFixed(2)); p.loop.setAttribute('display', t <= 0.005 ? 'none' : 'inline');
    });
    out.textContent = t <= 0.01 ? 'grid' : t >= 0.99 ? 'loop' : Math.round(t * 100) + '%';
    el.style.setProperty('--p', (t * 100).toFixed(1) + '%');
  }
  el.addEventListener('input', function () { draw(el.value / 100); });
  if (RM) { el.value = 100; draw(1); return; }
  // the reveal plays once, when the figure comes into view: the grid everyone knows winds into the loop it is
  el.value = 0; draw(0);
  var played = false, box = el.closest('figure');
  function play() {
    if (played) return; played = true;
    var t0 = null;
    function step(now) {
      if (t0 === null) t0 = now;
      var u = Math.min(1, (now - t0) / 2400);
      el.value = Math.round(ease(u) * 100); draw(ease(u));
      if (u < 1) requestAnimationFrame(step);
    }
    setTimeout(function () { requestAnimationFrame(step); }, 500);
  }
  if ('IntersectionObserver' in window && box) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { play(); io.disconnect(); } }); }, { threshold: 0.5 });
    io.observe(box);
  } else play();
})();
</script>'''
    return html + js


if __name__ == '__main__':
    print(len(fig_morph()))
