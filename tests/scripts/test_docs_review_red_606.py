"""#606 and B146 follow-ups: the agent and skill docs name the red-run proof, the plan contract and the new lint warnings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split())


def test_package_reviewer_proves_red_runs_and_reads_the_plan_contract():
    t = read("agents/package-reviewer.md")
    assert "A `Red runs (task reports):` section in your brief names tasks whose report shows no red run." in t
    assert "A test that stays green is a finding" in t
    assert "The Produces line is not the whole contract" in t
    assert "List each such test under tests added with that red run's summary line." in t


def test_fleet_reviewer_line_names_both_sections():
    t = read("skills/subagent-driven-development/fleet.md")
    assert "`Red runs (task reports):`" in t and "`Plan contract outside Tn's Produces`" in t and "`no red run`" in t


def test_writing_plans_names_also_touches_and_the_lint_warnings():
    t = "\n".join(read(f"skills/writing-plans/{n}") for n in ("SKILL.md", "task-template.md", "probe-plan.md", "split.md"))
    assert "| `Also-touches` |" in t
    assert "`ALSO-TOUCHES:`" in t and "`OWNS:`" in t and "`REACH:`" in t
