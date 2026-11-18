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
    for want in ("BLOCKED: budget", "budget extend --plan $PLAN --ruling", "budget raise --to", "/superlite:resume"):
        assert want in s, want
    assert "no extra review rounds" not in SKILL


def test_skill_stop_conditions_name_the_budget_pause():
    assert "a budget pause after the one extension" in section(SKILL, "Stop conditions")


def test_skill_final_review_names_unverified_and_rounds():
    s = section(SKILL, "Final review")
    assert "UNVERIFIED" in s and "findings rounds" in s


def test_skill_names_corrections_add():
    assert "corrections add" in SKILL


def test_skill_length_stays_near_today():
    assert len(SKILL.encode("utf-8")) <= 13295 + 600


def test_metrics_md_documents_the_subcommands():
    m = (ROOT / "skills/subagent-driven-development/metrics.md").read_text(encoding="utf-8")
    assert "sl budget extend" in m and "sl budget raise" in m


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


def test_resume_names_budget_raise():
    assert "sl budget raise" in (ROOT / "commands/resume.md").read_text(encoding="utf-8")
