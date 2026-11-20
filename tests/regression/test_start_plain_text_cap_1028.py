"""#1028: start.md step 4 states the 4-question cap for a run that never loads brainstorming."""
from pathlib import Path

START = Path(__file__).resolve().parents[2] / "commands/start.md"
CAP = (
    "4. Load the skill for the mode before you read code or ask anything, and follow it. "
    "Its one question batch holds at most 4 questions, with or without a question tool: "
    "in plain text at most 4 numbered questions in one message and nothing asked after them; "
    "rule the rest as `Ruling:` lines or ask them after the reply.\n"
)
BULLETS = (
    "   - Regular: `superlite:using-superlite` sizing, then `superlite:brainstorming`.\n"
    "   - MVP: same as `/superlite:mvp`.\n"
    "   - Feature: same as `/superlite:feature`.\n"
    "   - Debug: same as `/superlite:debug`.\n"
)


def test_start_step_4_states_the_plain_text_cap_1028():
    assert CAP in START.read_text(encoding="utf-8")


def test_start_step_4_keeps_the_mode_bullets_1028():
    assert CAP + BULLETS in START.read_text(encoding="utf-8")
