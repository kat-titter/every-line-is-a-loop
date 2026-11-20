"""The essay's three reading budgets, counted the way the masthead counts the main read.

Kat's targets (2026-11-19): 15 minutes without the drop-downs, up to 30 with them, up to 1 hour
with all the supplemental data and methods. The three tiers nest, so a paragraph moved from the
main read into a fold leaves tier 1 and stays in tier 2; one moved from a chapter fold into the
Supplement leaves tier 2 and stays in tier 3. Only deleting words moves tier 3.

Usage: python3 analysis/read_budgets.py            the three budgets
       python3 analysis/read_budgets.py --chapters the main read, chapter by chapter
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fold_census as FC  # noqa: E402

ESSAY = pathlib.Path(__file__).resolve().parent.parent / 'every-line-is-a-loop.html'
TARGETS = (15, 30, 60)


def tiers(essay):
    """(words, minutes) for the main read, the main read with folds open, and everything but the sources."""
    body = essay[:essay.index('<section id="refs">')]
    chapters = body[:body.index('<section id="supplement">')]
    out = []
    for html, folds in ((body, 'closed'), (chapters, 'open'), (body, 'open')):
        n = len(FC.count_words(html, folds))
        out.append((n, max(1, round(n / FC.WPM))))
    return out


def main():
    essay = ESSAY.read_text(encoding='utf-8')
    names = ('main read, folds closed', 'chapters, folds open', 'all, supplement open')
    for (words, mins), name, target in zip(tiers(essay), names, TARGETS):
        room = target * FC.WPM - words
        print(f'{name:26s} {words:6d} words  {mins:3d} min   target {target:2d} min'
              f'  {"room for " + str(room) if room >= 0 else str(-room) + " over"}')

    if '--chapters' in sys.argv:
        import re
        body = essay[:essay.index('<section id="refs">')]
        chapters = body[:body.index('<section id="supplement">')]
        print('\nmain read by chapter (closed / open / what the folds add):')
        for m in re.finditer(r'<section id="([^"]+)">(.*?)(?=\n<section id="|$)', chapters, flags=re.S):
            shut = len(FC.count_words(m.group(2), 'closed'))
            full = len(FC.count_words(m.group(2), 'open'))
            print(f'  {m.group(1):10s} {shut:5d}  {full:5d}  +{full - shut:5d}')


if __name__ == '__main__':
    main()
