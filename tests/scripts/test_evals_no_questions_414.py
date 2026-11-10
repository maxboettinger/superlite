"""#414: the ai-bounded-quiet no-questions judge passes a final message that reports a denied test command."""
from __future__ import annotations

from pathlib import Path

GRADER = Path(__file__).resolve().parents[2] / "evals" / "ai-bounded-quiet" / "graders" / "no-questions.md"


def split():
    text = GRADER.read_text()
    assert text.startswith("---\n")
    _, head, body = text.split("---\n", 2)
    fm = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return head, fm, body


def test_type_and_one_line_criteria():
    head, fm, _ = split()
    assert fm["type"] == "llm"
    assert set(fm) == {"type", "criteria"}
    assert len(head.splitlines()) == 2


def test_criteria_fail_only_on_design_scope_or_preference_questions():
    criteria = split()[1]["criteria"]
    for need in ("Fail only when", "design, scope or preference", "waits for the user's answer",
                 "zero questions included"):
        assert need in criteria, need


def test_criteria_never_counts_a_denied_test_command_report():
    criteria = split()[1]["criteria"]
    for need in ("Ruling lines", "a tool, command or permission was denied", "run a command or test by hand",
                 "Bash was denied, please run pytest yourself", "enable or allow a denied tool",
                 "checks not run", "optional follow-up"):
        assert need in criteria, need


def test_criteria_is_a_safe_yaml_plain_scalar():
    criteria = split()[1]["criteria"]
    assert ": " not in criteria and " #" not in criteria
    assert criteria[0] not in "\"'&*!|>%@`{[#-?:,"
    assert not criteria.endswith(":")


def test_body_names_the_denied_command_report():
    body = split()[2]
    assert "rulings, not questions" in body
    assert "run it by hand" in body and "not a question" in body
