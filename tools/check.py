"""HANDOFF section 6 checks for every-line-is-a-loop.html.

1. Tags balanced; em dashes counted (allowed sparingly since 2026-10-20).
2. Full-page screenshots at 390 and 900 px, light and dark, with the
   interactive states engaged (Figure 3 day chip held, Figure 4 slider at 100).
   Any page error or console error fails the run.

Usage: .venv/bin/python tools/check.py [OUT_DIR] [--page PATH]   (default: shots/, the page beside tools/)
Uses the installed Google Chrome through Playwright (channel="chrome").
"""
import asyncio
import hashlib
import pathlib
import sys
from html.parser import HTMLParser

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / 'every-line-is-a-loop.html'
if '--page' in sys.argv:
    i = sys.argv.index('--page')
    PAGE = pathlib.Path(sys.argv[i + 1]).resolve()
    del sys.argv[i:i + 2]
VOID = ('meta', 'input', 'br', 'img', 'line', 'circle', 'ellipse', 'path', 'rect', 'polygon')


def static_checks():
    s = PAGE.read_text(encoding='utf-8')
    dashes = s.count('—')

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.err = [], []

        def handle_starttag(self, t, a):
            if t not in VOID:
                self.stack.append(t)

        def handle_endtag(self, t):
            if t in VOID:
                return
            if self.stack and self.stack[-1] == t:
                self.stack.pop()
            else:
                self.err.append((t, self.getpos()))

    p = P()
    p.feed(s)
    print('em dashes', dashes, '(sparingly); unclosed', p.stack, 'errors', p.err)
    assert not p.stack and not p.err, 'tag balance failed'


async def shots(out):
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        for w in (390, 900):
            for scheme in ('light', 'dark'):
                pg = await b.new_page(viewport={'width': w, 'height': 900}, color_scheme=scheme)
                errs = []
                pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
                pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
                await pg.goto(PAGE.as_uri())
                await pg.wait_for_timeout(500)
                if await pg.locator('button.chip[data-k="day"]').count():
                    await pg.click('button.chip[data-k="day"]')
                await pg.evaluate("const s=document.getElementById('t-w'); if (s) { s.value=100; s.dispatchEvent(new Event('input')) }")
                await pg.wait_for_timeout(500)
                f = out / f'shot_{w}_{scheme}.png'
                await pg.screenshot(path=str(f), full_page=True)
                h = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
                print(f'{f.name}  errors={len(errs)}  sha256={h}')
                assert not errs, errs
                await pg.close()
        await b.close()


if __name__ == '__main__':
    static_checks()
    asyncio.run(shots(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'shots'))
