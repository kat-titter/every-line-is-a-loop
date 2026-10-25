"""What each element of the loop table does: names, behaviour, examples and, for blanks, predictions.

An element is (n, k, j): n feedback loops, k of them braking, j of them through a running total.
Discovered elements take their name and examples from the essay's example key (every-line-is-a-loop.html).
Blanks are predicted the way Mendeleev predicted gallium, from their neighbours: an element behaves like its
parent without running totals, (n, k, 0), changed by what a running total does on the kind of loop it sits on.

  On a braking loop, a running total makes the loop return exactly to its set point after a change
  (integral feedback; Yi et al. 2000, Briat et al. 2016). This is established.
  On an amplifying loop, a running total adds up the input until the loop commits. This is a hypothesis.

The table does not say which loops carry the running totals. At least j - (n - k) of them must sit on braking
loops and at least j - k on amplifying loops; when neither bound bites, the element could do either.
"""

# parent elements (no running total): name, short tile label, what it does, behaviour trace
PARENT = {
    (0, 0): ('counter', 'counter', 'No feedback: a line that adds up or runs down, with nothing to stop it.', 'counts'),
    (1, 0): ('switch', 'switch', 'Holds one of two states; a strong enough pulse flips it.', 'holds two states'),
    (1, 1): ('clock', 'clock', 'Keeps time, or holds a level steady.', 'keeps time'),
    (2, 0): ('memory', 'memory', 'Holds one of several states and keeps it.', 'holds two states'),
    (2, 1): ('relaxation oscillator', 'oscillator', 'Builds up, fires and resets: a spike or a beat.', 'fires and resets'),
    (2, 2): ('coupled clocks', 'two clocks', 'Two rhythms that pull on each other.', 'keeps time'),
    (3, 0): ('multistate memory', 'fates', 'Holds one of many stable states, like a cell fate.', 'holds two states'),
    (3, 1): ('working memory', 'working', 'Holds a state for a while, then lets it go.', 'holds, then fades'),
    (3, 2): ('circadian', 'circadian', 'Keeps a steady, long rhythm, like the day clock.', 'keeps time'),
    (3, 3): ('clock, no memory', 'pulses', 'Rhythm with nothing to hold a state: pulses that reset.', 'keeps time'),
}
ADAPTER = ('adapter', 'adapter', 'Responds to a change, then returns exactly to where it was.', 'adapts exactly')

# A shorthand, as chemistry has Na and Fe: two letters for each named element. Elements not yet named take their
# parent's symbol plus an integral sign per running total (Sw∫, Ro∫²), the way chemistry gives undiscovered elements
# systematic names until they are confirmed.
# Each symbol is unique, and none reuses a chemical element's symbol or a code from the essay's example key.
SYMBOL = {(0, 0): 'Ct', (1, 0): 'Sw', (1, 1): 'Tk', (2, 0): 'Me', (2, 1): 'Ro', (2, 2): 'Tw',
          (3, 0): 'Mm', (3, 1): 'Wm', (3, 2): 'Ci', (3, 3): 'Ps'}
CHEMICAL = set('''H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr
Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb
Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og'''.split())
ESSAY_CODES = set('Am Df Dv Ag Ev Al Rs Ck Lc Lh Ch Hg Gl Hs Kc Pc Ap Cc Sg Pl Eg Cr Nf'.split())


def symbol(n, k, j):
    """(plain text, html) of the element's symbol."""
    if (n, k, j) == (1, 1, 1):
        return 'Ad', 'Ad'
    base = SYMBOL[(n, k)]
    if j == 0:
        return base, base
    sup = {2: '\u00b2', 3: '\u00b3'}.get(j, '')
    sup_html = f'<sup>{j}</sup>' if j > 1 else ''
    return base + '\u222b' + sup, f'{base}<span class="sy-i">\u222b{sup_html}</span>'

