"""brainstorming: the 4-question cap also holds with no question tool."""
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills/brainstorming/SKILL.md"


def test_plain_text_batch_keeps_the_cap():
    assert (
        "ask them in ONE `AskUserQuestion` call (no question tool: one plain-text message, same cap, nothing asked outside its numbered questions): up to 4 questions"
        in SKILL.read_text()
    )


def test_detail_choice_is_a_ruling_for_ai_orchestrator():
    assert (
        "include the plan `detail` choice in the same batch (AI orchestrator: a `Ruling:` line, not a question): `contracts`"
        in SKILL.read_text()
    )
