"""Export every-line-is-a-loop.html to a static PDF through the print stylesheet.

The slider is left where a fresh load puts it; the page's own beforeprint handler
must close Figure 4 and open the symbol key, so the PDF proves the print path a
reader gets with Cmd+P.

Usage: .venv/bin/python tools/export_pdf.py [OUT.pdf] [--a4] [--scheme dark]
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright
from pypdf import PdfReader, PdfWriter

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / 'every-line-is-a-loop.html'


async def export(out, fmt, scheme):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        pg = await b.new_page(viewport={'width': 900, 'height': 900}, color_scheme=scheme)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(PAGE.as_uri())
        await pg.wait_for_timeout(500)
        await pg.evaluate("window.__bp = 0; window.__ap = 0;"
                          "addEventListener('beforeprint', () => window.__bp++);"
                          "addEventListener('afterprint', () => window.__ap++);")
        before = await pg.evaluate("document.getElementById('t-w').value")
        await pg.pdf(path=str(out), format=fmt, print_background=True, prefer_css_page_size=False)
        after = await pg.evaluate("[window.__bp, window.__ap, document.getElementById('t-w').value, document.querySelector('#table details').open]")
        await b.close()
    print(f'slider before {before}; beforeprint fired {after[0]}, afterprint fired {after[1]}; '
          f'slider after {after[2]}; key open after {after[3]}; page errors {len(errs)}')
    assert not errs, errs
    assert after[0] >= 1, 'beforeprint did not fire'

    r = PdfReader(str(out))
    w = PdfWriter(clone_from=r)
    w.add_metadata({
        '/Title': 'Every line is a loop: a periodic table for biology',
        '/Author': 'Kat Titterton',
        '/Subject': 'Draft for comment, October 2026',
    })
    with open(out, 'wb') as f:
        w.write(f)
    box = r.pages[0].mediabox
    print(f'{out.name}: {len(r.pages)} pages, {float(box.width):.0f} x {float(box.height):.0f} pt, {out.stat().st_size // 1024} KB')


if __name__ == '__main__':
    a = sys.argv[1:]
    fmt = 'A4' if '--a4' in a else 'Letter'
    scheme = a[a.index('--scheme') + 1] if '--scheme' in a else 'light'
    pos = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or a[i - 1] != '--scheme')]
    out = pathlib.Path(pos[0]) if pos else ROOT / 'every-line-is-a-loop.pdf'
    asyncio.run(export(out, fmt, scheme))
