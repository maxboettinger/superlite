# tests/scripts/test_fleet_stop_slash_930.py: fleet stop tells exit_agent whether the agent takes slash commands (#930)
import sys
import pytest
from test_fleet import world, REAL  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")


def rec(world):
    seen = []
    world.fh.exit_agent = lambda name, slash=False: seen.append((name, slash))
    return seen


def put(world, wid, **w):
    d = fleet.fs.load(world.sd); d["on"] = True
    d["workers"][wid] = {"name": f"sl-p-{wid.lower()}", "pane_id": f"w6:{wid}", "state": "ready", **w}
    fleet.fs.save(world.sd, d)


@pytest.mark.parametrize("w,slash", [
    ({"role": "implementer", "launch": {"argv": ["--model", "sonnet", "--disable-slash-commands"]}}, False),
    ({"role": "lead", "launch": {"argv": ["--model", "opus", "--permission-mode", "auto"]}}, True),
    ({"role": "lead", "launch": {"argv": ["--disable-slash-commands"]}}, False),
    ({"role": "research"}, False),
    ({"role": "lead"}, True),
    ({}, False),
])
def test_slash_commands(w, slash):
    assert fleet.slash_commands(w) is slash


def test_stop_spawned_worker_is_lean(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    seen = rec(world)
    assert fleet.stop(world.sd, ["W1"]) == ["W1"]
    assert seen == [(fleet.fs.agent_name(world.sd, "W1"), False)]
    assert any(c[0] == "close_pane" for c in world.fh.calls)


def test_stop_lead_keeps_slash(world):
    put(world, "W2", role="lead", launch={"argv": ["--model", "opus", "--permission-mode", "auto"]})
    seen = rec(world)
    assert fleet.stop(world.sd, ["W2"]) == ["W2"]
    assert seen == [("sl-p-w2", True)]
    assert ("close_pane", "w6:W2") in world.fh.calls
