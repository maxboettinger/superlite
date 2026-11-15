"""#849: brainstorming ranks open questions by what the answer saves and asks at most 2 rounds of 4."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills/brainstorming/SKILL.md").read_text(encoding="utf-8")
COVERAGE = (ROOT / "skills/brainstorming/coverage.md").read_text(encoding="utf-8")


def step2() -> str:
    return SKILL.split("## 2. Explore and ask, once")[1].split("## 3. Design")[0]


def test_step2_ranks_by_cost_saved():
    s = step2()
    assert "rank the open questions (coverage rows too) by what the answer saves" in s
    assert "shrinks the plan or makes a task mechanical enough for a cheaper model" in s


def test_step2_caps_two_rounds_of_four():
    assert "Ask at most 2 rounds of 4 (plain text: 4 per message, no 5th, the rest after the reply)" in step2()


def test_step2_rules_the_rest():
    assert "rule the rest as `Ruling:` lines the user can veto (a coverage row: `ruled`)" in step2()


def test_major_and_uncertain_never_capped():
    assert "major and uncertain first (the cap never rules them away)" in step2()


def test_no_ask_until_none_open():
    assert "until none is open" not in SKILL
    assert "until no row is open" not in COVERAGE


def test_coverage_step3_ranks_and_caps():
    assert "Rank the open rows by what the answer saves (major and uncertain first" in COVERAGE
    assert "recommended option first, at most 2 calls (no question tool:" in COVERAGE
    assert "a major or uncertain row is never ruled away by the cap" in COVERAGE


def test_skill_under_cap():
    assert len(SKILL) <= 10000
