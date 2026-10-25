"""Build count-the-elements.html, the companion post for the counting experiment, from results/.

Usage: python analysis/build_post.py
Reads results/tables_traj.json, results/tables_random.json, results/toys.json, results/r31_structure_traj.jsonl
and results/r31_dynamics.jsonl. Every count from the census comes from these files. The few things typed in
below (short model names, which molecules a flag points at, what kind of clock each dashed clock is, the
Baudier et al. row) are checked against the files by asserts, so the prose cannot drift from the data.
"""
import html as html_lib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
import post_math as PM  # noqa: E402
import table_figures as TF  # noqa: E402
import story_figures as SF  # noqa: E402
import bio_figures as BF  # noqa: E402
import elements as EL  # noqa: E402
import interactive as IA  # noqa: E402
R = ROOT / 'results'
MAIN = 'ref24_rank'
REPO_URL = 'https://github.com/kat-titter/every-line-is-a-loop'
TITLE = 'Every line is a loop. Let&#8217;s count them.'
MINUS = '&#8722;'
WORD = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
        11: 'eleven', 12: 'twelve'}
LOOPS = {1: 'one loop', 2: 'two loops', 3: 'three loops'}

# Short names for well-known curated models, used to label the squares of the census figure (priority order).
NAMES = [
    ('BIOMD0000000012', 'repressilator'), ('BIOMD0000000507', 'toggle switch'), ('BIOMD0000000036', 'fly day clock'),
    ('BIOMD0000000062', 'trp operon'), ('BIOMD0000000003', 'mitosis clock'), ('BIOMD0000000006', 'cell cycle'),
    ('BIOMD0000000020', 'squid giant axon'), ('BIOMD0000000016', 'fly day clock'), ('BIOMD0000000021', 'fly day clock'),
    ('BIOMD0000000171', 'fly day clock'), ('BIOMD0000000073', 'mammal day clock'), ('BIOMD0000000189', 'p53&#8211;Mdm2'),
    ('BIOMD0000000188', 'p53&#8211;Mdm2'), ('BIOMD0000000174', 'endosome switch'), ('BIOMD0000000201', 'somite clock'),
    ('BIOMD0000000098', 'calcium spikes'), ('BIOMD0000000318', 'Rb&#8211;E2F switch'), ('BIOMD0000000215', 'T-cell fate'),
    ('BIOMD0000000372', 'insulin&#8211;glucose'), ('BIOMD0000000304', 'bursting neuron'), ('BIOMD0000000179', 'cell memory'),
    ('BIOMD0000000033', 'growth signals'), ('BIOMD0000000313', 'IL-13 signalling'), ('BIOMD0000000039', 'calcium spikes'),
    ('BIOMD0000000225', 'glycolysis pulse'), ('BIOMD0000000040', 'BZ reaction'),
]
# The fruit fly's day clock (PER and TIM proteins), from each model's source paper (PubMed 8587874, 20540926,
# 9486845, 10366496, 10643740).
FLY_CLOCK = ['BIOMD0000000016', 'BIOMD0000000036', 'BIOMD0000000171', 'BIOMD0000000021', 'BIOMD0000000298']
# Clocks with no braking loop after the filters: what runs dry in each (from the model names and papers).
DEPLETION_KIND = {'BIOMD0000000039': 'calcium', 'BIOMD0000000045': 'calcium', 'BIOMD0000000098': 'calcium', 'BIOMD0000000113': 'calcium',
                  'BIOMD0000000114': 'calcium', 'BIOMD0000000166': 'calcium', 'BIOMD0000000184': 'calcium',
                  'BIOMD0000000225': 'glycolysis', 'BIOMD0000000236': 'glycolysis', 'BIOMD0000000319': 'enzyme'}
# Plain names for the molecules the loose running-total reading flags in the control models.
LOOSE_NAMES = {'BIOMD0000000429': {'species_7': 'the glycerol-making protein', 'species_13': 'glycerol outside the cell'},
               'BIOMD0000000603': {'acetate_e': 'acetate', 'ethanol_e': 'ethanol', 'glycerol_e': 'glycerol', 'biomass': 'biomass'},
               'BIOMD0000000006': {'v': 'total cyclin'},
               'BIOMD0000000404': {'Tni': 'two receptor complexes', 'Tni_W': 'two receptor complexes'}}
STRICT_NAMES = {'BIOMD0000000006': 'total cyclin'}

REFS = {
    'elowitz': 'Elowitz MB, Leibler S. A synthetic oscillatory network of transcriptional regulators. <i>Nature</i> 403:335&#8211;338 (2000). <a href="https://doi.org/10.1038/35002125">doi:10.1038/35002125</a>',
    'biomodels': 'Malik-Sheriff RS et al. BioModels: 15 years of sharing computational models in life science. <i>Nucleic Acids Res</i> 48(D1):D407&#8211;D415 (2020). <a href="https://doi.org/10.1093/nar/gkz1055">doi:10.1093/nar/gkz1055</a>',
    'baudier': 'Baudier A, Fages F, Soliman S. Graphical requirements for multistationarity in reaction networks and their verification in BioModels. <i>J Theor Biol</i> 459:79&#8211;89 (2018). <a href="https://doi.org/10.1016/j.jtbi.2018.09.024">doi:10.1016/j.jtbi.2018.09.024</a>',
    'yi': 'Yi T-M, Huang Y, Simon MI, Doyle J. Robust perfect adaptation in bacterial chemotaxis through integral feedback control. <i>Proc Natl Acad Sci USA</i> 97(9):4649&#8211;4653 (2000). <a href="https://doi.org/10.1073/pnas.97.9.4649">doi:10.1073/pnas.97.9.4649</a>',
    'muzzey': 'Muzzey D, G&#243;mez-Uribe CA, Mettetal JT, van Oudenaarden A. A systems-level analysis of perfect adaptation in yeast osmoregulation. <i>Cell</i> 138(1):160&#8211;171 (2009). <a href="https://doi.org/10.1016/j.cell.2009.04.047">doi:10.1016/j.cell.2009.04.047</a>',
    'soule': 'Soul&#233; C. Graphic requirements for multistationarity. <i>ComplexUs</i> 1:123&#8211;133 (2003). <a href="https://doi.org/10.1159/000076100">doi:10.1159/000076100</a>',
    'snoussi': 'Snoussi EH. Necessary conditions for multistationarity and stable periodicity. <i>J Biol Syst</i> 6(1):3&#8211;9 (1998). <a href="https://doi.org/10.1142/S0218339098000042">doi:10.1142/S0218339098000042</a>',
    'gouze': 'Gouz&#233; J-L. Positive and negative circuits in dynamical systems. <i>J Biol Syst</i> 6(1):11&#8211;15 (1998). <a href="https://doi.org/10.1142/S0218339098000054">doi:10.1142/S0218339098000054</a>',
    'kaufman': 'Kaufman M, Thomas R. Emergence of complex behaviour from simple circuit structures. <i>C R Biol</i> 326(2):205&#8211;214 (2003). <a href="https://doi.org/10.1016/S1631-0691(03)00063-5">doi:10.1016/S1631-0691(03)00063-5</a>',
    'gardner': 'Gardner TS, Cantor CR, Collins JJ. Construction of a genetic toggle switch in <i>Escherichia coli</i>. <i>Nature</i> 403:339&#8211;342 (2000). <a href="https://doi.org/10.1038/35002131">doi:10.1038/35002131</a>',
    'milo': 'Milo R, Shen-Orr S, Itzkovitz S, Kashtan N, Chklovskii D, Alon U. Network motifs: simple building blocks of complex networks. <i>Science</i> 298(5594):824&#8211;827 (2002). <a href="https://doi.org/10.1126/science.298.5594.824">doi:10.1126/science.298.5594.824</a>',
    'alon': 'Alon U. Network motifs: theory and experimental approaches. <i>Nat Rev Genet</i> 8(6):450&#8211;461 (2007). <a href="https://doi.org/10.1038/nrg2102">doi:10.1038/nrg2102</a>',
    'novak': 'Nov&#225;k B, Tyson JJ. Design principles of biochemical oscillators. <i>Nat Rev Mol Cell Biol</i> 9(12):981&#8211;991 (2008). <a href="https://doi.org/10.1038/nrm2530">doi:10.1038/nrm2530</a>',
    'briat': 'Briat C, Gupta A, Khammash M. Antithetic integral feedback ensures robust perfect adaptation in noisy biomolecular networks. <i>Cell Systems</i> 2(1):15&#8211;26 (2016). <a href="https://doi.org/10.1016/j.cels.2016.01.004">doi:10.1016/j.cels.2016.01.004</a>',
    'hucka': 'Hucka M et al. The systems biology markup language (SBML): a medium for representation and exchange of biochemical network models. <i>Bioinformatics</i> 19(4):524&#8211;531 (2003). <a href="https://doi.org/10.1093/bioinformatics/btg015">doi:10.1093/bioinformatics/btg015</a>',
    'lenovere': 'Le Nov&#232;re N et al. BioModels Database: a free, centralized database of curated, published, quantitative kinetic models of biochemical and cellular systems. <i>Nucleic Acids Res</i> 34:D689&#8211;D691 (2006). <a href="https://doi.org/10.1093/nar/gkj092">doi:10.1093/nar/gkj092</a>',
    'soliman': 'Soliman S. A stronger necessary condition for the multistationarity of chemical reaction networks. <i>Bull Math Biol</i> 75(11):2289&#8211;2303 (2013). <a href="https://doi.org/10.1007/s11538-013-9893-7">doi:10.1007/s11538-013-9893-7</a>',
    'sundials': 'Hindmarsh AC et al. SUNDIALS: suite of nonlinear and differential/algebraic equation solvers. <i>ACM Trans Math Softw</i> 31(3):363&#8211;396 (2005). <a href="https://doi.org/10.1145/1089014.1089020">doi:10.1145/1089014.1089020</a>',
    'chancourtois': 'B&#233;guyer de Chancourtois A-E. Vis tellurique: classement des corps simples ou radicaux (1862). Science Museum Group model, object 1925-647. <a href="https://collection.sciencemuseumgroup.org.uk/objects/co13134">collection record</a>',
    'tyson': 'Tyson JJ, Chen KC, Novak B. Sniffers, buzzers, toggles and blinkers: dynamics of regulatory and signaling pathways in the cell. <i>Curr Opin Cell Biol</i> 15(2):221&#8211;231 (2003). <a href="https://doi.org/10.1016/S0955-0674(03)00017-6">doi:10.1016/S0955-0674(03)00017-6</a>',
    'ahnert': 'Ahnert SE, Marsh JA, Hern&#225;ndez H, Robinson CV, Teichmann SA. Principles of assembly reveal a periodic table of protein complexes. <i>Science</i> 350(6266):aaa2245 (2015). <a href="https://doi.org/10.1126/science.aaa2245">doi:10.1126/science.aaa2245</a>',
    'ma': 'Ma W, Trusina A, El-Samad H, Lim WA, Tang C. Defining network topologies that can achieve biochemical adaptation. <i>Cell</i> 138(4):760&#8211;773 (2009). <a href="https://doi.org/10.1016/j.cell.2009.06.013">doi:10.1016/j.cell.2009.06.013</a>',
    'li': 'Li Z, Liu S, Yang Q. Incoherent inputs enhance the robustness of biological oscillators. <i>Cell Systems</i> 5(1):72&#8211;81.e4 (2017). <a href="https://doi.org/10.1016/j.cels.2017.06.013">doi:10.1016/j.cels.2017.06.013</a>',
    'aoki': 'Aoki SK, Lillacci G, Gupta A, Baumschlager A, Schweingruber D, Khammash M. A universal biomolecular integral feedback controller for robust perfect adaptation. <i>Nature</i> 570:533&#8211;537 (2019). <a href="https://doi.org/10.1038/s41586-019-1321-1">doi:10.1038/s41586-019-1321-1</a>',
    'lillacci': 'Lillacci G, Aoki S, Schweingruber D, Khammash M. A synthetic integral feedback controller for robust tunable regulation in bacteria. <i>bioRxiv</i> 170951 (2017). <a href="https://doi.org/10.1101/170951">doi:10.1101/170951</a>',
    'sontag': 'Sontag E, Veliz-Cuba A, Laubenbacher R, Jarrah AS. The effect of negative feedback loops on the dynamics of Boolean networks. <i>Biophys J</i> 95(2):518&#8211;526 (2008). <a href="https://doi.org/10.1529/biophysj.107.125021">doi:10.1529/biophysj.107.125021</a>',
    'roadrunner': 'Welsh C et al. libRoadRunner 2.0: a high performance SBML simulation and analysis library. <i>Bioinformatics</i> 39(1):btac770 (2023). <a href="https://doi.org/10.1093/bioinformatics/btac770">doi:10.1093/bioinformatics/btac770</a>',
    'takahashi': 'Takahashi JS. Transcriptional architecture of the mammalian circadian clock. <i>Nat Rev Genet</i> 18(3):164&#8211;179 (2017). <a href="https://doi.org/10.1038/nrg.2016.150">doi:10.1038/nrg.2016.150</a>',
    'ozbudak': 'Ozbudak EM, Thattai M, Lim HN, Shraiman BI, van Oudenaarden A. Multistability in the lactose utilization network of <i>Escherichia coli</i>. <i>Nature</i> 427(6976):737&#8211;740 (2004). <a href="https://doi.org/10.1038/nature02298">doi:10.1038/nature02298</a>',
    'barkai': 'Barkai N, Leibler S. Robustness in simple biochemical networks. <i>Nature</i> 387(6636):913&#8211;917 (1997). <a href="https://doi.org/10.1038/43199">doi:10.1038/43199</a>',
    'bardeen': 'Bardeen J, Brattain WH. The transistor, a semi-conductor triode. <i>Phys Rev</i> 74(2):230&#8211;231 (1948). <a href="https://doi.org/10.1103/PhysRev.74.230">doi:10.1103/PhysRev.74.230</a>',
    'perrier': 'Perrier C, Segr&#232; E. Radioactive isotopes of element 43. <i>Nature</i> 140(3535):193&#8211;194 (1937). <a href="https://doi.org/10.1038/140193b0">doi:10.1038/140193b0</a>',
    'ventura': 'Ventura A, Kirsch DG, McLaughlin ME, Tuveson DA, Grimm J, Lintault L, Newman J, Reczek EE, Weissleder R, Jacks T. Restoration of p53 function leads to tumour regression in vivo. <i>Nature</i> 445(7128):661&#8211;665 (2007). <a href="https://doi.org/10.1038/nature05541">doi:10.1038/nature05541</a>',
    'xue': 'Xue W, Zender L, Miething C, Dickins RA, Hernando E, Krizhanovsky V, Cordon-Cardo C, Lowe SW. Senescence and tumour clearance is triggered by p53 restoration in murine liver carcinomas. <i>Nature</i> 445(7128):656&#8211;660 (2007). <a href="https://doi.org/10.1038/nature05529">doi:10.1038/nature05529</a>',
    'postow': 'Postow MA, Sidlow R, Hellmann MD. Immune-related adverse events associated with immune checkpoint blockade. <i>N Engl J Med</i> 378(2):158&#8211;168 (2018). <a href="https://doi.org/10.1056/NEJMra1703481">doi:10.1056/NEJMra1703481</a>',
    'scerri': 'Scerri ER, Worrall J. Prediction and the periodic table. <i>Stud Hist Philos Sci A</i> 32(3):407&#8211;452 (2001). <a href="https://doi.org/10.1016/S0039-3681(01)00023-1">doi:10.1016/S0039-3681(01)00023-1</a>',
    'moseley': 'Moseley HGJ. The high-frequency spectra of the elements. <i>Philos Mag</i> 26(156):1024&#8211;1034 (1913). <a href="https://doi.org/10.1080/14786441308635052">doi:10.1080/14786441308635052</a>',
    'libsbml': 'Bornstein BJ, Keating SM, Jouraku A, Hucka M. LibSBML: an API library for SBML. <i>Bioinformatics</i> 24(6):880&#8211;881 (2008). <a href="https://doi.org/10.1093/bioinformatics/btn051">doi:10.1093/bioinformatics/btn051</a>',
}


def cite(*keys):
    """Placeholder, numbered by first appearance once the page is assembled."""
    return '<span class="cite">[' + ','.join('@' + k + '@' for k in keys) + ']</span>'


