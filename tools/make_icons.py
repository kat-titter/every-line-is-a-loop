"""Render the essay's two share images from SVG: the touch icon and the share card.

The tab icon itself is an inline SVG data URI in each page's head (the title mark, a line ending in a loop). Phones
and link previews need PNGs, so these two files are the repo's one exception to its no-binaries habit.

Writes: assets/icon-180.png (180 x 180, apple-touch-icon), assets/card.png (1200 x 630, og:image).
Run: .venv/bin/python tools/make_icons.py            (needs Playwright with Chrome)
     .venv/bin/python tools/make_icons.py --sizes DIR  also writes the tab icon at 16, 32 and 180 px into DIR
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIME, INK, MUTED = '#a5d63a', '#1c2226', '#68727a'
SANS = '"Helvetica Neue", Helvetica, Arial, sans-serif'
# the tab icon's own drawing (the same path as the data URI in the pages' heads)
ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="{s}" height="{s}">'
    '<rect width="32" height="32" rx="7" fill="#fff"/>'
    f'<path d="M4 24.5H20.5A7.75 7.75 0 0 0 20.5 9A7.75 7.75 0 0 0 20.5 24.5" fill="none" stroke="{LIME}" '
    'stroke-width="4.5" stroke-linecap="round"/></svg>'
)
# a touch icon has no rounded corner of its own (the phone crops it) and wants its mark inside a safe margin
TOUCH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="180" height="180">'
    '<rect width="32" height="32" fill="#fff"/>'
    f'<path d="M5.5 23.5H20A6.75 6.75 0 0 0 20 10A6.75 6.75 0 0 0 20 23.5" fill="none" stroke="{LIME}" '
    'stroke-width="4" stroke-linecap="round"/></svg>'
)
# the share card: the title, the mark drawn across the card (a line that ends in a loop), the subtitle, the author
CARD = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
<rect width="1200" height="630" fill="#fff"/>
<text x="89" y="232" font-family='{SANS}' font-size="104" font-weight="700" letter-spacing="-2.5" fill="{INK}">Every line is a loop</text>
<path d="M89 372H1010A62 62 0 0 0 1010 248A62 62 0 0 0 1010 372" fill="none" stroke="{LIME}" stroke-width="20" stroke-linecap="round"/>
<text x="89" y="470" font-family='{SANS}' font-size="38" font-weight="400" fill="{INK}">What would a maximally plausible periodic table</text>
<text x="89" y="520" font-family='{SANS}' font-size="38" font-weight="400" fill="{INK}">for biology look like?</text>
<text x="89" y="578" font-family="ui-monospace, Menlo, monospace" font-size="24" fill="{MUTED}">Kat Titterton</text>
</svg>'''


async def render(jobs: list[tuple[str, int, int, pathlib.Path]]) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        for svg, w, h, out in jobs:
            pg = await b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
            await pg.set_content(f'<body style="margin:0">{svg}</body>')
            await pg.screenshot(path=str(out), clip={'x': 0, 'y': 0, 'width': w, 'height': h})
            await pg.close()
            print(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out, f'{w} x {h}', f'{out.stat().st_size / 1000:.1f} KB')
        await b.close()


def main() -> None:
    (ROOT / 'assets').mkdir(exist_ok=True)
    jobs = [(TOUCH, 180, 180, ROOT / 'assets' / 'icon-180.png'), (CARD, 1200, 630, ROOT / 'assets' / 'card.png')]
    if '--sizes' in sys.argv:
        d = pathlib.Path(sys.argv[sys.argv.index('--sizes') + 1])
        d.mkdir(parents=True, exist_ok=True)
        jobs += [(ICON.format(s=s), s, s, d / f'icon-{s}.png') for s in (16, 32, 180)]
    asyncio.run(render(jobs))
    assert (ROOT / 'assets' / 'card.png').stat().st_size < 300_000, 'share card over 300 KB'


if __name__ == '__main__':
    main()
