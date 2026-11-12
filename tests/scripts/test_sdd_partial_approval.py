"""SDD SKILL.md Final review 3: an APPROVED that fleet wait marks ` partial` is no approval (follow-up of #591 to #593)."""
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "SKILL.md"


def test_partial_approval_is_no_review():
    final = SKILL.read_text(encoding="utf-8").split("## Final review", 1)[1].split("## Measure and budget", 1)[0]
    step3 = next(ln for ln in final.splitlines() if ln.startswith("3. "))
    assert "or a ` partial` APPROVED is no review: start a fresh one." in step3
