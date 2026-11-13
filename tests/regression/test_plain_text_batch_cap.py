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


COVERAGE = SKILL.parent / "coverage.md"
ONE_BATCH = SKILL.parents[2] / "evals/ai-asks-once/graders/one-batch.md"
PLAIN_CAP = "no question tool: at most 4 numbered questions per message and no question after them; rows past the fourth are asked after the reply"


def test_plain_text_rounds_keep_the_cap_758():
    # #758: with no question tool a run listed 6 numbered questions in one message.
    assert "until none is open (plain text: 4 per message, no 5th, the rest after the reply)" in SKILL.read_text()
    assert PLAIN_CAP in COVERAGE.read_text()


def test_one_batch_judge_lists_then_counts_758():
    text = ONE_BATCH.read_text()
    assert "First list, one per line, each question" in text
    assert "then count the lines" in text
    assert "a separate list of the defaults it will use when the user does not answer" in text
    assert "Pass when the count is four or fewer, zero included" in text
    assert "fail only when it is five or more" in text
