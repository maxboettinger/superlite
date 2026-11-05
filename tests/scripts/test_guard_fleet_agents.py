# tests/scripts/test_guard_fleet_agents.py
import json
import pytest
from test_fleet_hooks import run_hook, sd  # noqa: F401  (sd is a fixture)

def agent_call(sd, agent, **extra):
    return json.dumps({"session_id": "s1", "tool_name": "Agent", "cwd": str(sd.parent),
                       "tool_input": {"subagent_type": agent, "description": "d", "prompt": "p"}, **extra})

def fleet(sd, on=True):
    (sd / "fleet.json").write_text(json.dumps({"on": on, "label": "sl:proj", "next": 2,
                                               "workers": {"W1": {"one_turn": True, "state": "ready"}}}, indent=2))

def guard(sd, agent, env=None, **extra):
    return run_hook("block-coordinator-edits", agent_call(sd, agent, **extra), {"SUPERLITE_STATE_DIR": str(sd), **(env or {})}, sd.parent)

@pytest.mark.parametrize("agent,hint", [
    ("superlite:implementer", "sl fleet spawn --role implementer "),
    ("superlite:implementer-haiku", "sl fleet spawn --role implementer --tier haiku"),
    ("superlite:fixer-sonnet", "sl fleet spawn --role fixer --tier sonnet "),
    ("superlite:fixer-sonnet-high", "sl fleet spawn --role fixer --tier sonnet-high"),
    ("superlite:fixer-opus", "sl fleet spawn --role fixer --tier opus"),
    ("superlite:package-reviewer", "sl fleet spawn --role package-reviewer"),
    ("superlite:final-reviewer", "sl fleet spawn --role final-reviewer"),
    ("superlite:researcher", "sl fleet spawn --role research")])
def test_fleet_on_blocks_each_superlite_role(sd, agent, hint):
    fleet(sd)
    r = guard(sd, agent)
    assert r.returncode == 2 and hint in r.stderr and "fleet send Wn --brief" in r.stderr and "sl fleet off" in r.stderr
    inc = json.loads((sd / "incidents.jsonl").read_text().splitlines()[-1])
    assert (inc["kind"], inc["agent"], inc["tool"]) == ("rule-block", "coordinator", "Agent") and agent in inc["target"]

def test_fleet_off_or_absent_changes_nothing(sd):
    assert guard(sd, "superlite:fixer-opus").returncode == 0
    fleet(sd, on=False)
    assert guard(sd, "superlite:final-reviewer").returncode == 0

def test_other_agents_workers_and_subagents_pass(sd):
    fleet(sd)
    assert guard(sd, "Explore").returncode == 0 and guard(sd, "general-purpose").returncode == 0
    assert guard(sd, "superlite:implementer", env={"SUPERLITE_FLEET_WORKER": "W1"}).returncode == 0
    assert guard(sd, "superlite:implementer", agent_id="a123").returncode == 0
