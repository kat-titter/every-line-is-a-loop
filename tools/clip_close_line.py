"""Frame-by-frame capture of Figure 1 (close the line) under a paused clock: line, wind to loop, flip one arrow,
flip back, unwind. Ends where it began, so the clip loops."""
import pathlib, sys
from playwright.sync_api import sync_playwright

repo, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for f in out.glob("*.png"):
    f.unlink()
STEPS = [33, 33, 34]
ease = lambda t: t * t * (3 - 2 * t)
n = 0

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1024, "height": 1100}, device_scale_factor=2, color_scheme="light")
    pg.clock.install(time=0)
    pg.goto((repo / "every-line-is-a-loop.html").as_uri())
    pg.clock.pause_at(8000)
    pg.add_style_tag(content="""
      #fig-close, #fig-close * { animation: none !important; transition: none !important; }
      #fig-close { padding: 26px !important; margin: 0 !important; background: var(--paper); position: relative; }
      #fig-close figcaption { display: none !important; }""")
    pg.evaluate("""() => {
      const fig = document.querySelector('#fig-close'), dot = document.createElement('div');
      dot.style.cssText = 'position:absolute;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;border:2px solid var(--ink);background:rgba(28,34,38,.14);opacity:0;pointer-events:none;z-index:9';
      fig.appendChild(dot);
      const rel = r => { const f = fig.getBoundingClientRect(); return [r.left - f.left, r.top - f.top]; };
      window.__dot = (xy, o) => { if (xy) { dot.style.left = xy[0] + 'px'; dot.style.top = xy[1] + 'px'; } dot.style.opacity = o; };
      window.__thumb = () => { const w = document.querySelector('#cl-wind'), r = w.getBoundingClientRect(), o = rel(r), tw = 26;
        return [o[0] + tw / 2 + (r.width - tw) * (w.value / 100), o[1] + r.height / 2]; };
      window.__edge = i => { const r = fig.querySelectorAll('g[role=button]')[i].getBoundingClientRect(), o = rel(r); return [o[0] + r.width / 2, o[1] + r.height / 2]; };
      window.__wind = (v, done) => { const w = document.querySelector('#cl-wind'); w.value = v; w.dispatchEvent(new Event('input', {bubbles: true}));
        if (done) w.dispatchEvent(new Event('change', {bubbles: true})); };
      window.__flip = i => fig.querySelectorAll('g[role=button]')[i].dispatchEvent(new MouseEvent('click', {bubbles: true}));
      window.scrollTo(0, fig.getBoundingClientRect().top + scrollY - 20);
    }""")
    r = pg.evaluate("() => { const r = document.querySelector('#fig-close').getBoundingClientRect(); return {x: r.left, y: r.top, width: r.width, height: r.height}; }")

    def snap(k=1):
        global n
        for _ in range(k):
            pg.clock.run_for(STEPS[n % 3])
            pg.screenshot(path=str(out / f"f{n:04d}.png"), clip=r)
            n += 1

    def say():
        return pg.evaluate("() => document.querySelector('#fig-close [aria-live]').textContent")

    log = []
    snap(24); log.append((n, say()))                     # a line
    for i in range(1, 37):                               # wind the line into a loop
        pg.evaluate("([v, d]) => { __wind(v, d); __dot(__thumb(), .9); }", [round(100 * ease(i / 36)), i == 36]); snap()
    snap(6); pg.evaluate("() => __dot(null, 0)"); snap(48); log.append((n, say()))   # it remembers
    pg.evaluate("() => __dot(__edge(2), .9)"); snap(4); pg.evaluate("() => __flip(2)"); snap(4)
    pg.evaluate("() => __dot(null, 0)"); snap(66); log.append((n, say()))            # one switch-off: it keeps time
    pg.evaluate("() => __dot(__edge(2), .9)"); snap(4); pg.evaluate("() => __flip(2)"); snap(4)
    pg.evaluate("() => __dot(null, 0)"); snap(22); log.append((n, say()))            # back to remembering
    for i in range(1, 31):                               # unwind
        pg.evaluate("([v, d]) => { __wind(v, d); __dot(__thumb(), .9); }", [round(100 * (1 - ease(i / 30))), i == 30]); snap()
    snap(4); pg.evaluate("() => __dot(null, 0)"); snap(12); log.append((n, say()))
    b.close()

print("frames", n, "| clip box", {k: round(v) for k, v in r.items()})
for at, words in log:
    print(f"  frame {at}: {words}")
