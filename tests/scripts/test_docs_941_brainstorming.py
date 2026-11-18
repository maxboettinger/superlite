from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_brainstorming_rules_941():
    text = (REPO / "skills/brainstorming/SKILL.md").read_text(encoding="utf-8")
    for phrase in (
        "Ask only when the answer changes what gets built",
        "it is the first question of the batch",
        "show mockups of the options before the plan",
        "what a builder would still have to guess",
    ):
        assert text.count(phrase) == 1, phrase
    assert len(text) <= 10000, len(text)


def test_coverage_platform_rule_941():
    text = (REPO / "skills/brainstorming/coverage.md").read_text(encoding="utf-8")
    assert text.count("a new project's platform is never assumed") == 1
