import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_names_the_unattended_rule():
    t = (ROOT / "commands" / "start.md").read_text()
    for s in ("AskUserQuestion is unavailable", "sl orchestrator set ai", "Ruling:", "superlite:brainstorming"):
        assert s in t


def test_using_superlite_stays_under_cap():
    assert len((ROOT / "skills" / "using-superlite" / "SKILL.md").read_text()) <= 1500


def test_using_superlite_says_a_new_app_is_never_trivial():
    t = (ROOT / "skills" / "using-superlite" / "SKILL.md").read_text()
    assert any("new app" in s and "never trivial" in s for s in re.split(r"(?<=[.!?])\s+", t))