REF_POPOVER_JS = """<script>
(function () {
  // a citation opens a card with the reference and a link to the source; without JavaScript it jumps to the list
  var card = document.createElement('div'); card.className = 'ecard refcard'; card.setAttribute('role', 'dialog'); card.hidden = true; document.body.appendChild(card);
  var opener = null;
  function close() { if (card.hidden) return; card.hidden = true; card.classList.remove('on'); if (opener) { opener.setAttribute('aria-expanded', 'false'); opener.focus(); opener = null; } }
  function open(a) {
    var id = a.getAttribute('href').slice(1), li = document.getElementById(id); if (!li) return;
    var n = id.slice(1), src = li.querySelector('a[href]');
    card.innerHTML = '<p class="rc-k">reference ' + n + '</p><div class="rc-t">' + li.innerHTML + '</div><p class="rc-a">' +
      (src ? '<a class="rc-open" href="' + src.href + '" target="_blank" rel="noopener">open the source</a>' : '') + '<a href="#' + id + '">see it in the list</a></p>';
    card.setAttribute('aria-label', 'reference ' + n); card.hidden = false; card.classList.add('on');
    var r = a.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight, vw = document.documentElement.clientWidth;
    var below = r.bottom + 8 + h <= window.innerHeight || r.top - 8 - h < 0;
    card.style.left = (Math.min(Math.max(8, r.left), vw - w - 8) + window.scrollX) + 'px';
    card.style.top = ((below ? r.bottom + 8 : r.top - 8 - h) + window.scrollY) + 'px';
    a.setAttribute('aria-expanded', 'true'); opener = a;
    var first = card.querySelector('a'); if (first) first.focus();
  }
  document.addEventListener('click', function (e) {
    var s = e.target.closest('.rc-a a[href^="#r"]'); if (s) { var d = document.getElementById('refs-d'); if (d) d.open = true; close(); }
    var a = e.target.closest('.cite a');
    if (a) { e.preventDefault(); if (opener === a && !card.hidden) close(); else open(a); return; }
    if (!card.hidden && !card.contains(e.target)) close();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  [].forEach.call(document.querySelectorAll('.cite a'), function (a) { a.setAttribute('aria-haspopup', 'dialog'); a.setAttribute('aria-expanded', 'false'); });
  // a link into a closed supplement opens it (older browsers do not open a details on fragment navigation), and print shows them all
  function openTarget() { var t = location.hash && document.getElementById(location.hash.slice(1)), d = t && t.closest('details'); if (d) d.open = true; }
  openTarget(); addEventListener('hashchange', openTarget);
  addEventListener('beforeprint', function () { [].forEach.call(document.querySelectorAll('details.supp'), function (d) { d.open = true; }); });
})();
</script>"""


def number_refs(page):
    order = []
    for k in re.findall(r'@(\w+)@', page):
        if k not in order:
            order.append(k)
    num = {k: i + 1 for i, k in enumerate(order)}
    page = re.sub(r'\[((?:@\w+@,?)+)\]', lambda m: '[' + ', '.join(f'<a href="#r{num[k]}">{num[k]}</a>' for k in re.findall(r'@(\w+)@', m.group(1))) + ']', page)
    unused = set(REFS) - set(order)
    assert not unused, f'references never cited: {unused}'
    return page.replace('%REFS%', ''.join(f'<li id="r{num[k]}">{REFS[k]}</li>' for k in order))


def rows_grid():
    """Rows of the table as k-by-j grids: with n loops, k and j each run from 0 to n, so a row has (n + 1) x (n + 1) elements."""
    c, g, x, out, slot = 15, 3, 0, [], 86
    for n in (1, 2, 3):
        m = n + 1
        w = m * (c + g) - g
        x0 = x + max(0, (slot - w) / 2) if n == 1 else x
        for j in range(m):
            for k in range(m):
                out.append(f'<rect x="{x0 + k * (c + g):.0f}" y="{22 + j * (c + g)}" width="{c}" height="{c}" rx="3" fill="var(--tint)" stroke="var(--muted)" stroke-width="1"/>')
        mid = x0 + w / 2
        out.append(f'<text x="{mid:.1f}" y="{22 + 4 * (c + g) + 14}" text-anchor="middle" fill="var(--ink)" font-weight="600">{m} &#215; {m} = {m * m}</text>')
        out.append(f'<text x="{mid:.1f}" y="{22 + 4 * (c + g) + 31}" text-anchor="middle" fill="var(--muted)">{LOOPS[n]}</text>')
        x = max(x0 + w, mid + slot / 2) + 34
    W = x - 34
    out.append(f'<text x="0" y="12" fill="var(--muted)">across: loops that brake (k)</text>')
    return (f'<svg class="rows-grid" viewBox="-2 0 {W + 4} {22 + 4 * (c + g) + 38}" width="{W + 4}" role="img" '
            f'aria-label="Rows of the table as grids: one loop gives 2 by 2 = 4 elements, two loops 3 by 3 = 9, three loops 4 by 4 = 16; '
            f'across, how many loops brake; down, how many run through a running total" font-size="12.5">{"".join(out)}</svg>'
            '<p class="grid-key">down: loops through a running total (j)</p>')


def signs(nu, k):
    return ' '.join(['+'] * (nu - k) + [MINUS] * k)


def signs_html(nu, k):
    """The sign pattern with each glyph in its colour: lavender amplifies, amber brakes."""
    return ' '.join(['<span class="sp">+</span>'] * (nu - k) + ['<span class="sn">' + MINUS + '</span>'] * k)


def listing(items):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def cap(s):
    return s[0].upper() + s[1:]


# ---------------------------------------------------------------- page style
# One stylesheet for this page. Tokens first: four colours (ink = content; muted gray = secondary, axes, not found;
# lavender = amplify in strokes and text, found in fills, and links; amber = brake) with the surfaces they sit on,
# one serif for reading, one sans for labels, figures and UI, monospace for code only, and the golden-ratio scales.
LIGHT = ('--paper: #ffffff; --ink: #141414; --muted: #6a6a6a; --rule: #dcdcdc; '
         '--accent: #a98be0; --accent-text: #6f52c0; --accent-soft: rgba(169, 139, 224, 0.16); --accent-tint: #efe9fb; '
         '--accent2: #e39a5a; --accent2-text: #a4521a; --accent2-soft: rgba(227, 154, 90, 0.18); --orb2-lo: #b8622a; '
         '--plate: #f9f8fd; --tint: #f2f0f6; --lift: rgba(48, 32, 92, 0.2); --orb-hi: #ffffff; --orb-lo: #7a5fc7; color-scheme: light;')
DARK = ('--paper: #111214; --ink: #ececea; --muted: #9b9b98; --rule: #2d2f33; '
        '--accent: #cdb8ff; --accent-text: #cdb8ff; --accent-soft: rgba(205, 184, 255, 0.18); --accent-tint: #2b2737; '
        '--accent2: #f2b57c; --accent2-text: #f2b57c; --accent2-soft: rgba(242, 181, 124, 0.2); --orb2-lo: #c97a3e; '
        '--plate: #18171e; --tint: #1d1c23; --lift: rgba(0, 0, 0, 0.6); --orb-hi: #f6f1ff; --orb-lo: #8a6fd6; color-scheme: dark;')
