"""B95 (B94 follow-up): SDD fleet.md and the fixers name the task=coordinator brief and its report line."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINE = "commit: held for the coordinator"


def test_sdd_fleet_names_task_coordinator():
    text = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    assert "task=coordinator" in text and LINE in text


@pytest.mark.parametrize("name", ["fixer-sonnet", "fixer-sonnet-high", "fixer-opus"])
def test_fixer_names_task_coordinator(name):
    text = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
    assert "task=coordinator" in text or "task coordinator" in text, name
    assert LINE in text, name
