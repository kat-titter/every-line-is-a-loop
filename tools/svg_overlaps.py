"""Run the path-sampling SVG legibility check (text on text, text on strokes, text
past the viewBox) on every figure of the page, after the interactive states are set.

Usage: .venv/bin/python tools/svg_overlaps.py [PAGE]
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK = pathlib.Path.home() / 'ex_gf/treble_2026/tools/legibility_check.js'


async def main(page):
    js = CHECK.read_text()
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        pg = await b.new_page(viewport={'width': 900, 'height': 900})
        await pg.goto(page.as_uri())
        await pg.wait_for_timeout(500)
        await pg.evaluate("const s=document.getElementById('t-w'); if (s) { s.value=100; s.dispatchEvent(new Event('input')) }")
        await pg.wait_for_timeout(500)
        res = await pg.evaluate(js)
        await b.close()
    n = 0
    for r in res:
        if r['overlaps']:
            n += len(r['overlaps'])
            print(json.dumps(r, ensure_ascii=False))
    print(f'{len(res)} svgs, {n} overlaps')


if __name__ == '__main__':
    asyncio.run(main(pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'every-line-is-a-loop.html'))
