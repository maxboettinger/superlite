"""#898: SDD SKILL.md's "Rulings, not stalls" line names the scope ruling form and points to orchestrator.md."""
from pathlib import Path

SDD_DIR = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development"
SDD = (SDD_DIR / "SKILL.md").read_text(encoding="utf-8")
ORCH = (SDD_DIR / "orchestrator.md").read_text(encoding="utf-8")
FORM = "`Ruling: [scope] <decision> - <why> - <cost if wrong>`"
SCOPE = "a deliverable added, dropped or changed after approval: " + FORM + " (`orchestrator.md` `## Scope rulings`)."


def test_rulings_line_names_the_scope_form():
    line = next(l for l in SDD.splitlines() if l.startswith("**Rulings, not stalls.**"))
    assert line.endswith("to `.superlite/progress.md`; " + SCOPE)


def test_orchestrator_section_matches():
    assert "## Scope rulings" in ORCH and FORM in ORCH


def test_cap_holds():
    assert len(SDD) <= 13300, len(SDD)