STYLE = r'''
:root {
  %LIGHT%
  --serif: "Iowan Old Style", "Charter", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif;
  --code: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --s1: 3px; --s2: 5px; --s3: 8px; --s4: 13px; --s5: 21px; --s6: 34px; --s7: 55px; --s8: 89px;
  --t1: 12px; --t2: 14px; --t3: 16.5px; --t4: 19px; --t5: 23px; --t6: 31px; --title: clamp(42px, 8vw, 70px);
  --measure: 640px; --page: 760px;
  --raise: 0 1px 2px var(--lift), 0 6px 18px -10px var(--lift);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { %DARK% } }
:root[data-theme="dark"] { %DARK% }

/* base */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 var(--t3)/1.5 var(--sans); -webkit-font-smoothing: antialiased; }
a { color: var(--accent-text); text-decoration: none; }
a:hover, a:focus-visible { text-decoration: underline; text-underline-offset: 3px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
p { margin: 0 0 var(--s5); }
b, strong { font-weight: 600; }
figure { margin: 0; }
svg, svg text { font-family: var(--sans); }
code, pre { font-family: var(--code); font-size: 0.86em; }
pre { margin: var(--s3) 0; padding: var(--s4); background: var(--tint); border-radius: var(--s3); line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
pre code { font-size: inherit; }
.cite { font: 400 var(--t1)/1 var(--sans); color: var(--muted); vertical-align: 0.3em; white-space: nowrap; }
.cite a { color: inherit; text-decoration: none; border-bottom: 1px dotted var(--muted); }
.cite a:hover, .cite a:focus-visible, .cite a[aria-expanded="true"] { color: var(--accent-text); border-bottom-color: var(--accent-text); text-decoration: none; }
.cite a { position: relative; } .cite a::after { content: ""; position: absolute; inset: -6px -3px; } .cite a:only-child::after { left: -9px; right: -9px; }
.ecard.refcard { width: 320px; max-width: calc(100vw - 16px); pointer-events: auto; }
.refcard[hidden] { display: none; }
.rc-k { font: 500 12px/1.5 var(--sans); letter-spacing: 0.04em; color: var(--muted); }
.rc-t { font: 400 14px/1.5 var(--sans); color: var(--ink); margin: 3px 0 8px; }
.rc-t a { color: var(--accent-text); }
.rc-a { display: flex; flex-wrap: wrap; gap: 5px 21px; font: 500 14px/1.5 var(--sans); }
.rc-a a { color: var(--accent-text); }
.label { font: 500 var(--t1)/1.4 var(--sans); letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin: 0 0 var(--s3); }

/* layout: one reading column; figures may break out of it */
.post { max-width: var(--page); margin: 0 auto; padding: var(--s7) var(--s5) var(--s8); }
.text { max-width: var(--measure); }
section { margin: var(--s8) 0 0; }

/* masthead */
.mast { margin: 0 0 var(--s5); }
.eyebrow { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--s2) var(--s5); margin: 0 0 var(--s5); font: 500 var(--t1)/1.4 var(--sans); letter-spacing: 0.04em; color: var(--muted); }
.eyebrow .field { color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-right: 0; }
.mast h1 { font: 400 var(--title)/1.04 var(--serif); letter-spacing: -0.02em; margin: 0 0 var(--s4); }
.mast .sub { font: 400 var(--t5)/1.3 var(--serif); color: var(--muted); margin: 0 0 var(--s6); }
.mast .meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s1) var(--s5); font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); margin: 0; }
.mast .links { display: contents; }
.mast .meta a { display: inline-flex; align-items: center; min-height: 44px; padding: 0 var(--s3); margin: -11.5px calc(-1 * var(--s3)); font: 500 var(--t2)/1.5 var(--sans); }

/* reading text */
.text > p, .text li { font: 400 var(--t4)/1.6 var(--serif); }
.text > p.lede { font-size: var(--t5); line-height: 1.6; }
.text > p.coda { font-size: var(--t5); line-height: 1.6; margin: var(--s6) 0 0; }
.text ul { padding-left: var(--s5); margin: 0 0 var(--s5); }
.text li { margin: 0 0 var(--s3); }
.text li::marker { color: var(--muted); }
h2 { font: 400 var(--t6)/1.15 var(--serif); letter-spacing: -0.01em; margin: 0 0 var(--s5); }
.text h3 { font: 400 var(--t5)/1.3 var(--serif); margin: var(--s6) 0 var(--s3); }
.text > p.kicker { font: 500 var(--t1)/1.4 var(--sans); letter-spacing: 0.1em; color: var(--muted); margin: 0 0 var(--s3); }
.text > p.kicker .n { color: var(--muted); margin-right: var(--s3); }
math[display="block"] { display: block; margin: var(--s4) 0 var(--s5); font-size: var(--t5); }

/* summary and scorecard */
.abstract { margin: 0 0 var(--s6); }
.abstract > p:not(.label) { font: 400 var(--t4)/1.6 var(--serif); }
.abstract > p:last-child { margin-bottom: 0; }
.grid-fig { margin: 0 0 var(--s5); }
.grid-fig svg { display: block; max-width: 100%; height: auto; }
.grid-key { font: 400 var(--t1)/1.4 var(--sans); color: var(--muted); margin: var(--s1) 0 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--s4); }
/* each card is a subgrid of four rows (label, title, found, verdict), so the rows line up across neighbours */
.card { background: var(--paper); border: 1px solid var(--accent-soft); border-radius: var(--s4); padding: var(--s4) var(--s5); box-shadow: var(--raise); display: grid; grid-template-rows: subgrid; grid-row: span 4; row-gap: 0; }
.card .k { font: 500 var(--t1)/1.4 var(--sans); letter-spacing: 0.04em; color: var(--muted); margin: 0 0 var(--s1); }
.card h3 { font: 400 var(--t4)/1.3 var(--serif); margin: 0 0 var(--s4); }
.card dl { display: grid; grid-template-columns: auto 1fr; gap: var(--s2) var(--s4); margin: 0; font: 400 var(--t2)/1.5 var(--sans); }
.card dt { font: 500 var(--t1)/1.75 var(--sans); color: var(--muted); }
.card dd { margin: 0; }
.card .v { display: grid; grid-template-columns: auto 1fr; gap: var(--s3); align-items: baseline; margin: var(--s4) 0 0; font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); }
.card .v .chip { margin: 0; }
.chip { display: inline-block; font: 600 var(--t1)/1.4 var(--sans); color: var(--ink); border: 1px solid var(--rule); border-radius: 999px; padding: var(--s1) var(--s3); }
.chip > span { font-size: 1.1em; }

/* figures: lavender plates; nodes, cells and cards lift off them */
figure.fig { background: var(--plate); border: 1px solid var(--accent-soft); border-radius: var(--s5); padding: var(--s6) var(--s5) var(--s5); margin: var(--s6) 0 var(--s7); }
figure.fig svg { display: block; width: 100%; height: auto; }
figure.fig figcaption { max-width: var(--measure); margin: var(--s5) 0 0; font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); }
figure.fig figcaption b { color: var(--ink); }
figure.fig svg circle[fill="var(--paper)"][stroke], figure.fig svg rect[fill="var(--accent-soft)"] { filter: url(#fx-lift); }
figure.fig svg rect[fill="var(--accent-soft)"] { fill: var(--accent-tint); }
.interactive + .interactive { margin-top: var(--s5); }
/* panels share the text column's left edge; two to a row at the page width, one on a phone */
.pair { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: var(--s4) var(--s5); }
.pair > div { flex: 1 1 280px; max-width: none; }
.quad { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--s4) var(--s5); align-items: start; }
.bio { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: var(--s4) var(--s5); }
.bio > div { flex: 1 1 250px; max-width: none; }
.bio-key { padding: var(--s4) var(--s4) 0; font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); }
.bio-key > div { display: grid; grid-template-columns: 34px 1fr; align-items: center; gap: var(--s3); margin: 0 0 var(--s3); }
.bio-key .bk-g { display: inline-flex; align-items: center; justify-content: center; }
.bio-key .bk-int { font: italic 400 22px/1 var(--serif); color: var(--ink); }
.sp { color: var(--accent-text); } .sn { color: var(--accent2-text); }
.bio svg { display: block; width: 100%; height: auto; }
.solo { max-width: 348.5px; margin: 0; }   /* one pair slot wide, so its 330 viewBox renders at the pair's scale */
.scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.wide svg { min-width: 720px; }
.bars svg { max-width: 520px; margin: 0; }
.fig-narrow { display: none; }
.fig-narrow svg { max-width: 440px; margin: 0 auto; }
table { border-collapse: collapse; width: 100%; margin: var(--s4) 0 var(--s3); font: 400 var(--t2)/1.5 var(--sans); }
th, td { text-align: left; vertical-align: top; padding: var(--s3) var(--s4) var(--s3) 0; border-bottom: 1px solid var(--rule); hyphens: auto; }
th { font-weight: 600; }
table.key td:nth-child(2) { white-space: nowrap; }
.nowrap { white-space: nowrap; }

/* controls: one 44 px row, label | track | value; the track is drawn with the page's tokens, filled to --p */
.ctl { display: grid; grid-template-columns: auto 1fr auto; gap: var(--s4); align-items: center; max-width: 420px; margin: var(--s2) 0 0; }
.ctl label, .ctl output { font: 500 var(--t1)/1.4 var(--sans); color: var(--muted); min-width: 0; }
.ctl output { min-width: 3.5ch; text-align: right; }
.ctl input[type=range] { -webkit-appearance: none; appearance: none; width: 100%; height: 44px; margin: 0; background: transparent; }
.ctl input[type=range]::-webkit-slider-runnable-track { height: 4px; border-radius: 2px; background: linear-gradient(var(--accent), var(--accent)) 0 0 / var(--p, 50%) 100% no-repeat var(--tint); }
.ctl input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; margin-top: -8px; border-radius: 50%; background: var(--paper); border: 2px solid var(--accent); box-shadow: var(--raise); }
.ctl input[type=range]::-moz-range-track { height: 4px; border-radius: 2px; background: var(--tint); }
.ctl input[type=range]::-moz-range-progress { height: 4px; border-radius: 2px; background: var(--accent); }
.ctl input[type=range]::-moz-range-thumb { width: 20px; height: 20px; border-radius: 50%; background: var(--paper); border: 2px solid var(--accent); box-shadow: var(--raise); }
.arr, .sl-node { cursor: pointer; }
.sl-node circle { transition: stroke-width .15s ease, stroke .15s ease; }
.arr circle { transition: stroke .15s ease; }   /* the badge ring is the arrow's only focus mark, so its width changes at once */
.arr:focus, .sl-node:focus:not(:focus-visible) { outline: none; }
.arr:hover .badge, .arr:focus-visible .badge { stroke: var(--ink); stroke-width: 2; }
.sl-node:hover circle, .sl-node:focus-visible circle { stroke: var(--ink); stroke-width: 2; }
.sl-node:focus-visible { outline: 2px solid var(--ink); outline-offset: 1px; }
.sl-wrap .solo { max-width: 380px; }

/* Figure 6: the census funnel and the model explorer. Pressable things rest flat and tint on hover and when pressed. */
#funnel { max-width: var(--measure); margin: 0; }
.f-row { display: grid; grid-template-columns: 64px 1fr; grid-template-areas: "n bar" ". t"; gap: var(--s1) var(--s4); width: 100%; min-height: 48px; padding: var(--s3) var(--s4); margin: 0 0 var(--s2); text-align: left; font: inherit; color: var(--ink); background: transparent; border: 0; border-radius: var(--s4); box-shadow: none; cursor: pointer; transition: background-color .15s ease; }
.f-row:hover, .f-row:focus-visible { background: var(--accent-soft); }
.f-row[aria-pressed="true"] { background: var(--accent-tint); }
.f-n { grid-area: n; align-self: center; font: 600 var(--t3)/1 var(--sans); font-variant-numeric: tabular-nums; }
.f-bar { grid-area: bar; align-self: center; height: var(--s4); background: var(--tint); border-radius: var(--s3); overflow: hidden; }
.f-bar span { display: block; height: 100%; border-radius: var(--s3); background: var(--accent); }
.f-t { grid-area: t; font-size: var(--t2); }
/* the panels are stacked in one grid cell and one is shown, so the figure keeps its height */
.f-panel { max-width: var(--measure); margin: var(--s4) 0 0; padding: var(--s4) var(--s5); background: var(--paper); border-radius: var(--s4); box-shadow: var(--raise); display: grid; }
.f-panel > div { grid-area: 1 / 1; visibility: hidden; }
.f-panel > div.on { visibility: visible; }
.f-panel p:not(.label) { font: 400 var(--t2)/1.5 var(--sans); margin: 0 0 var(--s3); }
.explorer { max-width: var(--measure); margin: var(--s5) 0 0; }
.ex-lab, .ex-count { display: block; font: 500 var(--t1)/1.4 var(--sans); color: var(--muted); margin: 0 0 var(--s2); }
#ex-q { width: 100%; min-height: 44px; padding: var(--s3) var(--s4); font: 400 var(--t3) var(--sans); color: var(--ink); background: var(--paper); border: 1px solid var(--muted); border-radius: var(--s4); box-shadow: none; }
.ex-picks { display: flex; flex-wrap: wrap; gap: var(--s2); margin: var(--s3) 0; }
.pick { min-height: 44px; padding: 0 var(--s4); font: 500 var(--t2) var(--sans); color: var(--accent-text); background: var(--paper); border: 1px solid var(--accent); border-radius: 999px; box-shadow: none; cursor: pointer; transition: background-color .15s ease; }
.pick:hover, .pick[aria-pressed="true"] { background: var(--accent-tint); }
ol.ex-list { list-style: none; padding: 0; margin: 0; }
ol.ex-list li { padding: var(--s3) 0; border-bottom: 1px solid var(--rule); }
.ex-name { display: block; font-size: var(--t2); }
.ex-meta { display: block; margin-top: var(--s1); font: 400 var(--t1)/1.4 var(--sans); color: var(--muted); }
.ex-meta span + span { margin-left: var(--s4); }

/* hero: the spiral, one turn per row */
figure.hero { margin: 0 0 var(--s5); }
.hero-stage { position: relative; background: radial-gradient(ellipse 46% 52% at 50% 56%, var(--accent-soft), transparent 72%); }
#hero-svg { display: block; width: 100%; height: auto; touch-action: pan-y; cursor: grab; }
#hero-svg.over { cursor: pointer; }
#hero-svg:active { cursor: grabbing; }
#hero-svg:focus { outline: none; }
#hero-svg:focus-visible { outline: 2px solid var(--accent); outline-offset: var(--s2); border-radius: var(--s4); }
.hero-key { display: flex; flex-wrap: wrap; justify-content: flex-start; align-items: center; gap: var(--s3) var(--s6); margin: var(--s3) auto 0; font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); }
.hero-key .key { display: inline-flex; align-items: center; gap: var(--s3); }
.hero-key svg { flex: 0 0 auto; }

/* element cards, shared by the hero and the periodic table */
.ecard { position: absolute; z-index: 3; width: 272px; padding: var(--s4); background: var(--paper); border: 1px solid var(--accent-soft); border-radius: var(--s4);
         box-shadow: 0 1px 2px var(--lift), 0 8px 21px -8px var(--lift); pointer-events: none; opacity: 0; visibility: hidden; transform: translateY(3px);
         transition: opacity 0.14s ease, transform 0.14s ease, visibility 0.14s; }
.ecard.on { opacity: 1; visibility: visible; transform: none; }
.ecard.on.pinned { pointer-events: auto; }   /* a hover card is click-through; a pinned card is a reading surface */
/* two tiers: a hover card peeks (name, circuit, what it does); a pinned card reads in full (traces, models, examples) */
.ecard:not(.pinned) .ec-tr, .ecard:not(.pinned) .ec-h, .ecard:not(.pinned) .ec-h ~ * { display: none; }
.ecard p { margin: 0; }
.ecard svg, figure.fig .ecard svg, figure.fig .pt-el svg, figure.fig .pt-legend svg { display: inline-block; width: auto; height: auto; max-width: none; }
.pt-legend svg { vertical-align: -2px; margin-right: var(--s1); }
.ecard .ec-top { display: flex; justify-content: space-between; align-items: baseline; gap: var(--s3); }
.ecard .ec-k { font: 500 var(--t1)/1.5 var(--sans); letter-spacing: 0.04em; color: var(--muted); }
.ecard .ec-s { font: 500 var(--t1)/1.5 var(--sans); color: var(--accent-text); }
.ecard .ec-blank, .ecard .ec-candidate { color: var(--muted); }
.ecard .ec-t { font: 400 var(--t4)/1.3 var(--serif); color: var(--ink); margin: var(--s1) 0 var(--s2); }
.ecard .ec-sym { font: 600 var(--t4)/1 var(--sans); margin-right: var(--s3); }
.ecard .ec-glyph { margin: 0 0 var(--s2); line-height: 0; }
.ecard .ec-key { display: flex; flex-wrap: wrap; gap: var(--s1) var(--s4); font: 400 var(--t1)/1.5 var(--sans); color: var(--muted); margin: var(--s1) 0 0; }
.ecard .ec-d { font: 400 var(--t2)/1.5 var(--serif); color: var(--ink); margin: 0 0 var(--s3); }
.ecard .ec-tr { list-style: none; margin: 0; padding: 0; }
.ecard .ec-tr li { display: grid; grid-template-columns: 32px 1fr auto; align-items: center; gap: var(--s3); font: 400 var(--t2)/1.5 var(--sans); color: var(--ink); margin: 0; }
.ecard .ec-tr li i { font-style: normal; font-size: var(--t1); color: var(--muted); }
.ecard .ec-tr b { font-variant-numeric: tabular-nums; }
.ecard .ec-h { font: 500 var(--t1)/1.4 var(--sans); letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin: var(--s3) 0 var(--s1); padding-top: var(--s3); border-top: 1px solid var(--rule); }
.ecard .ec-x { font: italic 400 var(--t2)/1.5 var(--serif); color: var(--ink); }
.ecard .ec-l { font: 400 var(--t2)/1.5 var(--sans); color: var(--ink); }

/* Figure 3: the periodic table of loops */
.ptable { position: relative; --tile: 64px; }
.pt-axes { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: var(--s1) var(--s6); font: 400 var(--t1)/1.5 var(--sans); color: var(--muted); margin: 0 0 var(--s4); }
.pt-blocks { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-start; gap: var(--s5); }
.pt-h { font: 400 var(--t1)/1.4 var(--sans); color: var(--muted); margin: 0 0 var(--s2); }
.pt-h b { color: var(--ink); margin-right: var(--s2); }
.pt-grid { display: grid; gap: var(--s2); }
/* a tile's border says how it is known (muted: this census; ink: experiments; dashed: a looser reading or nothing yet); the tint says found */
.pt-el { position: relative; width: var(--tile); height: 84px; padding: 0; margin: 0; font: inherit; color: var(--ink); background: var(--paper); border: 1px solid var(--muted); border-radius: var(--s3); cursor: pointer; }
.pt-el.pt-found { background: var(--accent-tint); box-shadow: 0 1px 2px var(--lift), 0 4px 13px -8px var(--lift); }
.pt-el.pt-known { border: 2px solid var(--ink); }
.pt-el.pt-candidate { border: 1px dashed var(--muted); }
.pt-el.pt-blank { border: 1px dashed var(--muted); background: transparent; }
.pt-el:hover, .pt-el:focus-visible, .pt-el[aria-pressed="true"] { outline: 2px solid var(--ink); outline-offset: 1px; }
.pt-n { position: absolute; left: var(--s2); top: var(--s1); font: 500 11px/1.2 var(--sans); color: var(--muted); }
.pt-found .pt-n { color: var(--ink); }
.pt-sig { position: absolute; right: var(--s2); top: var(--s1); font: 600 11px/1.2 var(--sans); color: var(--ink); }
.pt-sym { position: absolute; left: 0; right: 0; top: 19px; font: 600 var(--t4)/1 var(--sans); text-align: center; color: var(--ink); letter-spacing: -0.01em; }
.sy-i { font-family: var(--serif); font-style: italic; font-weight: 400; margin-left: 1px; }
.sy-i sup { font: 600 11px/0 var(--sans); font-style: normal; }
.pt-tr { position: absolute; left: 50%; top: 45px; transform: translateX(-50%); line-height: 0; }
.pt-c { position: absolute; left: 0; right: 0; bottom: 4px; font: 600 11px/1 var(--sans); text-align: center; color: var(--ink); }
.pt-blank .pt-c, .pt-candidate .pt-c, .pt-blank .pt-sym { color: var(--muted); }
.pt-keybox { align-self: flex-start; }
.pt-anat { position: relative; width: 340px; max-width: 100%; height: 128px; }
.pt-el.pt-big { position: absolute; left: 0; top: 0; cursor: default; transform: scale(1.5); transform-origin: 0 0; }
.pt-el.pt-big { pointer-events: none; }   /* the sample in the key is a picture, not a button */
.pt-a { position: absolute; left: 112px; right: 0; font: 400 var(--t1)/1.35 var(--sans); color: var(--muted); white-space: nowrap; }
.pt-a::before { content: ""; position: absolute; left: -13px; top: 0.65em; width: var(--s3); border-top: 1px solid var(--muted); }
.pt-gap { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: var(--s2) var(--s6); font: 400 var(--t2)/1.5 var(--sans); margin: var(--s5) 0 0; }
.pt-legend { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: var(--s3) var(--s5); font: 400 var(--t1)/1.5 var(--sans); color: var(--muted); margin: var(--s4) 0 0; }
.pt-key { display: inline-block; width: 18px; height: 14px; margin-right: var(--s3); vertical-align: -2px; border: 1px solid var(--muted); border-radius: 3px; background: var(--paper); }
.pt-key.pt-found { background: var(--accent-tint); }
.pt-key.pt-known { border: 2px solid var(--ink); }
.pt-key.pt-candidate { border: 1px dashed var(--muted); }
.pt-key.pt-blank { border: 1px dashed var(--muted); background: transparent; }

/* Supplement A: element tiles beside carbon */
.tiles { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--s4); }
.tile { position: relative; width: 128px; height: 150px; background: var(--paper); border: 1px solid var(--muted); border-radius: var(--s2); }
.tile.chem { background: var(--paper); border-top: 3px solid var(--ink); }
.tile .z { position: absolute; left: var(--s3); top: var(--s2); font-size: var(--t1); }
.tile .cnt { position: absolute; right: var(--s3); top: var(--s2); font-size: var(--t1); color: var(--muted); letter-spacing: 0.04em; }
.tile .sym { position: absolute; left: 0; right: 0; top: 30px; height: 44px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: var(--t5); line-height: 1; }
.tile .rings { display: flex; gap: var(--s2); height: var(--s4); margin-top: var(--s2); }
.tile .ring { display: inline-block; width: 7px; height: 7px; border: 1.5px solid var(--muted); border-radius: 50%; }
.tile .nm { position: absolute; left: var(--s2); right: var(--s2); top: 84px; text-align: center; font-size: var(--t2); }
.tile .ms { position: absolute; left: var(--s2); right: var(--s2); top: 105px; text-align: center; font-size: var(--t1); color: var(--muted); }
.tile .ex { position: absolute; left: var(--s2); right: var(--s2); top: 125px; text-align: center; font-size: var(--t1); color: var(--muted); }

/* Supplements B and D: numbered steps through the code */
ol.steps { list-style: none; counter-reset: step; padding: 0; margin: 0; max-width: var(--measure); }
ol.steps > li { counter-increment: step; position: relative; padding: 0 0 var(--s5) var(--s6); font: 400 var(--t3)/1.5 var(--sans); }
ol.steps > li::before { content: counter(step); position: absolute; left: 0; top: 0; width: 26px; height: 26px; border: 1.5px solid var(--accent); border-radius: 50%; background: var(--paper); font: 500 var(--t2)/23px var(--sans); text-align: center; }
ol.steps .out { display: block; margin-top: var(--s2); color: var(--muted); }

/* supplements, methods and references */
details.supp { border-top: 1px solid var(--rule); }
details.supp[open] { padding-bottom: var(--s6); }
details.supp:last-of-type { border-bottom: 1px solid var(--rule); }
details.supp > summary { display: flex; align-items: center; gap: var(--s4); min-height: 55px; padding: var(--s4) 0; font: 400 var(--t4)/1.3 var(--serif); cursor: pointer; list-style: none; }
details.supp > summary::-webkit-details-marker { display: none; }
details.supp > summary::before { content: "\203A"; flex: 0 0 var(--s5); font: 400 var(--t5)/1 var(--sans); color: var(--muted); text-align: center; transition: transform 0.14s ease; }
details.supp[open] > summary::before { transform: rotate(90deg); }
details.supp > summary:hover { color: var(--accent-text); }
#methods > p, #methods li { font-size: var(--t3); line-height: 1.6; }
ol.refs { padding-left: var(--s5); margin: 0; }
.text ol.refs li { font: 400 var(--t2)/1.5 var(--sans); margin: 0 0 var(--s3); }
.end { margin-top: var(--s7); }
.end .meta { display: flex; flex-wrap: wrap; gap: var(--s1) var(--s5); font: 400 var(--t2)/1.5 var(--sans); color: var(--muted); }
.end a { display: inline-flex; align-items: center; min-height: 44px; }

/* a plate's negative margin equals its padding plus its border, so figure content shares the text column's left edge */
@media (min-width: 860px) {
  figure.fig { margin-left: calc(-1 * var(--s6) - 1px); margin-right: calc(-1 * var(--s6) - 1px); padding: var(--s6) var(--s6) var(--s5); }
  /* Figure 5: the four blocks in one row, the key in the slot under the first three */
  .pt-blocks { display: grid; grid-template-columns: auto auto auto auto; grid-template-areas: "a b c d" "key key key d"; gap: var(--s4); justify-content: start; align-items: start; }
  .pt-block:nth-child(1) { grid-area: a; } .pt-block:nth-child(2) { grid-area: b; } .pt-block:nth-child(3) { grid-area: c; } .pt-keybox { grid-area: key; } .pt-block:nth-child(5) { grid-area: d; }
}
@media (min-width: 701px) and (max-width: 859px) {
  figure.fig { margin-left: calc(-1 * var(--s5) - 1px); margin-right: calc(-1 * var(--s5) - 1px); padding: var(--s6) var(--s5) var(--s5); }
}
@media (min-width: 701px) {
  .sl-wrap { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s5); align-items: start; }
  .sl-wrap .solo, .sl-wrap .f-panel { max-width: none; margin: 0; }
  .ptable .ecard.pinned { max-height: calc(100% + var(--s5)); overflow: auto; }
}
@media (max-width: 700px) {
  .post { padding: var(--s6) var(--s5) var(--s7); }
  section { margin-top: var(--s7); }
  figure.fig { margin-left: calc(-1 * var(--s4) - 1px); margin-right: calc(-1 * var(--s4) - 1px); padding: var(--s5) var(--s4) var(--s4); border-radius: var(--s4); }
  .text > p.lede, .text > p.coda, .mast .sub { font-size: var(--t4); }
  .mast .meta { gap: var(--s5); }   /* the links' 44 px hit boxes clear the byline row above */
  .quad { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero-key { gap: var(--s2) var(--s5); }
  .fig-wide { display: none; }
  .fig-narrow { display: block; }
  .pt-keybox { order: -1; }
  /* element cards become a fixed sheet: at the bottom, or at the top when the tapped tile is in the lower half */
  .ptable .ecard, .hero-card { position: fixed; left: var(--s4); right: var(--s4); top: auto; bottom: var(--s4); width: auto; max-height: 42vh; overflow: auto; pointer-events: auto; }
  .ptable .ecard.up, .hero-card.up { top: var(--s4); bottom: auto; }
}
@media (prefers-reduced-motion: reduce) { .ecard, .f-row, .pick, .sl-node circle, .arr circle, details.supp > summary::before { transition: none; } }
@media print {
  html:root, html:root[data-theme="dark"], html:root:not([data-theme="light"]) { %LIGHT% }
  .post { max-width: none; padding: 0; }
  figure.fig { margin-left: 0; margin-right: 0; break-inside: avoid; }
  .fig-wide { display: block; }
  .fig-narrow, .ctl, .ex-picks { display: none; }
}
'''.replace('%LIGHT%', LIGHT).replace('%DARK%', DARK)


