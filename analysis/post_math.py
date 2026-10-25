"""MathML for the methods of count-the-elements.html (MathML Core, rendered by current browsers)."""


def m(inner, block=True):
    return ('<math display="block">' if block else '<math>') + inner + '</math>'


def frac(a, b):
    return f'<mfrac><mrow>{a}</mrow><mrow>{b}</mrow></mfrac>'


def sub(a, b):
    return f'<msub><mi>{a}</mi><mrow>{b}</mrow></msub>'


D = '<mo>&#8706;</mo>'
MI = lambda s: f'<mi>{s}</mi>'
MO = lambda s: f'<mo>{s}</mo>'
MN = lambda s: f'<mn>{s}</mn>'
SP = '<mspace width="0.8em"></mspace>'

ODE = m(frac('<mi>d</mi><mi>x</mi>', '<mi>d</mi><mi>t</mi>') + MO('=') + MI('N') + MI('v') + MO('(') + MI('x') + MO(')'))
SIGN = m('<msubsup><mi>&#963;</mi><mrow><mi>i</mi><mi>k</mi></mrow><mrow><mo>(</mo><mi>j</mi><mo>)</mo></mrow></msubsup>' + MO('=') + MI('sgn') + MO('(')
         + frac(D + sub('v', '<mi>j</mi>'), D + sub('x', '<mi>i</mi>')) + MO(')') + MO('&#183;') + MI('sgn') + MO('(') + sub('N', '<mi>k</mi><mi>j</mi>') + MO(')'))
FD = m(frac(D + sub('v', '<mi>j</mi>'), D + sub('x', '<mi>i</mi>')) + MO('&#8776;')
       + frac(sub('v', '<mi>j</mi>') + MO('(') + MI('x') + MO('+') + MI('h') + sub('e', '<mi>i</mi>') + MO(')') + MO('&#8722;')
              + sub('v', '<mi>j</mi>') + MO('(') + MI('x') + MO('&#8722;') + MI('h') + sub('e', '<mi>i</mi>') + MO(')'), MN('2') + MI('h')))
LOOP = m(MI('sign') + MO('(') + MI('L') + MO(')') + MO('=') + '<munder><mo>&#8719;</mo><mrow><mi>a</mi><mo>&#8712;</mo><mi>L</mi></mrow></munder>' + sub('&#963;', '<mi>a</mi>'))
RANK = m(MI('rank') + '<mspace width="0.2em"></mspace>' + MI('N') + MO('[') + MO(':') + MO(',') + MI('R') + MO('(') + MI('L') + MO(')') + MO(']') + MO('=') + MO('|') + MI('L') + MO('|'))
CYC = m('<mi>&#957;</mi>' + MO('=') + MI('E') + MO('&#8722;') + MI('V') + MO('+') + MI('C'))
STRICT = m(frac(D + sub('f', '<mi>i</mi>'), D + sub('x', '<mi>i</mi>')) + MO('&#8801;') + MN('0'))
LOOSE = m(sub('r', '<mi>i</mi>') + MO('=') + frac(MO('|') + D + sub('f', '<mi>i</mi>') + MO('/') + D + sub('x', '<mi>i</mi>') + MO('|')
                                                 + '<mspace width="0.15em"></mspace>' + MO('|') + sub('x', '<mi>i</mi>') + MO('|'), sub('&#934;', '<mi>i</mi>'))
          + MO('&lt;') + MN('0.1'))
FLUX = m(sub('&#934;', '<mi>i</mi>') + MO('=') + '<munder><mo>&#8721;</mo><mi>j</mi></munder>' + MI('max') + MO('(') + sub('N', '<mi>i</mi><mi>j</mi>') + sub('v', '<mi>j</mi>') + MO(',') + MN('0') + MO(')'))
PAIR = m(MI('z') + MO('=') + sub('c', '<mi>a</mi>') + sub('x', '<mi>a</mi>') + MO('+') + sub('c', '<mi>b</mi>') + sub('x', '<mi>b</mi>') + MO(',') + SP
         + frac(D + '<mover><mi>z</mi><mo>&#729;</mo></mover>', D + sub('x', '<mi>q</mi>')) + MO('=') + MN('0') + SP + '<mtext>for</mtext>' + SP + MI('q') + MO('&#8712;') + MI('S') + MO('&#8746;') + MI('P'))
KINDS = m('<msup><mrow><mo>(</mo><mi>&#957;</mi><mo>+</mo><mn>1</mn><mo>)</mo></mrow><mn>2</mn></msup>' + MO('=')
          + '<munderover><mo>&#8721;</mo><mrow><mi>l</mi><mo>=</mo><mn>0</mn></mrow><mi>&#957;</mi></munderover>' + MO('(') + MN('2') + MI('l') + MO('+') + MN('1') + MO(')'))
QN = m(MI('n') + MO('=') + '<mi>&#957;</mi>' + MO('+') + MN('1') + MO(',') + SP + MI('l') + MO('=') + MI('max') + MO('(') + MI('k') + MO(',') + MI('j') + MO(')') + MO(',') + SP + MI('m') + MO('=') + MI('k') + MO('&#8722;') + MI('j'))
BALANCE = m(sub('&#963;', '<mi>a</mi><mi>b</mi>') + MO('=') + sub('s', '<mi>a</mi>') + sub('s', '<mi>b</mi>') + MO(',') + SP + sub('s', '<mi>a</mi>') + MO('&#8712;') + MO('{') + MO('+') + MN('1') + MO(',') + MO('&#8722;') + MN('1') + MO('}'))
KINDS_INLINE = m(KINDS[len('<math display="block">'):-len('</math>')], block=False)
