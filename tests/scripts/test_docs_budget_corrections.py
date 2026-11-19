"""The skill, metrics reference, gates, tools and resume docs name the budget pause, corrections and finding evidence."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills/subagent-driven-development/SKILL.md").read_text(encoding="utf-8")


def section(text, head):
    m = re.search(r"^## " + re.escape(head) + r"\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, head
    return m.group(1)


def row(text, name):
    m = re.search(r"^\| `" + re.escape(name) + r"` \|.*$", text, re.M)
    assert m, name
    return m.group(0)


def test_skill_budget_section_names_pause_extend_and_raise():
    s = section(SKILL, "Measure and budget")
    for want in ("BLOCKED: budget", "budget extend", "budget raise", "metrics.md"):
        assert want in s, want
    assert "no extra review rounds" not in SKILL
    m = (ROOT / "skills/subagent-driven-development/metrics.md").read_text(encoding="utf-8")
    assert "/superlite:resume" in m and "budget extend --plan P --ruling TEXT" in m and "budget raise --to USD" in m


def test_skill_stop_conditions_name_the_budget_pause():
    assert "a budget pause after the one extension" in section(SKILL, "Stop conditions")


def test_skill_final_review_names_unverified_and_rounds():
    s = (ROOT / "skills/subagent-driven-development/fixing.md").read_text(encoding="utf-8")
    assert "UNVERIFIED" in s and "findings rounds" in s


def test_skill_names_corrections_add():
    assert "corrections add" in (ROOT / "skills/subagent-driven-development/scripts/finish.py").read_text(encoding="utf-8")


def test_skill_length_stays_near_today():
    assert len(SKILL) <= 13300


def test_gates_md_row():
    g = (ROOT / "docs/gates.md").read_text(encoding="utf-8")
    r = row(g, "Cost caps are enforced") if "| `Cost caps" in g else next(ln for ln in g.splitlines() if "Cost caps are enforced" in ln)
    assert "pauses the run" in r and "stops optional work" not in g


def test_tools_md_rows():
    t = (ROOT / "docs/tools.md").read_text(encoding="utf-8")
    row(t, "corrections")
    row(t, "finding_check")
    for name, words in (("budget", ("extend", "raise")), ("findings", ("dismiss", "rounds"))):
        r = row(t, name)
        for w in words:
            assert w in r, (name, w)


def test_docs_name_the_real_blocked_lines_and_corrections_file():
    s = (ROOT / "skills/subagent-driven-development/metrics.md").read_text(encoding="utf-8")
    assert "dispatch: BLOCKED: budget: paused" in s and "BLOCKED: fleet spawn: budget: paused" in s
    t = (ROOT / "docs/tools.md").read_text(encoding="utf-8")
    r = row(t, "corrections")
    assert "docs/superlite/corrections.md" in r and "list" in r and "rm" in r
