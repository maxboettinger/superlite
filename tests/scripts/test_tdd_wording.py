"""TDD and verification skill wording: regression guards, right reason, real container."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TDD = (ROOT / "skills/test-driven-development/SKILL.md").read_text()
VERIFY = (ROOT / "skills/verification-before-completion/SKILL.md").read_text()


def line(text: str, prefix: str) -> str:
    return next(l for l in text.splitlines() if l.startswith(prefix))


def section(text: str, heading: str) -> str:
    return text.split(heading + "\n")[1].split("\n## ")[0]


def test_red_step_names_guard_exception():
    red = line(TDD, "1. **Red.**")
    assert "regression guard" in red
    assert "breaking the code on purpose" in red


def test_green_step_names_right_reason():
    green = line(TDD, "2. **Green.**")
    assert "for the intended reason" in green
    assert "print the measured values once" in green


def test_red_flag_allows_guards():
    expected = "- The test passed on its first run, and it is not a regression guard you saw fail on purpose."
    assert expected in TDD.splitlines()
    assert "- The test passed on its first run." not in TDD.splitlines()


def test_ui_check_in_real_container():
    for text, heading in ((TDD, "## Good tests"), (TDD, "## Done checklist"), (VERIFY, "## Acceptable evidence")):
        body = section(text, heading)
        assert "real container" in body and "real data state" in body, heading


def test_done_checklist_names_guards():
    assert "Regression guards were seen failing once" in section(TDD, "## Done checklist")
