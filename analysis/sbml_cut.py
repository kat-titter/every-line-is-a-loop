"""Rewire one arrow of an SBML model: hold it at a fixed value (a cut) or pass it through one relay step.

Reads:  an SBML document (libsbml), already loaded by the caller
Writes: nothing; edits the document in place (essential_loops.py saves it)
Run:    imported by analysis/essential_loops.py

An arrow src -> dst is every way src enters dst's rate of change: the kinetic laws of the reactions that make or use
dst and name src (directly or through assignment rules), or dst's own rate rule. Rewiring replaces src by a new symbol
in exactly those places and nowhere else:
  cut    the new symbol is a constant at src's settled value, so dst no longer hears src move
  relay  the new symbol is a new variable r with dr/dt = rate * (src - r), so dst hears src one step late
A reaction that changes other molecules too is split: dst gets its own copy of the reaction, with the rewired law, and
the original keeps every other molecule. Local parameters are promoted to global ones first, so both halves read the
same rate constants. For an arrow from a molecule to itself (a kept self-feeding loop) only the reactions named are
rewired, so its decay is left alone; a self-arrow written as a rate rule is rewired whole, decay included.
"""

from __future__ import annotations

from typing import Any

import libsbml

CUT, SHADOW = 'cut__', 'shadow__'


def promote_locals(doc: Any) -> None:
    """Make every reaction's local parameters global (the names truth_tests.setup would give them)."""
    props = libsbml.ConversionProperties()
    props.addOption('promoteLocalParameters', True)
    doc.convert(props)


def _names(node: Any) -> set[str]:
    """Every identifier an expression mentions."""
    if node is None:
        return set()
    out = {node.getName()} if node.getType() == libsbml.AST_NAME else set()
    for i in range(node.getNumChildren()):
        out |= _names(node.getChild(i))
    return out


def _assignments(m: Any) -> dict[str, Any]:
    return {r.getVariable(): r for r in (m.getRule(i) for i in range(m.getNumRules())) if r.isAssignment()}


def _hearers(m: Any, src: str) -> set[str]:
    """Assigned variables whose value depends on src, directly or through other assigned variables."""
    assign, hear, grew = _assignments(m), set(), True
    while grew:
        grew = False
        for v, r in assign.items():
            if v not in hear and _names(r.getMath()) & ({src} | hear):
                hear.add(v)
                grew = True
    return hear


def _add_parameter(m: Any, pid: str, value: float, constant: bool) -> None:
    p = m.createParameter()
    p.setId(pid)
    p.setValue(float(value))
    p.setConstant(constant)


def _shadow(m: Any, src: str, new: str, tag: str) -> dict[str, str]:
    """Copy each assigned variable that hears src into a shadow that hears `new` instead; return the renaming."""
    assign, hear = _assignments(m), sorted(_hearers(m, src))
    rename = {src: new, **{v: f'{SHADOW}{tag}__{v}' for v in hear}}
    for v in hear:
        _add_parameter(m, rename[v], 0.0, False)
        rule = m.createAssignmentRule()
        rule.setVariable(rename[v])
        rule.setMath(_renamed(assign[v].getMath(), rename))
    return rename


def _renamed(math: Any, rename: dict[str, str]) -> Any:
    out = math.deepCopy()
    for old, new in rename.items():
        out.renameSIdRefs(old, new)
    return out


def _split_reaction(m: Any, rid: str, dst: str, rename: dict[str, str], tag: str) -> None:
    """Give dst its own copy of reaction rid with the renamed law; the original keeps the other molecules."""
    old = m.getReaction(rid)
    new = old.clone()
    new.setId(f'{rid}__{tag}')
    if new.isSetName():
        new.unsetName()
    for refs, keep in ((new.getListOfReactants(), True), (new.getListOfProducts(), True)):
        for i in reversed(range(refs.size())):
            if (refs.get(i).getSpecies() == dst) != keep:
                refs.remove(i)
            else:
                refs.get(i).unsetId()
    for refs in (old.getListOfReactants(), old.getListOfProducts()):
        for i in reversed(range(refs.size())):
            if refs.get(i).getSpecies() == dst:
                refs.remove(i)
    mod = old.createModifier()
    mod.setSpecies(dst)
    new.getKineticLaw().setMath(_renamed(old.getKineticLaw().getMath(), rename))
    if m.addReaction(new) != libsbml.LIBSBML_OPERATION_SUCCESS:
        raise RuntimeError(f'could not add the split reaction for {rid}')


def rewire(doc: Any, src: str, dst: str, new: str, tag: str, only: set[str] | None = None) -> list[str]:
    """Replace src by the symbol `new` wherever it enters dst's rate of change; return the places rewired.

    `only` limits the reactions touched (used for a molecule's arrow to itself)."""
    m = doc.getModel()
    rename = _shadow(m, src, new, tag)
    hears = set(rename)
    done = []
    for i in range(m.getNumRules()):
        r = m.getRule(i)
        if r.isRate() and r.getVariable() == dst and _names(r.getMath()) & hears:
            r.setMath(_renamed(r.getMath(), rename))
            done.append('rule:' + dst)
    for rid in [m.getReaction(i).getId() for i in range(m.getNumReactions())]:
        rx = m.getReaction(rid)
        touches = any(
            refs.get(i).getSpecies() == dst
            for refs in (rx.getListOfReactants(), rx.getListOfProducts())
            for i in range(refs.size())
        )
        if not touches or not rx.isSetKineticLaw() or (only is not None and rid not in only):
            continue
        if _names(rx.getKineticLaw().getMath()) & hears:
            _split_reaction(m, rid, dst, rename, tag)
            done.append('R:' + rid)
    return done


def symbol_value(doc: Any, node: str, concentration: float, volume: float) -> float:
    """The value the bare symbol `node` has in a rate law when the molecule sits at `concentration`."""
    sp = doc.getModel().getSpecies(node)
    return concentration * volume if sp is not None and sp.getHasOnlySubstanceUnits() else concentration


def cut(doc: Any, src: str, dst: str, value: float, tag: str, only: set[str] | None = None) -> list[str]:
    """Hold the arrow src -> dst at `value`. The constant is written as an assigned parameter, so the atlas, which
    steps free parameters, never steps it."""
    m, new = doc.getModel(), f'{CUT}{tag}'
    _add_parameter(m, new, value, False)
    rule = m.createAssignmentRule()
    rule.setVariable(new)
    rule.setMath(libsbml.parseL3Formula(repr(float(value))))
    return rewire(doc, src, dst, new, tag, only)


def relay(doc: Any, src: str, dst: str, start: float, rate: float, tag: str, only: set[str] | None = None) -> list[str]:
    """Insert one relay step on the arrow src -> dst: a new variable that follows src at `rate` per time unit.

    The rate is written into the rule as a number, so the copy gains no parameter the atlas could step."""
    m, new = doc.getModel(), f'relay__{tag}'
    _add_parameter(m, new, start, False)
    rule = m.createRateRule()
    rule.setVariable(new)
    rule.setMath(libsbml.parseL3Formula(f'{float(rate)!r} * ({src} - {new})'))
    return rewire(doc, src, dst, new, tag, only)
