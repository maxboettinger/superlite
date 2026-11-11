"""#485, #438: a fixer says what it does outside an sl run and names the run_tests next: cue."""
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[2] / "agents"


@pytest.mark.parametrize("name", ["fixer-sonnet", "fixer-sonnet-high", "fixer-opus"])
def test_fixer_outside_run(name):
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    head = text.split("---\n")[1]
    assert "outside a run" in head
    for need in ("Outside a run", "git commit", "the full suite when your brief asks for it", "`next:`"):
        assert need in text, (name, need)
