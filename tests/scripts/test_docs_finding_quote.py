"""Reviewer and fixing prose: a finding quotes its line, earlier findings are named by id, rounds are listed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
PACKAGE = (ROOT / "agents" / "package-reviewer.md").read_text(encoding="utf-8")
FIXING = (ROOT / "skills" / "subagent-driven-development" / "fixing.md").read_text(encoding="utf-8")
FLEET = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")


def test_final_reviewer_grammar_names_quote():
    assert "file:line - problem - fix - tier N - quote: `<the exact text of that line>`" in FINAL
    assert "a finding whose quote is not in the file is dropped" in FINAL


def test_final_reviewer_missing_things_quote_an_anchor():
    assert "quotes the line where it belongs" in FINAL


def test_final_reviewer_names_earlier_findings_by_id():
    assert "naming the earlier one by its id" in FINAL


def test_package_reviewer_open_findings_carry_quote():
    assert "An open finding carries the exact text of its line as quote" in PACKAGE


def test_fixing_names_unverified_repeat_and_dismiss():
    for phrase in ("UNVERIFIED", "repeat of", "findings dismiss", "no review: start a fresh final reviewer"):
        assert phrase in FIXING, phrase


def test_fleet_md_names_rounds():
    assert "packet --previous" in FLEET


def test_final_reviewer_keeps_its_older_rules():
    for phrase in ("Checked:", "FAST PATH", "partial: lines A-B not read", "at most 300 words"):
        assert phrase in FINAL, phrase


def test_fleet_md_repeat_is_a_brief_note_not_a_stderr_line():
    assert "`UNVERIFIED ...` (the quoted line is not in the file; no fixer), `DISMISSED ...` (ruled no defect earlier)" in FLEET
    assert "`repeat of ...` (routed one tier up)" not in FLEET
    assert "the brief's finding line says `repeat of <id>`" in FLEET
