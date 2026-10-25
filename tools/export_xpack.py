"""Re-export x-pack figure stills from the page at 2x.

Usage: .venv/bin/python tools/export_xpack.py fig2 [--page PATH] [--out DIR]

fig2: the Figure 2 SVG alone, light scheme, 900 px viewport (figure 720 px wide), as
x-pack/fig2-table-by-loop-count.png (1440 x 914 in the original pack).
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = {
    'fig2': ('#table figure.fig svg', 'fig2-table-by-loop-count.png'),
}


async def main(names, page, out):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        pg = await b.new_page(viewport={'width': 900, 'height': 900}, color_scheme='light', device_scale_factor=2)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(page.as_uri())
        await pg.wait_for_timeout(500)
        for n in names:
            sel, fname = ASSETS[n]
            f = out / fname
            await pg.locator(sel).screenshot(path=str(f))
            print(f'{n}: {f}')
        await b.close()
    assert not errs, errs


if __name__ == '__main__':
    a = sys.argv[1:]
    page = ROOT / 'every-line-is-a-loop.html'
    out = ROOT / 'x-pack'
    if '--page' in a:
        i = a.index('--page'); page = pathlib.Path(a[i + 1]).resolve(); del a[i:i + 2]
    if '--out' in a:
        i = a.index('--out'); out = pathlib.Path(a[i + 1]).resolve(); del a[i:i + 2]
    out.mkdir(parents=True, exist_ok=True)
    asyncio.run(main(a or ['fig2'], page, out))
