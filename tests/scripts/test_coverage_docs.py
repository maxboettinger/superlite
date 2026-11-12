"""Skill and template text for the brainstorming coverage pass."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAINSTORM = (ROOT / "skills/brainstorming/SKILL.md").read_text()
WRITING = (ROOT / "skills/writing-plans/SKILL.md").read_text()
REVIEW = (ROOT / "skills/writing-plans/review-plan.md").read_text()


def test_brainstorming_points_at_the_pass():
    for phrase in ("coverage.md", "**Coverage:** off", "## Coverage", "spike"):
        assert phrase in BRAINSTORM, phrase
    assert len(BRAINSTORM) <= 10000  # 9,500 before #626 listed the 14 coverage categories inline


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


COVERAGE = (ROOT / "skills/brainstorming/coverage.md").read_text()


def coverage_categories():
    table = COVERAGE.split("## Categories", 1)[1]
    names = [ln.split("|")[1].strip() for ln in table.splitlines() if ln.startswith("| ")]
    return [n.lower() for n in names if n.lower() != "category"]


def test_brainstorming_lists_every_coverage_category_626():
    m = re.search(r"none merged or dropped: (.+?)\. A ruled row", BRAINSTORM)
    assert m, "the coverage pass names its categories inline"
    listed = [re.sub(r"\s*\(.*?\)", "", part).strip() for part in m.group(1).split("; ")]
    assert [x.lower() for x in listed] == coverage_categories()
    assert len(listed) == 14


def test_ruled_row_basis_is_the_decision_626():
    assert "A ruled row's basis is the decision itself (a number, a step), not \"none needed\"." in BRAINSTORM
