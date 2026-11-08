"""#286: the implementer agents name the next: cue and the cost of ending the turn before the wait reports."""
from __future__ import annotations

from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[2] / "agents"
RULE = ("then run the `wait:` line it prints (`<abs sl> run_tests --wait <path>`) in the foreground, "
        "never as a background command, and end your turn only after it reports; read only its summary.")
AGENT_CUE = ("The run prints a `next:` cue and, as its last line, that `wait:` line; a turn ended before "
             "the wait reports reaches the coordinator as your report, with no test result.")


@pytest.mark.parametrize("name", ["implementer.md", "implementer-haiku.md"])
def test_agents_name_the_cue(name):
    lines = (AGENTS / name).read_text(encoding="utf-8").splitlines()
    assert any(RULE + " " + AGENT_CUE in ln and ln.startswith("- TDD.") for ln in lines)


@pytest.mark.parametrize("name", ["implementer.md", "implementer-haiku.md"])
def test_agent_rule_kept(name):
    text = (AGENTS / name).read_text(encoding="utf-8")
    assert text.count(RULE) == 1 and text.count(AGENT_CUE) == 1
