"""Pixel diff of two PNGs, computed in Chrome (no imaging library needed).

Usage: .venv/bin/python tools/pixdiff.py A.png B.png [A2.png B2.png ...]
Prints size, number of differing pixels, max channel delta and the bounding box.
"""
import asyncio
import base64
import pathlib
import sys

from playwright.async_api import async_playwright

JS = """async ([a, b]) => {
  const load = src => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = src; });
  const [ia, ib] = await Promise.all([load(a), load(b)]);
  if (ia.width !== ib.width || ia.height !== ib.height)
    return {size: [ia.width, ia.height, ib.width, ib.height], n: -1};
  const w = ia.width, h = ia.height;
  const px = img => { const c = new OffscreenCanvas(w, h); const x = c.getContext('2d'); x.drawImage(img, 0, 0); return x.getImageData(0, 0, w, h).data; };
  const da = px(ia), db = px(ib);
  let n = 0, mx = 0, x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let i = 0; i < da.length; i += 4) {
    const d = Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i+1] - db[i+1]), Math.abs(da[i+2] - db[i+2]));
    if (d) { n++; mx = Math.max(mx, d); const p = i / 4, x = p % w, y = (p - x) / w;
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  }
  return {size: [w, h], n, max: mx, box: n ? [x0, y0, x1, y1] : null};
}"""


def uri(p):
    return 'data:image/png;base64,' + base64.b64encode(pathlib.Path(p).read_bytes()).decode()


async def main(pairs):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        pg = await b.new_page()
        for a, c in pairs:
            r = await pg.evaluate(JS, [uri(a), uri(c)])
            print(pathlib.Path(a).name, r)
        await b.close()


if __name__ == '__main__':
    args = sys.argv[1:]
    asyncio.run(main(list(zip(args[0::2], args[1::2]))))
