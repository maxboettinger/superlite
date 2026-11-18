from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD = REPO / "skills/subagent-driven-development"


def test_coordinator_rules_941():
    skill = (SDD / "SKILL.md").read_text(encoding="utf-8")
    fixing = (SDD / "fixing.md").read_text(encoding="utf-8")
    for phrase in (
        "Never send the same brief to the same tier twice",
        "check it yourself (run it or read it)",
        "the ruling names the smallest change that unblocks it",
    ):
        assert fixing.count(phrase) == 1, phrase
    for phrase in ("Never send the same brief to the same tier twice", "check it yourself (run it or read it)"):
        assert phrase not in skill, phrase
