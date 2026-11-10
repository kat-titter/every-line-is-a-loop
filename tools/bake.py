"""Write Figure 1's first frame (the open line) into every-line-is-a-loop.html, between the bake:net and bake:plot
markers, so the figure reads without JavaScript. Run after any change to the figure's script or styles:

    .venv/bin/python tools/bake.py [--page PATH]

The page draws the frame itself; this copies what the browser drew. The model behind it is checked by
check_close in analysis/circuit_figures.py."""
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / 'every-line-is-a-loop.html'
if '--page' in sys.argv:
    PAGE = pathlib.Path(sys.argv[sys.argv.index('--page') + 1]).resolve()

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    pg = b.new_page(viewport={'width': 1024, 'height': 800}, reduced_motion='reduce')
    pg.goto(PAGE.as_uri())
    frames = {k: pg.eval_on_selector(f'#cl-{k}', 'e => e.innerHTML') for k in ('net', 'plot')}
    b.close()
src = PAGE.read_text(encoding='utf-8')
for k, inner in frames.items():
    inner = re.sub(r'<!--.*?-->', '', inner, flags=re.S)
    src, n = re.subn(rf'<!-- bake:{k} -->.*?<!-- /bake:{k} -->', lambda m: f'<!-- bake:{k} -->{inner}<!-- /bake:{k} -->', src, flags=re.S)
    assert n == 1, k
PAGE.write_text(src, encoding='utf-8')
print('baked', {k: len(v) for k, v in frames.items()}, 'into', PAGE.name)
