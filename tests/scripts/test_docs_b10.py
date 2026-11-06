from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def test_skill_names_gate_hold_report():
    assert "`WAIT FOR T0:`" in SKILL
    assert "hold Tn --reason R" in SKILL
    assert "`<plan>.build-report.md`" in SKILL
    assert len(SKILL) <= 11700


def test_tools_rows():
    for s in ("| `hold` |", "WAIT FOR T0", "HELD:", "`stubs`", "`wait`", "`base`", "build-report",
              "never runs the suite"):
        assert s in TOOLS, s


def test_testcmd_row_sentences_split():
    assert "when `related` is set T0 runs it" not in TOOLS
    assert "`related` is set. Wave 0 (T0) runs it as the check that `run_tests` detects the stack." in TOOLS
