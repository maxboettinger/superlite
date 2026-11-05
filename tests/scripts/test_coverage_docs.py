"""Skill and template text for the brainstorming coverage pass."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAINSTORM = (ROOT / "skills/brainstorming/SKILL.md").read_text()
WRITING = (ROOT / "skills/writing-plans/SKILL.md").read_text()
REVIEW = (ROOT / "skills/writing-plans/review-plan.md").read_text()


def test_brainstorming_points_at_the_pass():
    for phrase in ("coverage.md", "**Coverage:** off", "## Coverage", "spike"):
        assert phrase in BRAINSTORM, phrase
    assert len(BRAINSTORM) <= 9500  # 9,000 before #151 added the worktree step


def test_writing_plans_names_coverage():
    for phrase in ("**Coverage:** off", "## Coverage", "COVERAGE:", "spike"):
        assert phrase in WRITING, phrase


def test_review_plan_has_coverage_section():
    decisions = REVIEW.index("`## Decisions you can change`")
    coverage = REVIEW.index("`## Coverage`")
    risks = REVIEW.index("`## Risks`")
    assert decisions < coverage < risks


def test_brainstorming_tells_to_read_coverage_md():
    assert "Read `coverage.md` in this skill's folder" in BRAINSTORM
    assert "../brainstorming/coverage.md" not in BRAINSTORM
