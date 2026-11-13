"""Docs name the brief-only implementer, tier roles, reviewer commit, checkpoint line, plan resolution, debug path."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = "skills/subagent-driven-development/fleet.md"
FLEET = "docs/fleet.md"
SKILLS = "docs/skills-and-agents.md"


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_docs_name_tier_roles():
    for rel in (SKILL, FLEET, SKILLS):
        assert "package-reviewer, final-reviewer and checker take no `--tier`" in text(rel), rel


def test_docs_name_brief_only_implementer():
    for rel in (SKILL, FLEET, SKILLS):
        t = text(rel)
        assert "fleet spawn --role implementer --brief" in t, rel
        assert "brief-only" in t, rel


def test_fleet_docs_quote_blocked_tail():
    for rel in (SKILL, FLEET):
        assert "or pass --brief FILE for a brief-only task outside a plan run" in text(rel), rel


def test_docs_reviewer_commits_outside_a_run():
    for rel in (SKILL, FLEET, SKILLS):
        assert "outside a run it commits its own fixes with a plain `git commit`" in text(rel), rel


def test_fleet_docs_name_reviewed_version():
    for rel in (SKILL, FLEET):
        assert "Reviewed version:" in text(rel), rel


def test_docs_fleet_md_names_plan_resolution():
    t = text(FLEET)
    assert "plan_tools.run_plan" in t
    assert "stable.json, then pool.json, then plan.md" in t


def test_debug_md_names_fleet_path():
    t = text("commands/debug.md")
    for phrase in (
        "fleet spawn --role fixer --tier 3 --brief",
        "Outside a run: commit with plain git commit",
        "fleet spawn --role implementer --brief",
        "Fix inline",
        "only inside a plan run",
    ):
        assert phrase in t, phrase
    assert t.index("worktree ensure") < t.index("Fix inline")
