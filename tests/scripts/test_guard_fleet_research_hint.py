import json
import re
import sys
from pathlib import Path

import pytest
from test_fleet_hooks import sd  # noqa: F401  (sd is a fixture)
from test_guard_fleet_agents import fleet, guard

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fleet_roles  # noqa: E402
import routing  # noqa: E402

AGENTS = ["superlite:implementer", "superlite:implementer-haiku", "superlite:fixer-sonnet",
          "superlite:fixer-sonnet-high", "superlite:fixer-opus", "superlite:package-reviewer",
          "superlite:final-reviewer", "superlite:researcher"]
NO_RETRY = "It is blocked on every call while fleet is on: do not retry it."
HINT = re.compile(r"sl fleet spawn --role (\S+)(?: --tier (\S+))? --plan PLAN")


@pytest.mark.parametrize("agent", AGENTS)
def test_block_says_do_not_retry(sd, agent):
    fleet(sd)
    r = guard(sd, agent)
    assert r.returncode == 2 and NO_RETRY in r.stderr


def test_researcher_block_names_full_research_path(sd):
    fleet(sd)
    r = guard(sd, "superlite:researcher")
    assert r.returncode == 2
    for part in ("superlite:researcher runs as a fleet worker",
                 "Research path (fleet.md), one worker per prompt",
                 f"write the prompt to {sd}/briefs/<name>.md;",
                 "sl fleet spawn --role research --plan PLAN prints Wn;",
                 f"sl fleet send Wn --brief {sd}/briefs/<name>.md --plan PLAN;",
                 "sl fleet wait Wn --plan PLAN (up to 9 min: Bash timeout 600000);",
                 f"the answer is in {sd}/fleet/reports/<name>.md.",
                 f"PLAN is the plan file, or {sd} before a plan exists.",
                 "sl fleet off goes back to in-process agents."):
        assert part in r.stderr, part
    assert "<abs brief>" not in r.stderr


def test_researcher_any_case_gets_research_path(sd):
    fleet(sd)
    r = guard(sd, "Superlite:Researcher")
    assert r.returncode == 2
    assert "Superlite:Researcher runs as a fleet worker" in r.stderr
    assert "sl fleet spawn --role research --plan PLAN prints Wn;" in r.stderr


@pytest.mark.parametrize("agent,hint", [("superlite:fixer-opus", "sl fleet spawn --role fixer --tier opus --plan PLAN"),
                                        ("superlite:final-reviewer", "sl fleet spawn --role final-reviewer --plan PLAN")])
def test_other_roles_keep_generic_hint(sd, agent, hint):
    fleet(sd)
    r = guard(sd, agent)
    assert r.returncode == 2 and hint in r.stderr
    assert "then sl fleet send Wn --brief <abs brief> --plan PLAN (fleet.md)." in r.stderr
    assert "Research path" not in r.stderr


def test_incident_line_unchanged(sd):
    fleet(sd)
    guard(sd, "superlite:researcher")
    inc = json.loads((sd / "incidents.jsonl").read_text().splitlines()[-1])
    assert inc == {"kind": "rule-block", "agent": "coordinator", "tool": "Agent",
                   "target": "superlite:researcher (fleet on)", "rule": "fleet", "cwd": str(sd.parent)}


@pytest.mark.parametrize("role,tier", [("implementer", None), ("implementer", "haiku"), ("fixer", "sonnet"),
                                       ("fixer", "sonnet-high"), ("fixer", "opus"), ("package-reviewer", None),
                                       ("final-reviewer", None), ("research", None)])
def test_hint_round_trips_through_fleet_roles(sd, role, tier):
    cfg = routing.load_cfg()
    agent = fleet_roles.launch(role, tier, cfg)["agent"]
    fleet(sd)
    m = HINT.search(guard(sd, agent).stderr)
    assert m, agent
    assert m.group(1) in fleet_roles.ROLES
    assert fleet_roles.launch(m.group(1), m.group(2), cfg)["agent"] == agent
