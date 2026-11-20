# tests/regression/test_using_superlite_start_first_1034.py
"""#1034: using-superlite routes a non-trivial request to /superlite:start before any tool."""
from pathlib import Path

USING = Path(__file__).resolve().parents[2] / "skills/using-superlite/SKILL.md"
LINE = "No mode, non-trivial build: `/superlite:start` before any tool.\n"
OLD = "First message, no mode, not trivial: `/superlite:start`."


def test_first_line_loads_start_before_any_tool_1034():
    body = USING.read_text(encoding="utf-8").split("---\n", 2)[2]
    assert body.lstrip("\n").startswith(LINE)


def test_old_first_line_is_gone_1034():
    assert OLD not in USING.read_text(encoding="utf-8")


def test_skills_line_keeps_bug_systematic_debugging_1034():
    assert "bug `systematic-debugging`" in USING.read_text(encoding="utf-8")


def test_file_stays_under_cap_1034():
    assert len(USING.read_text(encoding="utf-8")) < 1500


def test_graphify_wording_1034():
    assert "Graphify only via `sl graphify_gate`." in USING.read_text(encoding="utf-8")
