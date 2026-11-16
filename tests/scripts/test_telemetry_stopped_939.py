# tests/scripts/test_telemetry_stopped_939.py: a fleet worker stopped on purpose writes one agent_stop STOPPED line; fleet-worker agent_stop lines carry agent_session (#939)
import json, sys
from test_fleet import world, FakeHerdr  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import telemetry  # noqa: E402

SID = "0b8c1d2e-3f40-4a5b-9c6d-7e8f90a1b2c3"


def lines(kind): return [e for e in telemetry.read_events() if e["kind"] == kind]


def seed(w, **workers):
    d = fleet.fs.default(); d.update(on=True, workspace_id="w6", root_pane="w6:p1", accounts=["claude1"], next=len(workers) + 1)
    d["workers"] = {wid: {"name": f"sl-proj-{wid.lower()}", "pane_id": f"w6:p{i + 1}", "account": "claude1", "agent": "superlite:implementer",
                          "tier": "sonnet", "state": "ready", "task": None, "started": 1000, **kw} for i, (wid, kw) in enumerate(workers.items())}
    fleet.fs.save(w.sd, d)


def test_kind_agent_stop_stopped_once(world):
    seed(world, W1={"session": SID}, W2={})
    assert fleet.stop(world.sd, ["W1"]) == ["W1"]
    assert fleet.stop(world.sd, ["W1"]) == []
    assert fleet.stop(world.sd, all_=True) == ["W2"]
    a, b = lines("agent_stop")
    assert telemetry.validate(a) == [] and telemetry.validate(b) == []
    assert (a["status"], a["task"], a["role"], a["model"], a["account"], a["machine"], a["effort"], a["duration_s"]) == \
        ("STOPPED", None, "implementer", "sonnet", "claude1", None, None, None)
    assert (a["tokens"], a["cost_usd"], a["tool_calls"], a["agent_session"]) == (None, None, None, SID)
    assert b["status"] == "STOPPED" and "agent_session" not in b
    assert list(a)[-1] == "agent_session"


def test_kind_agent_stop_stopped_busy_worker(world, monkeypatch):
    monkeypatch.setattr(fleet_io, "now_ms", lambda: 2_005_000)
    seed(world, W1={"state": "busy", "task": "T3,T4", "sent": 2_000_000, "role": "package-reviewer", "model": "opus", "session": SID})
    fleet.stop(world.sd, ["W1"])
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert (e["status"], e["task"], e["role"], e["model"], e["duration_s"], e["agent_session"]) == ("STOPPED", "T3", "package-reviewer", "opus", 5.0, SID)
    assert lines("review") == []


def test_kind_agent_stop_stopped_fleet_off(world):
    seed(world, W1={"session": SID}, W2={"state": "stopped", "dead": True, "session": "other"})
    assert fleet.main(["off"]) == 0
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and (e["status"], e["agent_session"]) == ("STOPPED", SID)


def test_kind_agent_stop_dead_carries_agent_session(world):
    seed(world, W1={"session": SID})
    fleet.mark_dead(world.sd, "W1")
    fleet.stop(world.sd, all_=True)
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and (e["status"], e["agent_session"]) == ("DEAD", SID)


def test_kind_agent_stop_report_carries_agent_session(world):
    seed(world, W1={"state": "busy", "task": "T3", "sent": 1, "session": SID})
    stale = {k: v for k, v in fleet.fs.load(world.sd)["workers"]["W1"].items() if k != "session"}
    fleet_io._tel_finish(world.sd, "W1", stale, {"status": "DONE", "findings": []}, "T3")
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and (e["status"], e["task"], e["agent_session"]) == ("DONE", "T3", SID)


def test_kind_agent_stop_no_session_key_left_out(world):
    seed(world, W1={"session": ""})
    fleet.stop(world.sd, ["W1"])
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and "agent_session" not in e


def test_validate_rejects_other_unknown_keys():
    line = telemetry._build("agent_stop", None, None, None, {"status": "STOPPED", "agent_session": SID})
    assert telemetry.validate(line) == []
    assert telemetry.validate({**line, "worker_session": SID}) == ["agent_stop: unexpected worker_session"]
    run = telemetry._build("tests", None, None, None, {"mode": "fast", "agent_session": SID})
    assert "agent_session" not in run


def test_stop_fails_open(world, monkeypatch):
    def boom(*a, **k): raise SystemExit(3)
    monkeypatch.setattr(telemetry, "emit", boom)
    seed(world, W1={"session": SID})
    assert fleet.stop(world.sd, ["W1"]) == ["W1"]
    assert fleet.fs.load(world.sd)["workers"]["W1"]["state"] == "stopped"


def test_kind_agent_stop_stopped_off_switch(world, monkeypatch):
    monkeypatch.setenv("SUPERLITE_TELEMETRY", "0")
    seed(world, W1={"session": SID})
    fleet.stop(world.sd, ["W1"])
    assert lines("agent_stop") == []


def test_docs_name_stopped_and_agent_session():
    doc = (SCRIPTS.parents[2] / "docs" / "telemetry.md").read_text(encoding="utf-8")
    assert "`STOPPED` when superlite stops a fleet worker on purpose" in doc
    assert "`agent_session` (kind `agent_stop`" in doc
    row = next(l for l in doc.splitlines() if l.startswith("| `agent_stop` |"))
    assert "`fleet_remote_worker.py`" in row
