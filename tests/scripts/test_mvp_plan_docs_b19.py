# tests/scripts/test_mvp_plan_docs_b19.py
"""B19: MVP's orchestrator choice rides in brainstorming's batch; the seam rerun is pytest-only (#261, #262)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MVP = (ROOT / "commands" / "mvp.md").read_text(encoding="utf-8")
PLANS = (ROOT / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")


def test_mvp_has_no_standalone_orchestrator_question():
    assert "Ask the orchestrator choice" not in MVP
    steps = [ln for ln in MVP.splitlines() if ln[:3] in {f"{n}. " for n in range(1, 10)}]
    assert len(steps) == 7
    first = steps[0]
    assert first.startswith("1. First, before you write the plan or ask anything, load `superlite:brainstorming`")
    for s in ("one question batch carries the orchestrator choice", "`sl orchestrator set human|ai`",
              "AskUserQuestion is withheld", "go on to step 2 in the same turn", "replace brainstorming's design and approval steps"):
        assert s in first, s
    assert MVP.count("superlite:brainstorming") == 1
    assert steps[1].startswith("2. Write the MVP plan")


def test_seam_check_rerun_is_pytest_only():
    rule = next(ln for ln in PLANS.splitlines() if ln.startswith("2. **A task waits only"))
    assert "On pytest projects" in rule and "`SUPERLITE_REAL=1` swaps each fake" in rule
    assert rule.index("On pytest projects") < rule.index("SUPERLITE_REAL")
    assert "Other stacks have no such rerun" in rule and "test-support file" in rule and "integration task runs the real seam" in rule
    assert "Consumers' own tests still run against the real producer later, through the seam check (`SUPERLITE_REAL=1`)." not in PLANS
