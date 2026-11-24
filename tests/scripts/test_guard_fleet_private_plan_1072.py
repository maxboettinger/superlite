# tests/scripts/test_guard_fleet_private_plan_1072.py: rule 4 names a session's private state folder as PLAN like any other (#1072, #1088)
import json

import pytest
from test_guard_fleet_run_state_495 import Env

AGENTS = ["superlite:researcher", "superlite:writer", "superlite:final-reviewer"]


@pytest.fixture
def e(tmp_path):
    return Env(tmp_path)


def _private(e):
    p = e.home / "sessions" / "s1.d" / ".superlite"
    p.mkdir(parents=True)
    e.bind("s1", f"{p}\n123\n{e.main}\n")
    e.on(p)
    return p


@pytest.mark.parametrize("agent,tail", [("superlite:researcher", "before a plan exists."),
                                        ("superlite:writer", "for a build without a plan."),
                                        ("superlite:final-reviewer", "for a build without a plan.")])
def test_private_folder_named_as_plan_again(e, agent, tail):
    p = _private(e)
    r = e.call(e.main, agent=agent)
    assert r.returncode == 2
    assert f"PLAN is the plan file, or {p} {tail}" in r.stderr
    assert "never " not in r.stderr and "#1072" not in r.stderr
    rows = (p / "incidents.jsonl").read_text().splitlines()
    assert json.loads(rows[-1])["rule"] == "fleet"


@pytest.mark.parametrize("agent,tail", [("superlite:researcher", "before a plan exists."),
                                        ("superlite:writer", "for a build without a plan."),
                                        ("superlite:final-reviewer", "for a build without a plan.")])
def test_project_folder_text_unchanged(e, agent, tail):
    e.on(e.msd)
    r = e.call(e.main, agent=agent)
    assert r.returncode == 2
    assert f"PLAN is the plan file, or {e.msd} {tail}" in r.stderr and "never " not in r.stderr