# the essay's example key, by element (n, k, j); names as the essay gives them
ESSAY_EXAMPLES = {
    (0, 0, 0): ['amyloid growth', 'differentiation', 'development', 'aging', 'evolution'],
    (1, 0, 0): ['allosteric flip', 'riboswitch', 'CaMKII autophosphorylation', 'lac operon bistability', 'LH surge'],
    (1, 1, 1): ['chemotaxis adaptation', 'Hog1 osmoadaptation'],
    (1, 1, 0): ['glucose homeostasis', 'Hes1 and p53–Mdm2 oscillations', 'KaiABC'],
    (2, 0, 0): ['Polycomb read–write memory'],
    (2, 1, 0): ['action potential, pacemaker', 'cell cycle'],
    (2, 2, 0): ['segmentation clock'],
    (3, 0, 0): ['pluripotency core (OCT4, SOX2, NANOG)'],
    (3, 1, 0): ['EGFR and its phosphatases'],
    (3, 2, 0): ['circadian clock'],
    (3, 3, 0): ['NF-κB with IκBα, IκBε and A20'],
}

ADAPT = 'brings it back exactly after a change'
ACCUM = 'adds up its input and commits once the total is high enough'
LOOK_ADAPT = 'sensing and homeostasis, where cells return exactly to a set point: chemotaxis, osmotic stress, synthetic integral controllers'
LOOK_ACCUM = 'decisions that depend on how long or how strongly a signal lasts, such as commitment points in the cell cycle and in cell fate'


def describe(n, k, j):
    """name, short label, what it does, traces (defining behaviour first), predicted?, where to look"""
    if (n, k, j) == (1, 1, 1):
        name, short, does, trace = ADAPTER
        return {'name': name, 'short': short, 'does': does, 'traces': [trace], 'predicted': False, 'look': LOOK_ADAPT}
    name, short, does, trace = PARENT[(n, k)]
    if j == 0:
        return {'name': name, 'short': short, 'does': does, 'traces': [trace], 'predicted': False, 'look': ''}
    must_adapt, must_accum = j > n - k, j > k
    many = '' if j == 1 else f', {j} running totals'
    if must_adapt and not must_accum:
        return {'name': f'adapting {name}{many}', 'short': 'adapts', 'does': f'{does} Its running total {ADAPT}.',
                'traces': [trace, 'adapts exactly'], 'predicted': True, 'look': LOOK_ADAPT}
    if must_accum and not must_adapt:
        return {'name': f'accumulating {name}{many}', 'short': 'adds up', 'does': f'{does} Its running total {ACCUM}.',
                'traces': [trace, 'adds up, commits'], 'predicted': True, 'look': LOOK_ACCUM}
    if must_adapt and must_accum:
        return {'name': f'adapting, accumulating {name}{many}', 'short': 'both', 'does': f'{does} One running total {ADAPT}; another {ACCUM}.',
                'traces': [trace, 'adapts exactly', 'adds up, commits'], 'predicted': True, 'look': f'{LOOK_ADAPT}; and {LOOK_ACCUM}'}
    return {'name': f'{name} with {"a running total" if j == 1 else f"{j} running totals"}', 'short': 'totals',
            'does': f'{does} On a braking loop its running total {ADAPT}; on an amplifying loop it {ACCUM}.',
            'traces': [trace, 'adapts exactly', 'adds up, commits'], 'predicted': True, 'look': f'{LOOK_ADAPT}; or {LOOK_ACCUM}'}


def check_unique(elements):
    """Every element's symbol and name are its own; base symbols avoid chemistry's and the essay's codes."""
    syms = [symbol(*e)[0] for e in elements]
    names = [describe(*e)['name'] for e in elements]
    assert len(set(syms)) == len(syms), sorted(x for x in syms if syms.count(x) > 1)
    assert len(set(names)) == len(names), sorted(x for x in names if names.count(x) > 1)
    bases = set(SYMBOL.values()) | {'Ad'}
    assert not bases & CHEMICAL, bases & CHEMICAL
    assert not bases & ESSAY_CODES, bases & ESSAY_CODES
    return syms, names
