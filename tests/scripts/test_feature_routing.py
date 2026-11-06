"""#230: /superlite:feature loads brainstorming before reading code or asking anything; an eval case guards it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEATURE = (ROOT / "commands" / "feature.md").read_text(encoding="utf-8")
CASE = ROOT / "evals" / "feature-routing"


def test_brainstorming_loads_first():
    steps = [ln for ln in FEATURE.splitlines() if ln.startswith("- ")]
    assert len(steps) == 4
    assert steps[0].startswith("- First, before you read code or ask anything, load `superlite:brainstorming`")
    assert "even when the change looks trivial" in steps[0] and "orchestrator choice" in steps[0]
    assert FEATURE.index("superlite:brainstorming") < FEATURE.index("Read before designing")
    assert "Ask the orchestrator choice" not in FEATURE


def test_eval_case_scores_only_the_brainstorming_load():
    assert sorted(p.name for p in (CASE / "graders").glob("*.md")) == ["skill-fired.md"]
    g = (CASE / "graders" / "skill-fired.md").read_text(encoding="utf-8")
    for s in ("type: tool_used", "tool: Skill", "brainstorming", "arm: with-only"):
        assert s in g, s
    prompt = (CASE / "prompt.md").read_text(encoding="utf-8")
    assert prompt.startswith("/superlite:feature ") and "orchestrator" not in prompt.lower()