# ---------------------------------------------------------------- figures
SVG = ''   # the stylesheet gives every svg the page's sans
DASH_EMPTY = ' stroke-dasharray="3 3"'   # an empty square
DASH_CLOCK = ' stroke-dasharray="3 2"'   # a clock whose only brake the filters remove
# Arrowheads and bars come from the page's hidden <defs> (fx-arrow, fx-bar and their muted and ink copies), so every
# figure draws them at one size and in the meaning-carrying colour.


def node(x, y, t, r=22):   # one node style across the story and method figures
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--paper)" stroke="var(--muted)" stroke-width="1.4"/>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" fill="var(--ink)">{t}</text>')


def line(x1, y1, x2, y2, mk, cls):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" marker-end="url(#{mk})"/>'


def fig_method(toys):
    e, g = toys['enzyme'], toys['ring']
    assert e['thomas']['c'] == 5 and e[MAIN]['c'] == 0 and g[MAIN]['c'] == 1 and g[MAIN]['k'] == 1, toys
    st = ('<style>.f1g{stroke:var(--muted);stroke-width:1.4;stroke-dasharray:4 3}.f1k{stroke:var(--muted);stroke-width:1.4}'
          '.f1l{stroke:var(--accent2-text);stroke-width:2.2}</style>')
    enzyme = f'''<svg viewBox="0 0 330 270" role="img" aria-label="Enzyme E binds substrate S to make the pair ES, which releases product P. Five loops appear among E, S and ES, drawn dashed because none passes the filters." {SVG} font-size="14">
  {st}
  <text x="165" y="26" text-anchor="middle" font-weight="600" fill="var(--ink)">An enzyme at work</text>
  {line(70, 89, 70, 169, 'fx-bar-muted', 'f1g')}{line(54, 171, 54, 91, 'fx-bar-muted', 'f1g')}
  {line(81, 78, 142, 120, 'fx-arrow-muted', 'f1g')}{line(146, 134, 85, 92, 'fx-arrow-muted', 'f1g')}
  {line(81, 202, 142, 160, 'fx-arrow-muted', 'f1g')}{line(146, 146, 85, 188, 'fx-arrow-muted', 'f1g')}
  {line(181, 140, 244, 140, 'fx-arrow-muted', 'f1k')}
  {node(62, 70, 'E')}{node(62, 190, 'S')}{node(162, 140, 'ES')}{node(266, 140, 'P')}
  <text x="165" y="250" text-anchor="middle" fill="var(--muted)">{e['thomas']['c']} loops, none left after the filters</text>
</svg>'''
    ring = f'''<svg viewBox="0 0 330 270" role="img" aria-label="Three genes, lacI, tetR and cI, each switching off the next in a ring: one braking loop." {SVG} font-size="14">
  {st}
  <text x="165" y="26" text-anchor="middle" font-weight="600" fill="var(--ink)">The repressilator</text>
  {line(180, 84, 224, 165, 'fx-bar', 'f1l')}{line(212, 190, 120, 190, 'fx-bar', 'f1l')}{line(104, 166, 148, 87, 'fx-bar', 'f1l')}
  {node(165, 64, 'lacI')}{node(238, 190, 'tetR')}{node(92, 190, 'cI')}
  <text x="165" y="250" text-anchor="middle" fill="var(--ink)">1 braking loop: a clock</text>
</svg>'''
    return f'<div class="pair"><div>{enzyme}</div><div>{ring}</div></div>'


def fig_distribution(dist):
    cats = [('0', 'none'), ('1', '1'), ('2', '2'), ('3', '3'), ('4 to 10', '4 to 10'), ('over 10', 'more than 10'), ('over budget', 'search unfinished')]
    top = max(dist.get(c, 0) for c, _ in cats) or 1
    out = []
    for i, (c, lab) in enumerate(cats):
        v = dist.get(c, 0)
        y = 44 + i * 30 + (8 if c == 'over budget' else 0)
        w = max(220 * v / top, 2)
        if c in ('1', '2', '3'):
            bar = f'<rect x="130" y="{y}" width="{w:.1f}" height="18" rx="3" fill="var(--accent)"/>'
        else:
            bar = f'<rect x="130.5" y="{y + 0.5}" width="{w - 1:.1f}" height="17" rx="3" fill="none" stroke="var(--muted)"/>'
        out.append(f'<text x="120" y="{y + 13}" text-anchor="end" fill="var(--muted)">{lab}</text>{bar}'
                   f'<text x="{136 + w:.1f}" y="{y + 14}" fill="var(--ink)">{v}</text>')
    return f'''<svg viewBox="0 0 400 282" role="img" aria-label="How many models have no loop, one, two, three, four to ten, or more than ten loops, and for how many the search did not finish" {SVG} font-size="14">
  <text x="120" y="24" text-anchor="end" fill="var(--muted)">loops</text><text x="130" y="24" fill="var(--muted)">models</text>
  {''.join(out)}
</svg>'''


def table_square(x, y, nu, k, cells, ex):
    """One square of the census figure: sign pattern, a named model, and one small box per possible number of running totals."""
    CW, CH, SW, PITCH = 150, 112, 27, 33
    n = sum(v for (kk, _), v in cells.items() if kk == k)
    occ = n > 0
    out = [f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" rx="9" fill="{"var(--accent-soft)" if occ else "none"}" '
           f'stroke="{"var(--accent)" if occ else "var(--muted)"}" stroke-width="{1.5 if occ else 1}"{"" if occ else DASH_EMPTY}/>',
           f'<text x="{x + 12}" y="{y + 24}" fill="var(--ink)">{signs(nu, k)}</text>']
    if occ and ex:
        out.append(f'<text x="{x + 12}" y="{y + 46}" fill="var(--ink)">{ex}</text>')
    for j in range(nu + 1):
        sx = x + 12 + j * PITCH
        for q in range(j):  # hollow rings: how many loops keep a running total
            out.append(f'<circle cx="{sx + SW / 2 + (q - (j - 1) / 2) * 8:.1f}" cy="{y + 60}" r="3" fill="none" stroke="var(--muted)" stroke-width="1.3"/>')
        m = cells.get((k, j), 0)
        if m:
            out.append(f'<rect x="{sx}" y="{y + 70}" width="{SW}" height="28" rx="5" fill="var(--paper)" stroke="var(--accent)" stroke-width="1.2"/>'
                       f'<text x="{sx + SW / 2:.1f}" y="{y + 89}" text-anchor="middle" fill="var(--ink)">{m}</text>')
        else:
            out.append(f'<rect x="{sx}" y="{y + 70}" width="{SW}" height="28" rx="5" fill="none" stroke="var(--muted)" stroke-dasharray="3 3"/>')
    return ''.join(out)


def fig_table(rows, examples, narrow=False):
    """The census drawn in the essay's Figure 2 layout: one row per loop count, one square per sign pattern,
    and inside each square a strip of boxes for how many loops keep a running total (strict reading)."""
    CW, CH, GX, GY = 150, 112, 12, 18
    out, y = [], 0
    for nu in (1, 2, 3):
        Rr = rows[str(nu)]
        cells = {tuple(int(v) for v in k.strip('()').split(',')): n for k, n in Rr['essay']['cells'].items()}
        kinds = f'{(nu + 1) ** 2} possible, {Rr["essay"]["occupied"]} found'
        if narrow:
            out.append(f'<text x="6" y="{y + 20}" font-weight="600" fill="var(--ink)">{LOOPS[nu]}</text>'
                       f'<text x="318" y="{y + 20}" text-anchor="end" fill="var(--muted)">{kinds}</text>')
            y += 32
            for k in range(nu + 1):
                out.append(table_square(6 + (k % 2) * (CW + GX), y + (k // 2) * (CH + GX), nu, k, cells, examples.get((nu, k))))
            y += ((nu + 2) // 2) * (CH + GX) + 14
        else:
            X0 = 132
            out.append(f'<text x="{X0 - 14}" y="{y + 30}" text-anchor="end" font-weight="600" fill="var(--ink)">{LOOPS[nu]}</text>'
                       f'<text x="{X0 - 14}" y="{y + 50}" text-anchor="end" fill="var(--muted)">{(nu + 1) ** 2} possible</text>'
                       f'<text x="{X0 - 14}" y="{y + 68}" text-anchor="end" fill="var(--muted)">{Rr["essay"]["occupied"]} found</text>')
            for k in range(nu + 1):
                out.append(table_square(X0 + k * (CW + GX), y + 2, nu, k, cells, examples.get((nu, k))))
            y += CH + GY
    W = 324 if narrow else 132 + 4 * (CW + GX)
    H = y - (14 if narrow else GY) + 4
    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="The census drawn as the essay's table: rows for one, two and three loops, a square for each pattern of amplifying and braking loops, and inside each square one small box per possible number of loops keeping a running total" {SVG} font-size="14">
  {''.join(out)}
</svg>'''


BEHAVIOURS = [('multistable', 'holds two states'), ('oscillating', 'keeps time'), ('damped', 'rings, then settles'),
              ('steady', 'settles'), ('unbounded', 'grows without limit'), ('continuum', 'settles anywhere')]


def behaviour_panel(out, behav, depletion, x, y0, dx, dy, nus, header_y):
    for nu in nus:
        gx = x
        for k in range(nu + 1):
            cx = x + dx / 2
            out.append(f'<text x="{cx}" y="{y0 - 30}" text-anchor="middle" fill="var(--ink)">{signs(nu, k)}</text>')
            counts = behav.get((nu, k), {})
            for r, (b, _) in enumerate(BEHAVIOURS):
                cy = y0 + r * dy
                if (b == 'multistable' and k == nu) or (b == 'oscillating' and k == 0):
                    out.append(f'<rect x="{cx - dx / 2 + 3}" y="{cy - 16}" width="{dx - 6}" height="32" rx="6" fill="none" stroke="var(--muted)"/>')
                n = counts.get(b, 0)
                if n:
                    dep = b == 'oscillating' and k == 0 and depletion.get((nu, k))
                    out.append(f'<circle cx="{cx}" cy="{cy}" r="12" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1.3"'
                               f'{DASH_CLOCK if dep else ""}/>'
                               f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="var(--ink)">{n}</text>')
            x += dx
        out.append(f'<text x="{(gx + x) / 2}" y="{header_y}" text-anchor="middle" font-weight="600" fill="var(--ink)">{LOOPS[nu]}</text>'
                   f'<line x1="{gx + 6}" y1="{header_y + 8}" x2="{x - 6}" y2="{header_y + 8}" stroke="var(--rule)"/>')
        x += 20
    return x


def fig_behaviour(behav, depletion, narrow=False):
    """Dot matrix: what the models in each square do (models driven from outside left out)."""
    out = []
    if narrow:
        lx, dx, dy, y = 150, 46, 34, 0
        for nu in (1, 2, 3):
            y0 = y + 84
            for r, (_, lab) in enumerate(BEHAVIOURS):
                out.append(f'<text x="{lx}" y="{y0 + r * dy + 5}" text-anchor="end" fill="var(--muted)">{lab}</text>')
            behaviour_panel(out, behav, depletion, lx + 10, y0, dx, dy, (nu,), y0 - 58)
            y = y0 + (len(BEHAVIOURS) - 1) * dy + 34
        W, H = lx + 10 + 4 * dx + 6, y - 14
    else:
        x0, y0, dx, dy = 196, 78, 58, 38
        for r, (_, lab) in enumerate(BEHAVIOURS):
            out.append(f'<text x="{x0 - 16}" y="{y0 + r * dy + 5}" text-anchor="end" fill="var(--muted)">{lab}</text>')
        x = behaviour_panel(out, behav, depletion, x0, y0, dx, dy, (1, 2, 3), y0 - 54)
        W, H = x - 10, y0 + len(BEHAVIOURS) * dy - 14
    return f'''<svg viewBox="0 0 {W:.0f} {H}" role="img" aria-label="For each pattern of loops, how many models hold two states, keep time, ring then settle, settle, grow without limit, or settle anywhere" {SVG} font-size="14">
  {''.join(out)}
</svg>'''


# Tyson, Chen and Novak 2003 drew seven small circuits; BioModels' notes name the figure each model reproduces.
# Loops each name implies: (loops, braking loops), or 0 for none.
TEXTBOOK = [('BIOMD0000000312', 'perfect adapter', 0), ('BIOMD0000000311', 'mutual activation', (1, 0)),
            ('BIOMD0000000310', 'mutual inhibition (toggle)', (1, 0)), ('BIOMD0000000309', 'homeostasis by a braking loop', (1, 1)),
            ('BIOMD0000000308', 'braking-loop oscillator', (1, 1)), ('BIOMD0000000306', 'activator&#8211;inhibitor oscillator', (2, 1)),
            ('BIOMD0000000307', 'substrate-depletion oscillator', (2, 1))]
BEHAVIOUR_WORD = dict([('multistable', 'holds two states'), ('oscillating', 'keeps time'), ('continuum', 'settles anywhere'),
                       ('unbounded', 'grows without limit'), ('damped', 'rings, then settles'), ('steady', 'settles')])


def what_it_does(d):
    if not d or d.get('status') != 'ok':
        return 'not run'
    if d.get('forced'):
        return 'driven from outside'
    b = d.get('behaviours') or []
    if not b:
        return 'never settles'
    return next(w for k, w in BEHAVIOUR_WORD.items() if k in b)


def loops_word(p):
    if p is None:
        return 'no arrows'
    c, k = p
    return 'none' if c == 0 else signs(c, k)


def loops_html(p):
    """loops_word with each sign in its colour, so both columns of the answer key paint a sign one way."""
    if p is None or p[0] == 0:
        return loops_word(p)
    return signs_html(*p)


def fig_answer_key(struct, dyn):
    rows, agree, misses = [], 0, []
    for mid, name, want in TEXTBOOK:
        r = struct[mid]
        got = placement(r) if r.get('status') == 'ok' else None
        ok = (got == (0, 0)) if want == 0 else (got == want)
        agree += ok
        if not ok:
            misses.append(mid)
        rows.append(f'<tr><td>{name}</td><td>{"none" if want == 0 else signs_html(*want)}</td>'
                    f'<td>{loops_html(got)}{"" if ok else "&#160;&#10007;"}</td><td>{what_it_does(dyn.get(mid))}</td></tr>')
    table = ('<div class="scroll"><table class="key"><tr><th>Circuit</th><th>Its name implies</th><th>Census counts</th>'
             '<th>At published settings</th></tr>' + ''.join(rows) + '</table></div>')
    return table, agree, misses


def fig_pipeline(struct, dyn, starts):
    """The repressilator through the census, with the numbers read from the results."""
    import libsbml
    r, d = struct['BIOMD0000000012'], dyn['BIOMD0000000012']
    loop = r['loop_list']
    assert r['species'] == 6 and r['reactions'] == 12 and r['arcs'] == 6 and len(loop) == 1 and len(loop[0]['nodes']) == 6 and loop[0]['sign'] == '-', r
    assert r['integrator_nodes'] == 0 and d['runs'] == ['oscillating'] * starts, d
    m = libsbml.readSBMLFromFile(str(ROOT / 'data' / 'r31_curated' / 'BIOMD0000000012.xml')).getModel()
    law = libsbml.formulaToL3String(m.getReaction('Reaction11').getKineticLaw().getMath())
    assert law == 'a0_tr + a_tr * KM^n / (KM^n + PX^n)', law
    step = lambda title, text, code, out: (f'<li><b>{title}</b> {text}' + (f'<pre>{code}</pre>' if code else '') + f'<span class="out">{out}</span></li>')
    return '<ol class="steps">' + ''.join([
        step('Read the model.', f'BioModels stores each model as an SBML file: its molecules, its reactions and the rate law of every reaction. libRoadRunner {cite("roadrunner")} turns the file into equations it can solve.',
             "rr = roadrunner.RoadRunner(path)", 'Six molecules (three RNAs and three proteins) and twelve reactions.'),
        step('Read each arrow.', 'TetR&#8217;s RNA is made at a rate that falls as LacI protein (PX) rises:',
             law + '\n\nsg = s * (1 if st > 0 else -1)',
             'The code nudges LacI up by a tenth of a percent and the rate falls (s = &#8722;1). The reaction makes TetR RNA (st &gt; 0). So LacI brakes TetR. Reading every reaction this way, at five moments of the model&#8217;s own run, gives six arrows: each protein brakes the next gene, and each RNA amplifies its own protein.'),
        step('Find the loops.', 'A search walks the arrows and keeps every path that returns to its start, skipping any the filters forbid.',
             'found, complete = circuits(n, arcs, True, reverse, supports)',
             'One loop through all six molecules, with three brakes: a braking loop.'),
        step('Look for running totals.', 'A molecule keeps one if its own level appears in none of the rate laws that change it.',
             'if laws and all(v not in d for d in laws):\n    integ.add(i)',
             'Each RNA and protein decays at a rate set by its own level, so none does.'),
        step('Run it.', f'The model is simulated from its own start and {WORD[starts - 1]} others, and each run is labelled.',
             'starts = [x0] + spread_starts(x0, N, STARTS - 1, seed)',
             f'It keeps time from all {WORD[starts]} starts.'),
    ]) + '</ol>'


# ---------------------------------------------------------------- data helpers
def load_jsonl(p):
    return {d['model']: d for d in (json.loads(l) for l in open(p) if l.strip())}


def placement(r):
    m = r['defs'][MAIN]
    if not m.get('complete'):
        return None
    return m['c'], m['k']


def square_data(struct, dyn):
    """Named model per square (only models with no running total, so the name sits over its box), behaviours per
    square, and the clocks that sit in a square with no braking loop."""
    examples, behav, depletion, dep_models = {}, {}, {}, []
    order = {mid: i for i, (mid, _) in enumerate(NAMES)}
    best = {}
    for mid, r in struct.items():
        if r.get('status') != 'ok':
            continue
        p = placement(r)
        if not p or p[0] not in (1, 2, 3):
            continue
        m = r['defs'][MAIN]
        if mid in order and m['j'] == 0 and (p not in best or order[mid] < best[p]):
            best[p] = order[mid]
            examples[p] = dict(NAMES)[mid]
        d = dyn.get(mid)
        if not d or d.get('status') != 'ok' or d.get('forced'):
            continue
        b = set(d.get('behaviours') or [])
        if len(b) > 1:
            b.discard('steady')
        cnt = behav.setdefault(p, {})
        for x in b:
            cnt[x] = cnt.get(x, 0) + 1
        if 'oscillating' in b and m['k'] == 0:
            depletion[p] = depletion.get(p, 0) + 1
            dep_models.append(mid)
    return examples, behav, depletion, dep_models


def why_excluded(r):
    if r.get('status') == 'timeout':
        return 'ran out of time'
    if r.get('status') == 'no influence arcs':
        return 'gave no arrows at the states read'
    e = r.get('error', '')
    if 'delay' in e:
        return 'use delay equations'
    if 'not physically stored' in e or 'missing a value' in e or 'is missing' in e:
        return 'have values roadrunner cannot set'
    if 'qual' in e.lower() or 'logical' in e.lower() or 'no model' in e.lower() or 'reactions' in e.lower():
        return 'use logical rules'
    raise AssertionError(f'unclassified exclusion {r["model"]}: {e[:120]}')


# ---------------------------------------------------------------- page
def build(tables_traj, tables_random, toys_path, struct_path, dyn_path, out_path):
    T = json.load(open(tables_traj))
    TR = json.load(open(tables_random)) if tables_random and pathlib.Path(tables_random).exists() else None
    toys = json.load(open(toys_path))
    struct, dyn = load_jsonl(struct_path), load_jsonl(dyn_path)
    D = T['defs'][MAIN]
    rows = {str(k): v for k, v in D['rows'].items()}
    r1, r2, r3 = rows['1'], rows['2'], rows['3']
    small = r1['models'] + r2['models'] + r3['models']
    usable, census = T['usable'], sum(T['census'].values())
    examples, behav, depletion, dep_models = square_data(struct, dyn)
    th = T['theorem_checks']
    ms, osc = th['multistable'], th['oscillating']
    assert not th['multistable without refined positive circuit'] and not th['oscillating without negative circuit'], th
    autonomous = sum(1 for k, d in dyn.items() if d.get('status') == 'ok' and not d.get('forced') and struct.get(k, {}).get('status') == 'ok')
    dep = len(dep_models)
    assert set(dep_models) == set(DEPLETION_KIND), (sorted(dep_models), 'update DEPLETION_KIND')
    dep_plus = {nu: depletion.get((nu, 0), 0) for nu in (1, 2, 3)}
    kinds_count = {}
    for mid in dep_models:
        kinds_count[DEPLETION_KIND[mid]] = kinds_count.get(DEPLETION_KIND[mid], 0) + 1
    kind_words = {'calcium': ('is a calcium spike', 'are calcium spikes'), 'glycolysis': ('is a sugar-burning pulse in pancreatic cells', 'are sugar-burning pulses in pancreatic cells'),
                  'enzyme': ('is an enzyme oscillator', 'are enzyme oscillators')}
    dep_kinds = listing(f'{WORD[n]} {kind_words[k][n > 1]}' for k, n in sorted(kinds_count.items(), key=lambda x: -x[1]))
    dep_where = listing(f'{dep_plus[nu]} under {signs(nu, 0)}' for nu in (1, 2, 3) if dep_plus[nu])
    integ = T['integrators']
    strict_n = integ[[k for k in integ if k.startswith('models with any')][0]]
    complete_n = integ[[k for k in integ if k.startswith('models with complete')][0]]
    pt = T['paired_totals']
    pair_hits = pt['small models with a loop through one']
    assert pair_hits == ['BIOMD0000000639'], (pair_hits, 'update the paired-reading sentences')
    pair_occ = {nu: rows[str(nu)]['essay_pair']['occupied'] for nu in (1, 2, 3)}
    added = {nu: pair_occ[nu] - rows[str(nu)]['essay']['occupied'] for nu in (1, 2, 3)}
    assert added[1] == 1 and added[2] == 0 and added[3] == 0, added
    assert all(not c['pair_integrators'] for c in T['controls'].values()), 'controls now show paired totals'
    zt = toys['controller']
    assert zt['running_totals']['paired'] == [['z1', 'z2', 1, -1]] and zt[MAIN]['c'] == 1 and zt[MAIN]['k'] == 1, zt
    assert '(1, 1)' not in r1['essay_pair']['cells'], 'the controller box is no longer empty'
    assert not toys['enzyme']['running_totals']['paired'] and not toys['ring']['running_totals']['paired']
    integ_rows = load_jsonl(R / 'r31_integrators.jsonl') if (R / 'r31_integrators.jsonl').exists() else {}
    unchecked = sum(d.get('pair_unchecked') or 0 for d in integ_rows.values())
    near2 = r2.get('essay_near', {}).get('occupied', '?')
    near3 = r3.get('essay_near', {}).get('occupied', '?')
    rep, r24 = T['replication']['with reactions'], T['replication']['reference 24']
    assert (r24['models'], r24['no negative circuit'], r24['no positive circuit'], r24['no refined positive circuit']) == (506, 70, 48, 105)
    pct = lambda a, n: f'{100 * a / n:.0f}%' if n else 'n/a'
    cols = {nu: sum(1 for k in range(nu + 1) if any(c.startswith(f'({k},') for c in rows[str(nu)]['essay']['cells'])) for nu in (1, 2, 3)}
    by_k = {nu: {k: sum(v for c, v in rows[str(nu)]['essay']['cells'].items() if c.startswith(f'({k},')) for k in range(nu + 1)} for nu in (2, 3)}
    top2, top3 = max(by_k[2], key=by_k[2].get), max(by_k[3], key=by_k[3].get)
    # familiar circuits
    p_rep, p_trp = placement(struct['BIOMD0000000012']), placement(struct['BIOMD0000000062'])
    assert p_rep == (1, 1) and p_trp == (2, 2), (p_rep, p_trp)
    # fruit-fly day clock
    fp = {mid: placement(struct[mid]) for mid in FLY_CLOCK}
    assert all(fp.values()) and fp['BIOMD0000000171'] == fp['BIOMD0000000021'], fp
    def loops_at(mid, unit=False, each=''):
        c, k = fp[mid]
        n = f'{WORD.get(c, c)}{" loop" + ("s" if c > 1 else "") if unit else ""}{each}'
        return f'{n} ({signs(c, k)})' if c <= 3 else n
    fly_txt = (f'Goldbeter&#8217;s 1995 model has {loops_at("BIOMD0000000016", unit=True)}; Tyson and colleagues&#8217; 1999 model has {loops_at("BIOMD0000000036")}; '
               f'Leloup and Goldbeter&#8217;s 1998 and 1999 models have {loops_at("BIOMD0000000171", each=" each")}; '
               f'and their 1999 model with Gonze has {loops_at("BIOMD0000000298")}')
    fly_places = len(set(fp.values()))
    # where the essay's running-total examples sit
    ctl = T['controls']
    hog = [ctl[m]['loops'] for m in ('BIOMD0000000429', 'BIOMD0000000603')]
    assert all(isinstance(h, int) and h > 10 for h in hog), hog
    # controls table, with plain names checked against the flags
    ctl_rows = []
    for mid, c in ctl.items():
        assert c['status'] == 'ok', (mid, c)
        names = LOOSE_NAMES.get(mid, {})
        assert set(c['near_integrators']) == set(names), (mid, c['near_integrators'], 'update LOOSE_NAMES')
        loose = listing(sorted(set(names[x] for x in c['near_integrators']))) if c['near_integrators'] else 'none'
        if mid == 'BIOMD0000000603':
            loose = 'acetate, ethanol and glycerol outside the cell; biomass'
        strict = STRICT_NAMES.get(mid, 'yes') if c['strict_integrators_on_loops'] else 'none'
        assert bool(c['strict_integrators_on_loops']) == (mid in STRICT_NAMES), (mid, c)
        loops_txt = f"{c['loops']:,}" if isinstance(c['loops'], int) else 'thousands'
        label = re.sub(r' \(', ', has one (' if c['expected'] else ', has none (', c['label'], count=1)
        ctl_rows.append(f"<tr><td>{label}</td><td>{loops_txt}</td><td>{strict}</td><td>{loose}</td></tr>")
    ctl_rows = ''.join(ctl_rows)
    # the essay's test: kinds of behaviour per row
    fine = {nu: rows[str(nu)]['distinct_autonomous_behaviours'] for nu in (1, 2, 3)}
    coarse = {nu: len(rows[str(nu)]['coarse_behaviours']) for nu in (1, 2, 3)}
    pred = {nu: (nu + 1) ** 2 for nu in (1, 2, 3)}
    over = [nu for nu in (2, 3) if fine[nu] > pred[nu]]
    unsettled = sum(rows[str(nu)]['behaviours'].get('unsettled', 0) for nu in (1, 2, 3))
    # other counts of kinds, split recount, Sontag, independent loops
    t4 = {nu: rows[str(nu)]['types4'] for nu in (2, 3)}
    t3 = {nu: rows[str(nu)]['types3'] for nu in (2, 3)}
    sp = T['split']
    split_full = all(sp['patterns'][str(nu)] == nu + 1 for nu in (1, 2, 3))
    kpf = sum(rows[str(nu)]['k_pf_differs'] for nu in (1, 2, 3))
    nud = sum(rows[str(nu)]['nu_differs'] for nu in (1, 2, 3))
    # model 270, the filters' case study
    r270 = struct['BIOMD0000000270']
    m270 = r270['defs'][MAIN]
    assert r270['refined_positive'] is False and m270['complete'] and m270['k'] == m270['c'] > 0 and r270['conservation_laws'] == 9, m270
    # models left out
    excl = {}
    for r in struct.values():
        if r.get('status') != 'ok':
            excl.setdefault(why_excluded(r), []).append(r['model'])
    assert 'BIOMD0000000310' in excl.get('gave no arrows at the states read', []), 'Tyson mutual inhibition sentence'
    ex_order = ['use delay equations', 'use logical rules', 'have values roadrunner cannot set', 'ran out of time', 'gave no arrows at the states read']
    excl_txt = listing(f'{len(excl[w])} {w}' for w in ex_order if w in excl)
    # signs at random states, quoted only if the proven rules hold there too
    rob = ''
    if TR:
        thr = TR['theorem_checks']
        RR = {str(k): v for k, v in TR['defs'][MAIN]['rows'].items()}
        if not thr['multistable without refined positive circuit'] and not thr['oscillating without negative circuit']:
            rob = (f' It gives {RR["2"]["essay"]["occupied"]} of 9 elements at two loops and {RR["3"]["essay"]["occupied"]} of 16 at three, '
                   f'and the two proven rules still hold.')
        else:
            bad = len(thr['multistable without refined positive circuit']) + len(thr['oscillating without negative circuit'])
            rob = (f' It gives {RR["2"]["essay"]["occupied"]} of 9 and {RR["3"]["essay"]["occupied"]} of 16, but loses arrows: '
                   f'{bad} models then seem to break a proven rule, so those numbers are not used.')
    defs = [('thomas', 'every loop, as drawn'), ('ref24', 'after the filters'), ('ref24_rank', 'after the filters and the rank test (used here)')]
    def_rows = ''.join(f"<tr><td>{lab}</td>" + ''.join(f"<td>{T['defs'][d]['rows'][n]['models']}</td>" for n in ('1', '2', '3')) + '</tr>' for d, lab in defs)
    starts = int(re.search(r'^STARTS = (\d+)', (ROOT / 'analysis' / 'dynamics.py').read_text(), re.M).group(1))
    le3 = sum(D['distribution'].get(c, 0) for c in ('0', '1', '2', '3'))
    unfinished = D['distribution'].get('over budget', 0)
    runtime = 'about two hours'

    dyn_status = {}
    for d_ in dyn.values():
        dyn_status[d_.get('status')] = dyn_status.get(d_.get('status'), 0) + 1
    n_near = sum(1 for d_ in integ_rows.values() if d_.get('near_integrators'))
    step2 = lambda title, text, out: f'<li><b>{title}</b> {text}<span class="out">{out}</span></li>'
    pipeline_html = '<ol class="steps">' + ''.join([
        step2('<code>get_biomodels.sh</code>', 'downloads BioModels release 31, checks its SHA-256 and unpacks the curated models.', f'{census} model files.'),
        step2('<code>loops.py</code>', 'reads each model, reads every arrow at five states of its own run, lists loops under three definitions, marks strict running totals, and asks <code>elim.py</code> whether an amplifying loop survives the filters.',
              f'{usable} models read; {small} with one to three loops after the filters; {unfinished} searches unfinished.'),
        step2('<code>loops.py</code> again', 'repeats the count with signs read at random states.', 'A check on the sign reading.'),
        step2('<code>dynamics.py</code>', f'runs each readable model from {WORD[starts]} starts and labels what it does.',
              f'{autonomous} run on their own; {th["forced models excluded"]} are driven from outside; {dyn_status.get("timeout", 0)} ran out of time.'),
        step2('<code>integrators.py</code>', 'adds the loose and paired running-total readings.', f'{n_near} models with a loose running total; {len(pt["models with one"])} with a paired one.'),
        step2('<code>tabulate.py</code>, <code>report_tables.py</code>', 'place every model in the table, count elements four ways, and run the proven-rule checks, the controls and the replication.', 'tables_traj.json, tables_random.json, tables.md.'),
        step2('<code>toys.py</code>', 'builds the enzyme, the ring and the controller as models and counts them.', 'Fails the run if any toy changes.'),
        step2('<code>build_post.py</code>', 'writes this page from the tables.', 'Refuses to build if a sentence no longer matches the data.'),
    ]) + '</ol>'
    F = dict(score=1, model=2, lineloop=3, arrows=4, toy=5, cruise=6, tiles=7, orbitals=8, table=9, spiral=10, street=11,
             filters=12, code=13, dist=14, census=15, coast=16, behaviour=17, key=18, pipeline=19)
    coast_html, coast_len = IA.coast()
    fp_max = max(c for c, _ in fp.values())
    fp_min = min(c for c, _ in fp.values())
    ad_num, ad_sym = TF.NUMBER[(1, 1, 1)], EL.symbol(1, 1, 1)[0]
    sw_num, sw_sym = TF.NUMBER[(1, 0, 1)], EL.symbol(1, 0, 1)[0]
    assert ad_sym == 'Ad', ad_sym
    stages = [
        (census, census, 'curated models in release 31',
         'Downloaded BioModels release 31 (193 MB) and checked its SHA-256 checksum.',
         'Anyone who reruns the code gets the same files.'),
        (usable, census, 'read as equations',
         f'Read each model with libSBML and compiled it with libRoadRunner. {census - usable} could not be used: {excl_txt}.',
         'The census needs ordinary rate equations that it can differentiate and simulate.'),
        (complete_n, census, 'with every loop listed',
         f'Read each arrow&#8217;s sign at five moments of the model&#8217;s own run, then listed every loop that survives the filters. For {unfinished} models the search reached its step limit.',
         'Signs read where the model actually runs show the circuit as published; the filters remove loops that chemistry makes for free.'),
        (small, census, 'with one to three loops',
         'Placed each in the table by its loops, braking loops and running totals.',
         'These rows hold the 4, 9 and 16 elements that the table&#8217;s predictions are about.'),
        (autonomous, census, 'that run on their own',
         f'Simulated each from {WORD[starts]} starting states and labelled what it did: settles, keeps time, holds two states, and so on. {th["forced models excluded"]} models driven by an outside schedule were set aside.',
         'The proven rules, and the table&#8217;s claims, are about circuits left to themselves.'),
    ]
    funnel_html = IA.funnel(stages)
    ex_rows = []
    for mid, r in sorted(struct.items()):
        if r.get('status') != 'ok':
            continue
        m = r['defs'][MAIN]
        if not m.get('complete'):
            loops_txt, pattern, el = 'too many loops to list', '', None
        else:
            c_, k_, j_ = m['c'], m['k'], m['j']
            loops_txt = f'{c_} loop' + ('' if c_ == 1 else 's')
            pattern = (signs(c_, k_) + (' ' + '\u222b' * j_ if j_ else '')) if c_ else 'no loop'
            el = TF.NUMBER.get((c_, k_, j_)) if c_ <= 3 else None
        ex_rows.append({'id': str(int(mid[-6:])), 'name': r.get('name') or mid, 'loops': loops_txt,
                        'pattern': pattern.replace(MINUS, '\u2212'), 'element': el, 'does': what_it_does(dyn.get(mid))})
    assert len(ex_rows) == usable
    occ = {}
    for r_ in ex_rows:
        if r_['element'] is not None:
            occ[r_['element']] = occ.get(r_['element'], 0) + 1
    # loose and paired readings of the running totals, as in tabulate.py, to list candidates for the blanks
    near_el, pair_el = {}, {}
    for mid, r in struct.items():
        m = r.get('defs', {}).get(MAIN, {}) if r.get('status') == 'ok' else {}
        if not m.get('complete') or not 1 <= (m.get('c') or 0) <= 3 or r.get('loop_list') is None:
            continue
        ig = integ_rows.get(mid, {})
        near, pair = set(ig.get('near_integrators') or []), set(ig.get('pair_nodes') or [])
        kk = sum(1 for l in r['loop_list'] if l['sign'] == '-')
        near_el[mid] = TF.NUMBER.get((m['c'], kk, sum(1 for l in r['loop_list'] if set(l['nodes']) & near)))
        pair_el[mid] = TF.NUMBER.get((m['c'], kk, sum(1 for l in r['loop_list'] if l['integrates'] or set(l['nodes']) & pair)))
    short = {str(int(mid[-6:])): html_lib.unescape(nm) for mid, nm in reversed(NAMES)}
    hero_els = []
    for e in TF.ELEMENTS:
        num, (n_, k_, j_) = TF.NUMBER[e], e
        row = [x for x in TF.ELEMENTS if x[0] == n_]
        sig = (signs(n_, k_) + (' ' + '\u222b' * j_ if j_ else '')).replace(MINUS, '\u2212') if n_ else 'no loop'
        sym, sym_html = EL.symbol(n_, k_, j_)
        inside = [x for x in ex_rows if x['element'] == num]
        does = {}
        for x in inside:
            if x['does'] not in ('not run', 'never settles'):
                does[x['does']] = does.get(x['does'], 0) + 1
        census_ex = []
        for x in inside:
            nm = short.get(x['id'])
            if nm and nm not in census_ex:
                census_ex.append(nm)
        def clip(t, w=44):
            t = t.replace('_', ' ')
            return t if len(t) <= w else t[:t.rfind(' ', 0, w)] + '\u2026'
        cands = [] if inside else sorted({clip(struct[mid].get('name') or mid) for mid in near_el
                                          if near_el[mid] == num or pair_el.get(mid) == num})
        essay_ex = EL.ESSAY_EXAMPLES.get(e, [])
        status = 'found' if inside else 'known' if essay_ex else 'candidate' if cands else 'blank'
        D_ = EL.describe(n_, k_, j_)
        hero_els.append(dict(D_, num=num, n=n_, k=k_, j=j_, i=row.index(e), L=len(row), count=len(inside), status=status,
                             statusText={'found': f'found in {len(inside)} curated models', 'known': 'known from experiments',
                                         'candidate': 'candidates to check', 'blank': 'not found yet'}[status],
                             sig=sig, sigShort=''.join('<span class="sp">+</span>' if ch == '+' else '<span class="sn">\u2212</span>' if ch == '\u2212' else ch for ch in sig.replace(' ', '')) if n_ else '', sym=sym, symHtml=sym_html, observed=sorted(does.items(), key=lambda t: -t[1])[:3],
                             examples=census_ex[:3], essay=essay_ex[:3], candidates=cands[:3]))
    assert sum(h['count'] for h in hero_els if h['n']) == small, 'element counts must match the placed models'
    top_ = [h for h in hero_els if h['j'] == 0]
    rest_ = [h for h in hero_els if h['j'] > 0]
    found_top = (sum(h['status'] == 'found' for h in top_), len(top_))
    found_rest = (sum(h['status'] == 'found' for h in rest_), len(rest_))
    rest_models = sum(h['count'] for h in rest_)
    assert found_top == (10, 10) and found_rest[1] == 20, (found_top, found_rest)
    EL.check_unique(TF.ELEMENTS)
    ptable_html = IA.periodic_table(hero_els, found_top, found_rest)
    hero_html = IA.hero(hero_els)
    explorer_html = IA.explorer(ex_rows, [('repressilator', 'repressilator'), ('toggle', 'toggle'), ('day clocks', 'circ'),
                                          ('calcium', 'calcium'), ('p53', 'p53'), ('cell cycle', 'cell cycle')])
    science_html = IA.science_loop([
        ('idea', 'Loops sort circuits into (n + 1)<sup>2</sup> elements per row (claims 1 to 3).',
         'Count loops on a reduced model, with fast binding steps merged, so the count does not depend on detail; test nesting order as a fourth count.'),
        ('predict', 'No more than 9 and 16 kinds of behaviour; no switch without an amplifying loop; no clock without a braking one.',
         'Write down which blanks newer models will fill before looking, for example antithetic controllers in element 3.'),
        ('test', f'A census of {usable} curated models from BioModels release 31, at their published settings.',
         'Enumerate every small circuit per element across thousands of rate settings, and rerun the census on the current release.'),
        ('result', 'Every mix of amplifying and braking loops used, no theorem broken, behaviour within the bound at one setting, running totals unreadable, one clock in four places.',
         'Report, per element, the full range of behaviours and how often each appears.'),
        ('refine', 'Found the grain problem and the detector problem, fixed a counting bug, added a paired detector.',
         'Benchmark running-total detectors on models with known answers, and decide whether braking loops should be filtered.'),
    ])
    def card(label, title, found, mark, verdict, note):
        # label, title, what was found, verdict: the title says the test, so the found line carries what it needs of it
        return (f'<div class="card"><p class="k">{label}</p><h3>{title}</h3><dl><dt>found</dt><dd>{found}</dd></dl>'
                f'<p class="v"><span class="chip"><span aria-hidden="true">{mark}</span> {verdict}</span>{note}</p></div>')
    assert '(1, 1)' not in r1['essay']['cells'] and '(1, 1)' not in r1['essay_pair']['cells']
    scorecard = '<div class="cards">' + ''.join([
        card('claim 1', 'No more kinds of behaviour than elements',
             f'Two loops: {fine[2]} kinds, {pred[2]} elements. Three loops: {fine[3]} kinds, {pred[3]} elements.', '&#126;', 'holds, softly',
             'Each model ran at one setting of its rates.'),
        card('claim 2', 'Loops forbid some behaviours',
             f'No memory without an amplifying loop, no clock without a brake, in {autonomous} models.', '&#10003;', 'holds', 'Both rules are theorems, so this checks the code.'),
        card('claim 3', 'Every element can exist',
             f'Every mix of amplifying and braking loops. At two loops a strict detector fills {r2["essay"]["occupied"]} of {pred[2]} elements, a loose one {near2}.', '?', 'untested',
             'No detector reads running totals reliably yet.'),
        card('surprise', 'One circuit, one address',
             f'{cap(WORD[len(FLY_CLOCK)])} models of one clock land in {WORD[fly_places]} places.', '!', 'depends on the drawing', ''),
    ]) + '</div>'
    key_table, key_agree, key_misses = fig_answer_key(struct, dyn)
    assert key_agree == 5 and key_misses == ['BIOMD0000000310', 'BIOMD0000000307'], (key_agree, key_misses)
    assert placement(struct['BIOMD0000000307'])[1] == 0 and struct['BIOMD0000000307']['defs']['thomas']['k'] == 1, 'depletion brake sentence'
    key_does = {mid: what_it_does(dyn.get(mid)) for mid, _, _ in TEXTBOOK}
    assert key_does['BIOMD0000000311'] == 'holds two states' and all(key_does[m] in ('settles', 'rings, then settles') for m in ('BIOMD0000000306', 'BIOMD0000000307', 'BIOMD0000000308')), key_does
    no_arrows = len(excl.get('gave no arrows at the states read', []))
    # the audit story quotes the first run (before the backtracking fix) against this one
    assert small == 175 and r3['essay']['occupied'] == 5, 'update the audit sentence in Supplement B'
    if over:
        test_verdict = (f'At {listing(LOOPS[nu] for nu in over)} that is more kinds of behaviour than elements, which by the essay&#8217;s own terms kills the rule, '
                        f'at least with behaviour sorted this finely.')
    else:
        test_verdict = 'Neither two nor three loops shows more kinds of behaviour than it has elements, so by the essay&#8217;s own terms the rule survives.'
    if fine[1] > pred[1] and not over:
        test_verdict += (f' One loop shows more than its {pred[1]}, though the essay set its test at two and three loops, '
                         f'and merged into four behaviours it gives {"exactly " if coarse[1] == pred[1] else ""}{coarse[1]}.')

    code_link = f'{REPO_URL}/tree/main/analysis' if REPO_URL else 'analysis/README.md'
    data_link = f'{REPO_URL}/blob/main/results/tables.md' if REPO_URL else 'results/tables.md'
    repo_line = f' The repository is at <a href="{REPO_URL}">{REPO_URL.split("//")[1]}</a>.' if REPO_URL else ''
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{TITLE}</title>
<meta name="description" content="Counting the feedback loops in {usable} curated BioModels against the loop table's prediction of {pred[2]} and {pred[3]} elements at two and three loops, with the code that does it.">
<style>{STYLE}</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<filter id="fx-lift" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="1.6" stdDeviation="2.2" style="flood-color: var(--lift)"/></filter>
<radialGradient id="fx-orb" cx="36%" cy="30%" r="72%"><stop offset="0" style="stop-color: var(--orb-hi)"/><stop offset="0.5" style="stop-color: var(--accent)"/><stop offset="1" style="stop-color: var(--orb-lo)"/></radialGradient>
<marker id="fx-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--accent-text)"/></marker>
<marker id="fx-arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--muted)"/></marker>
<marker id="fx-arrow-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--ink)"/></marker>
<marker id="fx-bar" viewBox="0 0 3 10" refX="2" refY="5" markerWidth="3" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M1.5 0V10" stroke="var(--accent2-text)" stroke-width="2.2"/></marker>
<marker id="fx-bar-muted" viewBox="0 0 3 10" refX="2" refY="5" markerWidth="3" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M1.5 0V10" stroke="var(--muted)" stroke-width="2.2"/></marker>
</defs></svg>
{IA.element_card_js()}
<main class="post" id="top">
<header class="mast">
<p class="eyebrow"><span><span class="field">Cell and systems biology</span></span><span>October 2026</span></p>
<h1>Every line is a loop.<br>Let’s count them.</h1>
<p class="sub">A new periodic table for network biology</p>
<div class="meta"><span>Kat Titterton</span><span>Macrofluidics</span><span>%READTIME% min read</span><span>draft</span><nav class="links" aria-label="Code, data and supplement"><a href="{code_link}">code</a><a href="{data_link}">data</a><a href="#supplement">supplement</a></nav></div>
</header>
{hero_html}
<!--main-->
<div class="text">
<div class="abstract">
<p class="label">In short</p>
<p>Chemistry&#8217;s periodic table orders the elements, and its gaps once predicted new ones. This essay tries the same trick on the circuits that run a cell, counting their feedback loops instead of electrons, and tests the table on {census} published models. One band of the table turns out full and the other nearly empty, and the empty band is where to look next.</p>
</div>
</div>

<section id="intro">
<div class="text">
<p class="kicker"><span class="n">1</span>the puzzle</p>
<h2>Same parts, different machines</h2>
<p class="lede">In January 2000, <i>Nature</i> printed two synthetic circuits back to back. Elowitz and Leibler wired three repressors into a ring in <i>Escherichia coli</i>, the repressilator, and the cells oscillated with periods of hours {cite('elowitz')}. Gardner, Cantor and Collins wired two repressors to shut each other off, and their cells held either of two states until a brief pulse flipped them {cite('gardner')}. Same kind of parts, same bacterium. One circuit kept time; the other remembered. The difference was in how the arrows closed.</p>
<p>Chemistry met a puzzle like this in the 1860s: dozens of elements and no order. Mendeleev&#8217;s 1869 table gave them one, left gaps, and by 1871 had predicted the weight, density and oxide of one missing element. In 1875 gallium turned up to match, with scandium and germanium behind it {cite('scerri')}. Moseley pinned the order to X-ray spectra in 1913 {cite('moseley')}; electron shells explained the row lengths later. Order, then prediction, then explanation.</p>
<p>Could the circuits in a cell have a table like that? An earlier essay, <a href="every-line-is-a-loop.html">Every line is a loop</a>, proposes one built on three counts. This essay tests it: does the order hold, and do the gaps predict anything?</p>
</div>
</section>

<section id="theory">
<div class="text">
<p class="kicker"><span class="n">2</span>what a loop can do</p>
<h2>Flip the arrows and watch</h2>
<p>A <b>model</b> of a circuit is a set of equations: for each molecule, how fast it is made and removed. Draw an <b>arrow</b> from one molecule to another when the first changes how fast the second is made or removed. The arrow <b>amplifies</b> (+, drawn &#8594;) if more of the first means more of the second, and <b>brakes</b> (&#8722;, drawn &#8867;) if it means less. A <b>loop</b> is a path of arrows that comes back to where it began. A microphone pointed at its own speaker is an amplifying loop; a thermostat is a braking one. Biologists call them positive and negative feedback.</p>
<p>Now play. Flip the repressilator&#8217;s arrows below and count the brakes each time it ticks.</p>
</div>
<figure class="fig">
{IA.gauges()}
{IA.loop_toy()}
<figcaption><b>Figure 1. Arrows and loops.</b></figcaption>
</figure>
<div class="text">
<p>With one brake or three, it ticks. With none or two, it settles into one of two states: a switch. Signs multiply round a loop, so two brakes cancel like a double negative, and a loop brakes only when it holds an odd number of them. René Thomas proposed the rule decades ago, holding two states needs an amplifying loop and keeping a rhythm needs a braking one {cite('kaufman')}, and it is now a theorem {cite('soule', 'snoussi', 'gouze')}. The idea behind the proof is the one you just saw: to hold two states, a push must feed back on itself and grow; to keep swinging, something must eventually push back.</p>
<p>Cells build both kinds. The clock in your own cells is a braking loop: the proteins CLOCK and BMAL1 switch on the <i>Per</i> and <i>Cry</i> genes, the PER and CRY proteins build up, move into the nucleus and switch CLOCK and BMAL1 off, and the round trip takes about a day {cite('takahashi')}. The lac operon of <i>E. coli</i> is an amplifying loop made of two brakes: lactose disables the repressor LacI, LacI blocks the lac genes, and one of those genes makes the pump that brings lactose in. Two brakes cancel, and cells can hold either state, on or off {cite('ozbudak')}.</p>
<p>A loop can do a third thing. Drag the hill below and watch two cruise controls. One sags as the road steepens. The other gets back to 60, exactly, every time.</p>
</div>
<figure class="fig">
{IA.cruise()}
<figcaption><b>Figure 2. A running total on a hill.</b></figcaption>
</figure>
<div class="text">
<p>The one that recovers keeps a <b>running total</b> of its shortfall and pushes until the total stops growing. A molecule can do the same if its rate of change doesn&#8217;t depend on its own level, so it adds up what flows in and out. Put one inside a braking loop and a cell returns exactly to its set point after a push. Bacteria steer this way: the receptor that senses an attractant carries methyl groups, one enzyme adds them steadily and another, switched on by the receptor&#8217;s activity, removes them, so the methyl count is a running total and the cell returns exactly to its resting behaviour {cite('barkai', 'yi')}. Yeast handle salt the same way {cite('muzzey')}, and a running total can be built from two molecules that destroy each other {cite('briat')}.</p>
</div>
<figure class="fig">
{BF.fig_real_circuits()}
<figcaption><b>Figure 3. The three counts in real cells.</b></figcaption>
</figure>
<div class="text">
<p>So a circuit has three counts: how many loops, how many of them brake, and how many keep a running total. That is the whole idea of the table.</p>
</div>
</section>

<section id="table">
<div class="text">
<p class="kicker"><span class="n">3</span>the table</p>
<h2>Three counts make a periodic table</h2>
<p>Take a circuit with one loop. The loop brakes or it doesn&#8217;t; it keeps a running total or it doesn&#8217;t. That is 2 &#215; 2 = 4 kinds. With two loops, each count runs from 0 to 2: 3 &#215; 3 = 9. With three, 4 &#215; 4 = 16.</p>
<div class="grid-fig">{rows_grid()}</div>
<p>Each kind is an <b>element</b>. If 4, 9, 16 rings a bell, it is the number of orbitals in an atom&#8217;s second, third and fourth shells, and the match runs deeper. Sort a row by l = max(k, j), the larger of its two counts, and it splits into layers of 1, 3, 5 and 7, the sizes of the s, p, d and f subshells; inside a layer, m = k &#8722; j runs from &#8722;l to l, as the magnetic number does:</p>
<math display="block"><mrow><msup><mrow><mo>(</mo><mi>n</mi><mo>+</mo><mn>1</mn><mo>)</mo></mrow><mn>2</mn></msup><mo>=</mo><munderover><mo>&#8721;</mo><mrow><mi>l</mi><mo>=</mo><mn>0</mn></mrow><mi>n</mi></munderover><mo>(</mo><mn>2</mn><mi>l</mi><mo>+</mo><mn>1</mn><mo>)</mo></mrow></math>
<p>It is a counting identity, not physics, and it stops one step short: an atom&#8217;s shells hold twice as many electrons because each orbital takes two, and the earlier essay reads that missing factor as a missing binary, perhaps the order in which loops nest. Periodicity is itself a loop. The first periodic system wound the elements along a helix on a cylinder {cite('chancourtois')}, and drawn as spirals, one turn per row, both tables line their families up on rays.</p>
</div>
<figure class="fig">
{TF.fig_orbitals()}
{TF.fig_spirals()}
<figcaption><b>Figure 4. The same arithmetic as the atom.</b></figcaption>
</figure>
<div class="text">
<p>Others had sorted circuits by their loops before: oscillators {cite('novak')}, the named small circuits {cite('tyson')}, the wiring patterns that recur across organisms {cite('milo', 'alon')}. The table puts the three counts together, much as Ahnert and colleagues built a periodic table for protein complexes {cite('ahnert')}. Here it is. Tap an element to read it.</p>
</div>
<figure class="fig">
{ptable_html}
<figcaption><b>Figure 5. The periodic table of loops.</b></figcaption>
</figure>
<div class="text">
<p>If this is a real periodic table, three things should be true: circuits with a given number of loops do no more kinds of things than their row has elements; no circuit does what its loops forbid, no switch without an amplifying loop and no clock without a brake; and every element can be built, so each blank is a prediction. The second is the theorem above; the other two are open. To test them, count real circuits.</p>
</div>
</section>

<section id="data">
<div class="text">
<p class="kicker"><span class="n">4</span>the census</p>
<h2>Counting real circuits</h2>
<p><b>BioModels</b> is a public library of the mathematical models behind published papers, founded in 2005 {cite('biomodels')}, each one checked against its paper and stored in a standard format {cite('lenovere', 'hucka')}: the cell cycle, the fruit fly&#8217;s day clock, calcium spikes and more. The census took the {census} models of the 2017 release, the one Baudier, Fages and Soliman analysed, so the counts can be compared {cite('baudier')}. It drew each model&#8217;s arrows, listed its loops, dropped the ones chemistry makes for free (<a href="#supp-b">Supplement B</a>), and placed each circuit on the table. Click a step for what it kept and why, then search the models yourself.</p>
</div>
<figure class="fig">
{funnel_html}
{explorer_html}
<figcaption><b>Figure 6. The data.</b></figcaption>
</figure>
</section>

<section id="results">
<div class="text">
<p class="kicker"><span class="n">5</span>what the table says</p>
<h2>One band full, one band empty</h2>
<p>Of the {usable} models the census could read, {small} have one to three loops, few enough to place.</p>
<p>They fall in one band. Every element without a running total is filled, all {found_top[1]} of them, and familiar circuits sit where their biology puts them: the repressilator under one brake, the trp operon under two. Of the {found_rest[1]} elements with a running total, {found_rest[0]} are filled, by {rest_models} models between them. The table is fullest where biology already had words for what it saw, switches and clocks, and emptiest where the words arrived last.</p>
<p>The three tests are scored below; the weak one is the third: no reading of the equations finds the running total cleanly, not even in yeast, where experiments pinned it down {cite('muzzey')}.</p>
<p>One surprise. The fruit fly&#8217;s day clock has {WORD[len(FLY_CLOCK)]} curated models, all built from the same proteins, and they land in {WORD[fly_places]} different places, from {WORD.get(fp_min, fp_min)} to {WORD.get(fp_max, fp_max)} loops. Measure a coastline with a shorter ruler and it gets longer; a loop count grows the same way as a model gains detail (<a href="#supp-c">Supplement C</a>).</p>
</div>
<div class="summary-cards">
{scorecard}
</div>
</section>

<section id="gaps">
<div class="text">
<p class="kicker"><span class="n">6</span>the empty band</p>
<h2>What the gaps say</h2>
<p>Mendeleev&#8217;s gaps came with predictions, and so do these. Element {sw_num} ({sw_sym}) is a switch that keeps a running total. It should add up a signal and commit once the total is high enough: a switch that flips on how long something lasted rather than how strong it was. It is this table&#8217;s eka-aluminium, and nothing in the census sits there yet.</p>
<p>Why is the band empty? Three readings, each with its own test.</p>
<ul>
<li><b>Hidden.</b> The strict and the loose reading disagree across most of the band, and the circuits where experiments found a running total, chemotaxis and yeast osmotic stress {cite('yi', 'muzzey')}, are too tangled for this census to place; if so, better readings, tested on models with known answers, will fill the band.</li>
<li><b>Unmodelled.</b> Running totals entered the field&#8217;s vocabulary in 2000 {cite('yi')} and were built as synthetic parts by 2019 {cite('briat', 'aoki')}, while the release counted here dates from 2017; if so, newer releases will fill the band.</li>
<li><b>Rare.</b> An exact running total needs special chemistry, such as two molecules that destroy each other {cite('briat')}, so cells may keep theirs inside larger networks; if so, computer-built circuits will find these elements working {cite('ma')} while models of real cells keep them rare.</li>
</ul>
<p>What does an empty band say about the hypothesis itself? That the table is two thirds proven and one third promised. Loops and brakes are real axes: circuits spread across every combination of them. Running totals are, so far, an axis with almost no one on it. Mendeleev&#8217;s table carried predictions that never came true as well {cite('scerri')}, and if this band stays empty after better readings and newer releases, the honest move is his: retire the axis, and each row shrinks from (loops + 1)<sup>2</sup> elements to loops + 1, which is 2, 3 and 4. If the band fills, the square count stands. Either outcome is a result.</p>
<p>The census can&#8217;t yet tell these apart. Where else to look: <a href="https://cellcollective.org">Cell Collective</a>, the <a href="https://models.physiomeproject.org">Physiome Model Repository</a>, and decisions that hinge on how long a signal lasts, where {sw_sym} should live.</p>
</div>
</section>

<section id="next">
<div class="text">
<p class="kicker"><span class="n">7</span>next()</p>
<h2>Science is a loop: what comes next?</h2>
<p>The census can&#8217;t falsify the count itself, any more than a die can roll a seven; what it can do is close one turn of the research loop. Click a stage to see this round and the next.</p>
</div>
<figure class="fig">
{science_html}
<figcaption><b>Figure 7. The research loop.</b></figcaption>
</figure>
<div class="text">
<p>Proton number doesn&#8217;t depend on how you draw an atom; loop number depends on how you draw a circuit. If a count on a reduced model holds still, the {WORD[len(FLY_CLOCK)]} fly-clock models should land in one element. Then the first claim gets its test, every small circuit built on a computer and run across its rates {cite('ma', 'li')}, and the blanks become predictions: the running-total circuit built in bacteria in 2019 {cite('briat', 'aoki', 'lillacci')} belongs in element {ad_num}, the adapter ({ad_sym}).</p>
<p>Chemistry&#8217;s table went on to predict materials and medicines: eka-silicon became germanium and the first transistor {cite('bardeen')}; element 43 was made before it was found {cite('perrier')}. For cells, the same three gifts. For the field, a shared address: a model says which element it is, a reader asks whether its behaviour matches, and circuits built from different molecules in different organisms can turn out to be the same element, as the fly&#8217;s clock and ours are at their coarsest drawing, one braking loop through transcription.</p>
<p>For medicine, a diagnosis by element. The earlier essay reads three diseases as one algebra: a tumour as a brake lost, an autoimmune disease as a brake missing, a prion-like disease as an amplifying loop with no brake at all. The table turns that into a target, which loop to put back rather than which molecule to hit, and the clinic already has cases. Restore p53, a brake, and established tumours in mice regress {cite('ventura', 'xue')}. Remove a brake on T cells, as checkpoint blockade does, and they attack tumours and the body alike {cite('postow')}: the price the table puts on a lost brake. An element also says what to measure in a patient: a clock by its period, a switch by its threshold, a running total by its drift.</p>
<p>For technology, design by position, as a chemist who needs a reactive metal looks in the first column. A sensor that must reset exactly comes from {ad_sym}, where the circuit built in bacteria is the first part in the box and the closed-loop insulin pump is the same element built outside the cell. A timer that commits after a dose comes from {sw_sym}, which nobody has built. Wire a toggle switch to a running total and drive it with pulses of different lengths; if it flips on the total rather than the peak, {sw_sym} is made before it is found.</p>
</div>
</section>

<section id="limits">
<div class="text">
<p class="kicker"><span class="n">8</span>limits</p>
<h2>What this census can&#8217;t tell you</h2>
<ul class="limits">
<li>Behaviour was read at published parameters from {WORD[starts]} starts, so the census undercounts kinds of behaviour.</li>
<li>The loop filters are proved for amplifying loops only; applied to braking loops, they remove the brakes of {dep} clocks.</li>
<li>Loops written as formulas rather than reactions are invisible to it ({no_arrows} models), and {unfinished} loop searches stopped at their step limit.</li>
<li>BioModels holds what people chose to model and publish, not a random sample of biology.</li>
</ul>
</div>
</section>

<section id="close">
<div class="text">
<p class="kicker"><span class="n">9</span>return</p>
<h2>So, do real circuits fit?</h2>
<p>As far as this census can see, mostly. Go back to January 2000: one sign separated the clock from the switch, and that sign is what the table counts. None of the {autonomous} models that run without outside input broke the rules behind it; what&#8217;s left is an empty band where running totals should be, and a clock that moves when you redraw it. Chemistry&#8217;s table earned its keep when gallium turned up as predicted. This table&#8217;s gallium is still out there: a switch that keeps a running total, somewhere a cell has to decide how long a signal has lasted.</p>
<p>All of it is open: the code, the data and the supplements live in one repository, and <code>sh analysis/run_all.sh 8</code> rebuilds every number on this page from the raw download in {runtime} on a laptop.{repo_line} Change a definition, rerun, and see where your favourite circuit lands.</p>
<p class="coda">Every line is a loop. Let&#8217;s keep counting.</p>
</div>
</section>
<!--/main-->

<section id="supplement">
<div class="text">
<p class="kicker"><span class="n">S</span>supplement</p>
<h2>Want more depth?</h2>
<p>Four supplements and the references hold the rest of the evidence, with every figure and equation. Open any of them.</p>
</div>

<details class="supp" id="supp-a">
<summary>A. The elements as tiles</summary>
<figure class="fig">
{TF.fig_tiles()}
<figcaption><b>Figure S1. Element tiles.</b> Number, counts, name and period range, beside carbon. Examples are the earlier essay&#8217;s.</figcaption>
</figure>
</details>

<details class="supp" id="supp-b">
<summary>B. How the census works and how it was checked</summary>
<figure class="fig">
{SF.fig_model()}
<figcaption><b>Figure S4. From circuit to model.</b> The repressilator as a circuit, a diagram, equations and a run.</figcaption>
</figure>
<div class="text">
<p>Chemistry makes loops that regulate nothing. Binding and unbinding go out and back, like a two-way street, not round, like a roundabout. The filters of Baudier, Fages and Soliman {cite('baudier')}, built on Soliman’s condition {cite('soliman')}, remove them. They proved that dropping these loops loses no amplifying loop that could hold two states; the proof covers amplifying loops only (<a href="#supp-d">Supplement D</a>).</p>
</div>
<figure class="fig">
{SF.fig_street()}
{fig_method(toys)}
<figcaption><b>Figure S5. Out and back is not a loop.</b> The enzyme’s loops all come from binding and release, and none survives the filters; the repressilator’s ring does. The census code counts both panels.</figcaption>
</figure>
<figure class="fig">
{fig_pipeline(struct, dyn, starts)}
<figcaption><b>Figure S6. One model through the census.</b> Code lines are trimmed from loops.py and dynamics.py; simulation uses libRoadRunner {cite('roadrunner')}.</figcaption>
</figure>
<div class="text">
<p><b>Validation.</b> Toy models with known answers are counted on every build, and Tyson, Chen and Novák’s seven textbook circuits {cite('tyson')} serve as an answer key. On the same release, Baudier, Fages and Soliman found no braking loop in {pct(r24['no negative circuit'], r24['models'])} of models; this census finds none in {pct(rep['no negative circuit'], rep['models'])}. An audit of the first full run found a backtracking bug that cost 42 of 106 rate-rule models some loops, and after the fix the small-model count fell from 179 to {small}. Two independent runs from the raw download produce identical files.</p>
</div>
<figure class="fig">
{key_table}
<figcaption><b>Figure S7. Answer key.</b> The census reads {WORD[key_agree]} of seven as named (✗ marks the misses); at published settings only the switch shows its textbook behaviour.</figcaption>
</figure>
</details>

<details class="supp" id="supp-c">
<summary>C. More results: loop counts, behaviour, detail</summary>
<figure class="fig bars">
{fig_distribution(D['distribution'])}
<figcaption><b>Figure S8. Loops per model.</b> {le3} of {usable} have three loops or fewer; for {unfinished} the search stopped at its step limit.</figcaption>
</figure>
<figure class="fig">
<div class="scroll wide fig-wide">
{fig_behaviour(behav, depletion)}
</div>
<div class="fig-narrow">
{fig_behaviour(behav, depletion, narrow=True)}
</div>
<figcaption><b>Figure S9. Behaviour by sign pattern.</b> Outlined cells are forbidden by the proven rules. The only models inside them are the {dep} dashed clocks, {dep_kinds}, whose brake the filters remove.</figcaption>
</figure>
<div class="text">
<p>Sorted by six behaviours and their mixtures, one loop gives {fine[1]} kinds, two loops {fine[2]} and three loops {fine[3]}; merged into four behaviours, {coarse[1]}, {coarse[2]} and {coarse[3]}. {test_verdict} The fruit fly’s clock models: {fly_txt}. The paired running-total reading finds {WORD.get(len(pt['models with one']), len(pt['models with one']))} models with a total kept by two molecules; one, a folate pathway, has it on a loop.</p>
</div>
<figure class="fig">
{coast_html}
<figcaption><b>Figure S10. The coastline problem.</b> Drag the ruler: the measured length keeps growing, as a loop count does with model detail.</figcaption>
</figure>
</details>

<details class="supp" id="supp-d">
<summary>D. Methods: every step, setting and equation</summary>
<div class="text" id="methods">
<p>Every step is a script in the <code>analysis</code> folder beside this page, and every setting that can move a number is given here. The data flow top to bottom:</p>
</div>
<figure class="fig">
{pipeline_html}
<figcaption><b>Figure S11. The data pipeline.</b> One script per step; the last line of each step is what comes out.</figcaption>
</figure>
<div class="text">
<h3>Models into equations</h3>
<p>BioModels release 31 (26 June 2017) holds {census} curated models, the set Baudier, Fages and Soliman used {cite('baudier')}. Each is read with libSBML {cite('libsbml')}, with function definitions expanded, and compiled by libRoadRunner {cite('roadrunner')}. The variables x are the species that change and are not fixed by an assignment rule, plus any quantity with a rate rule. With v(x) the reaction rates and N the stoichiometry matrix, whose entry N<sub>kj</sub> is how many of molecule k reaction j makes (positive) or uses up (negative), each model is</p>
{PM.ODE}
<p>plus the right-hand sides of its rate rules. {usable} models could be read this way. Of the other {census - usable}, {excl_txt}, among them Tyson&#8217;s mutual-inhibition switch, whose loop is hidden inside a formula.</p>

<h3>Arrows</h3>
<p>An arrow runs from molecule i to molecule k through reaction j when reaction j changes k and its rate depends on i. Its sign multiplies two signs: whether the rate rises or falls with i, and whether the reaction makes or uses up k.</p>
{PM.SIGN}
<p>The derivative is a central difference, with step h equal to a tenth of a percent of x<sub>i</sub>:</p>
{PM.FD}
<p>A difference smaller than 10<sup>&#8722;13</sup> of the two rates counts as zero. Signs are read at five states of the model&#8217;s own run, t = 0, 1, 10, 100 and 1000, each reached from a fresh reset, so events and the clock apply only where they belong and one failed run loses one state, not all. A species sitting at exactly zero is lifted to 10<sup>&#8722;6</sup> of the median level so its arrows can be read. An arrow seen at any of the five states counts, so one arrow can carry both signs. Rate rules give arrows the same way, from the derivative of their right-hand side.</p>
<p>Self-loops need care, because every molecule that decays has a trivial braking loop on itself. Decay, consumption and reverse flux are not counted. A braking self-loop is kept only when a reaction that makes the molecule slows as it rises, and its rate law stays non-negative when the molecule is pushed a thousand times higher (end-product inhibition, autorepression); a symbolic test with sympy looks for a positive root of the rate law&#8217;s numerator. An amplifying self-loop is dropped when it only comes from a substrate written as a total minus the molecule itself.</p>
<p>As a check, signs were also read at random states, each variable drawn log-uniformly between the lowest and highest levels it reaches on its own run to t = 1000.{rob}</p>

<h3>Loops</h3>
<p>A loop is an elementary circuit of the arrow graph, with each arc labelled by its reaction. Its sign is the product of its arcs&#8217; signs, so it brakes when it holds an odd number of brakes:</p>
{PM.LOOP}
<p>Baudier, Fages and Soliman proved that three kinds of loop can be dropped without losing any amplifying loop that could hold two states {cite('baudier')}. The proofs run through the Jacobian; in plain terms, with the intuition for each:</p>
<ul>
<li>A loop that uses two arrows from the same reaction, or from reactions that are the same up to a positive factor (stoichiometry columns that are positive multiples of each other). One reaction cannot amplify itself.</li>
<li>A loop that uses a reaction and its reverse (columns that are negative multiples). Out and back is not a loop.</li>
<li>A loop whose molecules make up a whole conserved pool, a weighting p &#8805; 0 with p<sup>T</sup>N = 0 that no reaction changes. Moving material round a closed pool pushes nothing.</li>
</ul>
<p>The proofs cover amplifying loops only. There is no matching theorem for braking loops, so applying the filters to them is a choice, and the alternative split below counts braking loops as drawn. A fourth test, the rank condition from the same paper, keeps a loop only if its reactions are independent, so that their stoichiometry columns cannot be combined to cancel; it drops cycles that just move material round:</p>
{PM.RANK}
<p>Loops are listed by depth-first search from each molecule s through higher-numbered molecules in s&#8217;s strongly connected component, refusing an arc the moment it would break a filter. A search stops after 5,000,000 steps or 20,000 loops, and the model then counts as &#8220;search unfinished&#8221;. Counting steps instead of seconds is what makes reruns identical. Whether any amplifying loop survives the filters is decided separately by their vertex-elimination algorithm, which finishes even when listing doesn&#8217;t.</p>
<p>Each model gets three counts: c loops, k of them braking, j of them through a running total. The essay counts independent loops instead, the cyclomatic number of the union of all loops,</p>
{PM.CYC}
<p>with E arrows, V molecules and C connected pieces. It differs from c in {nud} of the {small} small models. Sontag&#8217;s distance to positive feedback {cite('sontag')}, the fewest sign flips that make every loop amplifying, gives a braking count that doesn&#8217;t depend on which loops are listed. Computed on the filtered loops, it differs from k in {kpf} of the {small}.</p>
<div class="scroll"><table><tr><th>Loops counted</th><th>one</th><th>two</th><th>three</th></tr>{def_rows}</table></div>

<h3>Running totals</h3>
<p>Strict reading. Molecule i keeps a running total if its own name appears in none of the rate laws that change it, so its rate cannot depend on its level:</p>
{PM.STRICT}
<p>Loose reading. Molecule i nearly keeps one if its own level moves its net rate by less than a tenth of the flow into it, at the last state reached (first-order decay scores exactly 1 at steady state):</p>
{PM.LOOSE}
{PM.FLUX}
<p>Paired reading. Two molecules a and b keep one together if a weighted sum z of them changes at a rate that depends on neither, nor on any molecule P that shares a conserved total with them, but does depend on something else:</p>
{PM.PAIR}
<p>A paired running total is two molecules whose weighted sum changes at a rate that depends on neither of them. The code screens for candidates numerically, then confirms each one exactly from the rate laws. Candidates come from the Jacobian J = N &#8706;v/&#8706;x at the five states. The block J[S, S &#8746; P] for S = &#123;a, b&#125;, stacked across states, must have rank one (smallest singular value under 10<sup>&#8722;4</sup> of the largest, rows normalised). Sums equal to one molecule plus a constant once conserved totals are used are dropped. Each survivor is then confirmed from the rate laws: the weights are rounded to a ratio of whole numbers up to 12, sympy differentiates the weighted rate exactly, and the derivative must cancel to 10<sup>&#8722;9</sup> at four random states spread over six orders of magnitude, with parameters at the model&#8217;s values. {unchecked} candidates whose rate laws use conditional formulas could not be confirmed and are left out.</p>
<p>The readings were checked on models where the answer is known:</p>
<div class="scroll"><table><tr><th>Model</th><th>Loops</th><th>Strict</th><th>Loose</th></tr>{ctl_rows}</table></div>
<p>The paired reading finds none in these six, finds the controller&#8217;s total in the toy, and finds nothing in the enzyme or the ring.</p>

<h3>Behaviour</h3>
<p>Each model runs at its published rates from its own start and {WORD[starts - 1]} others. The others keep every conserved total of the start: they are corners of the set of states x &#8805; 0 reachable as x<sub>0</sub> + N&#958; and capped at ten times the largest starting level, found by linear programs with random objectives, then mixed with Dirichlet(0.3) weights. The solver is CVODE {cite('sundials')} with relative tolerance 10<sup>&#8722;8</sup> and absolute tolerance 10<sup>&#8722;12</sup>. Each run tries horizons of 10<sup>2</sup>, 10<sup>3</sup>, 10<sup>4</sup> and 10<sup>5</sup> time units, 2,001 samples each, and stops at the first that decides:</p>
<div class="scroll"><table>
<tr><th>Label</th><th>Rule</th></tr>
<tr><td>settles</td><td>over the last fifth of the run every variable moves by less than 10<sup>&#8722;5</sup> of its level</td></tr>
<tr><td>rings, then settles</td><td>settles after crossing its final value at least twice, by more than 10<sup>&#8722;3</sup> of it</td></tr>
<tr><td>keeps time</td><td>in the second half, at least three peaks, a relative swing above 10<sup>&#8722;3</sup>, the last peak at least 0.9 of the first, and still at least 0.8 of that swing over a further 2T</td></tr>
<tr><td>holds two states</td><td>runs settle in two or more states more than 1% apart, but no more than a third as many states as runs, and no state has a zero eigenvalue in the Jacobian restricted to its conserved totals</td></tr>
<tr><td>settles anywhere</td><td>end states that differ but have a zero eigenvalue, or are too many to be a few separate states: a line of resting states</td></tr>
<tr><td>grows without limit</td><td>a variable passes 10<sup>6</sup> times its starting scale, or is still climbing at the last horizon</td></tr>
<tr><td>driven from outside</td><td>the model has events, or time appears in a rate law, rule or function; set aside ({th['forced models excluded']} models)</td></tr>
</table></div>
<p>{autonomous} models run on their own; {unsettled} small models never settle under these rules. Finding two states from {WORD[starts]} starts at one setting of the rates is a lower bound.</p>

<h3>The proven rules</h3>
<p>Two of the table&#8217;s rules are theorems, so the census uses them to check itself.</p>
<p><b>Two states need an amplifying loop.</b> Soul&#233; proved it {cite('soule')}: if a system of smooth rate equations has two separate steady states, then at some state in between, the arrows the census draws (the signed Jacobian) contain an amplifying loop. The idea, roughly: between two stable states lies an unstable one, a hilltop, and a hilltop needs a disturbance that feeds back on itself and grows, which is an amplifying loop. Baudier, Fages and Soliman sharpened the statement for reaction networks: the loop can be taken to be one that survives their filters {cite('baudier')}. The census checks this with their elimination algorithm, which decides whether such a loop exists without listing loops.</p>
<p><b>A sustained rhythm needs a braking loop.</b> Snoussi and Gouz&#233; proved that a stable oscillation needs a braking loop through at least two molecules {cite('snoussi', 'gouze')}. The idea: to swing, a system must overshoot and turn back, and turning back means some chain of arrows eventually pushes the other way, which multiplies to a brake. The census checks it exactly: a strongly connected piece of the graph has no braking loop just when its molecules split into two camps so that every arrow&#8217;s sign is the product of its ends&#8217; camps,</p>
{PM.BALANCE}
<p>which a single pass of two-colouring decides. Braking self-loops are left out of this check, as the theorem requires.</p>
<p>What the theorems do not say: they are necessary conditions, not sufficient ones. An amplifying loop does not guarantee two states, and a braking loop does not guarantee a rhythm. They also speak of the signs at some state of the system, which is why the census reads signs where each model actually runs, and again at random states as a check.</p>

<h3>Counting elements</h3>
<p>A model with c = &#957; loops goes in element (&#957;, k, j), and row &#957; has (&#957; + 1)<sup>2</sup> elements. Grouping them like orbitals gives each one an address, with layers of 2l + 1:</p>
{PM.QN}
{PM.KINDS}
<p> Two other counts treat each loop as carrying its own type. If every loop is one of four types (amplifying or braking, with or without a running total), a row is a multiset of &#957; types: 4, 10 and 20 elements, of which the models fill {t4[2]['occupied']} at two loops and {t4[3]['occupied']} at three. If only braking loops can keep a running total, three types give 3, 6 and 10 elements, of which they fill {t3[2]['occupied']} and {t3[3]['occupied']}. Counting amplifying loops after the filters and braking loops as drawn, the split the proofs support, moves {sp['moved']} models to another cell{'; every sign pattern stays filled' if split_full else ''}{', and no clock is left without a brake' if not sp['clocks without a brake'] else ''}. Kinds of behaviour are the distinct sets of labels among the models of a row that run on their own.</p>

<h3>Replication</h3>
<p>Baudier, Fages and Soliman ran the same three filters on the same release:</p>
<div class="scroll"><table><tr><th></th><th>Baudier, Fages and Soliman, Table 1: {r24['models']} models</th><th>This census: {rep['models']} models with reactions</th></tr>
<tr><td>No braking loop</td><td>{pct(r24['no negative circuit'], r24['models'])}</td><td>{pct(rep['no negative circuit'], rep['models'])}</td></tr>
<tr><td>No amplifying loop</td><td>{pct(r24['no positive circuit'], r24['models'])}</td><td>{pct(rep['no positive circuit'], rep['models'])}</td></tr>
<tr><td>No amplifying loop after the filters</td><td>{pct(r24['no refined positive circuit'], r24['models'])}</td><td>{pct(rep['no refined positive circuit'], rep['models'])}</td></tr>
</table></div>
<p>Amplifying loops differ in a direction sign reading can&#8217;t explain, because reading every setting at once, as they did, can only add arrows. The gap more likely comes from how each pipeline turns a model file into reactions; theirs rebuilds some models from their equations. Their headline, 160 of 506, adds a rewiring test not run here. Their case study, the ERK cascade of model 270, comes out as they found it: {m270['c']} loops survive the filters, all braking, so it cannot hold two states.</p>

<h3>Reproducing it</h3>
<div class="scroll"><table>
<tr><th>Setting</th><th>Value</th></tr>
<tr><td>Data</td><td>BioModels release 31, 193 MB, SHA-256 b6fba03e&#8230;0532, checked on download</td></tr>
<tr><td>Software</td><td>Python 3.9.6, libRoadRunner 2.7.0, python-libsbml 5.20.4, numpy 1.26.4, scipy 1.13.1, sympy 1.14.0 (all pinned in requirements.txt)</td></tr>
<tr><td>Randomness</td><td>every draw seeded; parallel jobs write results in model order</td></tr>
<tr><td>Loop search</td><td>5,000,000 steps or 20,000 loops per model; elimination capped at 300,000 arcs</td></tr>
<tr><td>Time limits</td><td>1,200 s per model for loops, 900 s for behaviour, 240 s for running totals</td></tr>
<tr><td>Threads</td><td>one per job (OMP_NUM_THREADS=1), so parallel jobs don&#8217;t fight over the CPU</td></tr>
<tr><td>Run time</td><td>{runtime} with 8 jobs on a 10-core laptop</td></tr>
</table></div>
<p>Two full runs from the raw download, in separate folders, gave identical files apart from the recorded timings. <code>build_post.py</code> writes this page from the results and refuses to build if a sentence no longer matches the data.</p>
</div>
</details>

<details class="supp" id="refs-d">
<summary>References, {len(REFS)}</summary>
<div class="text">
<ol class="refs">%REFS%</ol>
</div>
</details>
</section>

<footer class="end"><p class="meta"><a href="{REPO_URL}/issues">comment on GitHub</a><a href="#top">back to top</a></p></footer>
{REF_POPOVER_JS}
</main>
</body>
</html>
'''
    main_txt = page.split('<!--main-->')[1].split('<!--/main-->')[0]
    main_txt = re.sub(r'<figure\b.*?(<figcaption.*?</figcaption>).*?</figure>', r'\1', main_txt, flags=re.S)  # a figure counts as its caption
    main_txt = re.sub(r'<(script|style|svg|math).*?</\1>', ' ', main_txt, flags=re.S)
    main_words = len(re.sub(r'<[^>]+>', ' ', main_txt).split())
    page = page.replace('%READTIME%', str(max(1, round(main_words / 230))))
    page = number_refs(page)
    dashes = page.count('—') + page.count('&#8212;') + page.count('&mdash;')
    print('em dashes', dashes, '(a voice when sparing, a habit when frequent)')
    pathlib.Path(out_path).write_text(page, encoding='utf-8')
    return out_path


if __name__ == '__main__':
    print(build(R / 'tables_traj.json', R / 'tables_random.json', R / 'toys.json', R / 'r31_structure_traj.jsonl', R / 'r31_dynamics.jsonl',
                ROOT / 'count-the-elements.html'))
