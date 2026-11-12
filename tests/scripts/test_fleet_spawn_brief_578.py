# tests/scripts/test_fleet_spawn_brief_578.py: `fleet spawn --brief F [--label L] --wait [--timeout T]` spawns, sends and waits in one call (#578); a worker gets the lead's fresh-pane retry (#551)
import json, os, sys
import pytest
from test_fleet import world  # noqa: F401
from test_fleet_spawn_shell_retry import script, starts, pauses, MSG  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import fleet_lead  # noqa: E402

REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted herdr failures need the in-process fake")


@pytest.fixture
def rec(world, monkeypatch):
    fleet.main(["on"])
    calls = {"send": [], "wait": []}
    monkeypatch.setattr(fleet_io, "send_brief", lambda sd, wid, brief, label="", full=False: calls["send"].append((wid, brief, label)) or label)
    monkeypatch.setattr(fleet_io, "wait", lambda sd, ids, t, *a, **k: calls["wait"].append((ids, t)) or [])
    brief = world.proj / "b.md"; brief.write_text("do it\n")
    calls["brief"] = str(brief)
    return calls


def state(w, wid): return json.loads((w.sd / "fleet.json").read_text())["workers"][wid]["state"]


def test_spawn_brief_sends_after_spawn(world, rec):
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "2", "--brief", rec["brief"], "--label", "FX1"]) == 0
    assert rec["send"] == [("W1", rec["brief"], "FX1")] and rec["wait"] == []


def test_spawn_brief_wait_one_call(world, rec):
    base = ["spawn", "--role", "fixer", "--tier", "2", "--brief", rec["brief"], "--label", "FX1", "--wait"]
    assert fleet.main(base + ["--timeout", "580"]) == 0
    assert rec["wait"] == [(["W1"], 580000)]
    assert fleet.main(base) == 0
    assert rec["wait"][-1] == (["W2"], 540000)


def test_spawn_brief_missing_file_exits_2(world, rec, capsys):
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "2", "--brief", str(world.proj / "nope.md")]) == 2
    assert capsys.readouterr().err.startswith("error: brief not found: ")
    assert not [c for c in world.fh.calls if c[0] == "create_workspace"]


def test_spawn_wait_needs_brief(world, rec, capsys):
    assert fleet.main(["spawn", "--wait"]) == 2
    assert "error: --wait needs --brief" in capsys.readouterr().err
    assert fleet.main(["spawn", "--brief", rec["brief"], "--timeout", "5"]) == 2
    assert "error: --timeout needs --wait" in capsys.readouterr().err


def test_spawn_brief_refused_with_dispatch(world, rec, capsys):
    assert fleet.main(["spawn", "--for-dispatch", "--brief", rec["brief"]]) == 2
    assert "error: --brief is for a plain spawn" in capsys.readouterr().err


def test_spawn_brief_send_failure_stops_worker(world, rec, monkeypatch, capsys):
    def boom(*a, **k): raise world.fh.HerdrError("agent_prompt_stalled", "x")
    monkeypatch.setattr(fleet_io, "send_brief", boom)
    monkeypatch.setattr(fleet_io, "hc", world.fh)
    capsys.readouterr()
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "2", "--brief", rec["brief"], "--label", "FX1"]) == 3
    assert "BLOCKED: W1 FX1 not sent (x)" in capsys.readouterr().out
    assert state(world, "W1") == "stopped"


def test_worker_fresh_pane_after_two_shell_failures(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(world, {1: ("agent_start_failed", MSG), 2: ("agent_start_failed", MSG)})
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W2"
    assert state(world, "W1") == "blocked" and state(world, "W2") == "ready"
    assert ("close_pane", "w6:p1") in world.fh.calls
    assert len(starts(world)) == 3 and len(pauses) == 1
    assert f"W1 startup: {MSG}; retried once; retrying in a fresh pane" in capsys.readouterr().err


def test_worker_blocks_after_fresh_pane_fails(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(world, {n: ("agent_start_failed", MSG) for n in (1, 2, 3, 4)})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith("BLOCKED: W2 account ") and line.endswith(f"startup: {MSG}; retried once; retried in a fresh pane after W1")
    assert len(starts(world)) == 4 and len(pauses) == 2


def test_lead_noshell_is_fleet_noshell():
    assert fleet_lead.NoShell is fleet.NoShell
