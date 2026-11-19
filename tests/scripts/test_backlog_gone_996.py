"""The fleet 'panes are gone' notice asks the worker's own machine and skips reported workers (#996)."""
import json, sys, types
from pathlib import Path
import pytest
from test_backlog_run import bk, fleet_of, get, run, running  # noqa: F401
from test_fleet_remote_worker import world, started, record  # noqa: F401
import backlog_run as br  # noqa: E402
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402

REMOTE = {"name": "sl-r-w2", "state": "busy", "task": "T1", "sent": 3, "machine": "m1"}


def fake_listing(monkeypatch, result):
    seen = []
    def fake(sd, sync=True):
        seen.append((Path(sd), sync)); return result
    monkeypatch.setitem(sys.modules, "fleet_remote_worker", types.SimpleNamespace(states=fake))
    return seen


def later(monkeypatch):
    monkeypatch.setattr(br, "_now_ms", lambda: 5000 + br.GONE_MS)


def text_calls(bk):
    return [c for c in bk.calls if c[0] == "text"]


def test_holds_task_examples():
    assert br._holds_task({"state": "busy", "task": "T3", "sent": 7, "collected": 0}) is True
    assert br._holds_task({"state": "busy", "task": "T3", "sent": 7, "collected": 7}) is False
    assert br._holds_task({"state": "blocked", "task": None}) is False
    assert br._holds_task({"state": "ready", "task": None, "last_task": "T2"}) is False
    assert br._holds_task({"state": "busy", "task": "T3"}) is True
    assert br._holds_task({"state": "blocked", "task": "T4", "sent": 9, "collected": 3}) is True
    assert br._holds_task({"state": "stopped", "task": "T5", "sent": 1}) is False


def test_live_remote_worker_is_not_named(bk, capsys, monkeypatch):
    wt = running(bk); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2=dict(REMOTE))
    seen = fake_listing(monkeypatch, {"sl-r-w2": "working"})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1").get("gone_seen", {}) == {} and not text_calls(bk)
    assert seen and all(s == (wt / ".superlite", False) for s in seen)


def test_remote_worker_missing_on_its_machine_is_named(bk, capsys, monkeypatch):
    wt = running(bk); bk.states.update({"sl-m-W1": "working", "sl-r-w2": "working"})
    fleet_of(bk, wt, W2=dict(REMOTE))
    fake_listing(monkeypatch, {})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["gone_seen"] == {"W2": 5000}
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 worker panes gone: W2; lead W1 told\n")


def test_unreachable_machine_never_names_its_worker(bk, capsys, monkeypatch):
    wt = running(bk, gone_seen={"W2": 0}); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2=dict(REMOTE))
    fake_listing(monkeypatch, {"sl-r-w2": None})
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1").get("gone_seen", {}) == {}


def test_reported_worker_is_never_named(bk, capsys, monkeypatch):
    wt = running(bk, gone_seen={"W2": 0, "W6": 0}); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2={"name": "sl-l-w2", "state": "busy", "task": "T1", "sent": 4, "collected": 4},
             W6={"name": "sl-r-w6", "state": "busy", "task": "T6", "sent": 5, "collected": 5, "machine": "m1"})
    seen = fake_listing(monkeypatch, {})
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1").get("gone_seen", {}) == {} and seen == []


def test_ready_and_spawn_blocked_workers_are_never_named(bk, capsys, monkeypatch):
    wt = running(bk); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W7={"name": "sl-l-w7", "state": "ready", "last_task": "T2"}, W8={"name": "sl-l-w8", "state": "blocked"})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1").get("gone_seen", {}) == {}


def test_blocked_worker_with_a_task_is_named(bk, capsys, monkeypatch):
    wt = running(bk); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W3={"name": "sl-l-w3", "state": "blocked", "task": "T3", "sent": 2})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["gone_seen"] == {"W3": 5000}
    later(monkeypatch)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 worker panes gone: W3; lead W1 told\n")


def test_no_remote_listing_without_a_remote_candidate(bk, capsys, monkeypatch):
    wt = running(bk); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2={"name": "sl-l-w2", "state": "busy", "task": "T2", "sent": 1},
             W6={"name": "sl-r-w6", "state": "stopped", "task": "T6", "sent": 1, "machine": "m1"})
    def boom(sd, sync=True):
        raise AssertionError("remote listing without a remote candidate")
    monkeypatch.setitem(sys.modules, "fleet_remote_worker", types.SimpleNamespace(states=boom))
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["gone_seen"] == {"W2": 5000}


def test_states_without_sync_lists_and_never_syncs(world, monkeypatch):
    started(world)
    name = record(world)["name"]; world.fh.agent_map = {name: "done"}
    d = json.loads((world.sd / "fleet.json").read_text()); d["workers"]["W1"]["state"] = "busy"
    (world.sd / "fleet.json").write_text(json.dumps(d))
    seen = []
    monkeypatch.setattr(fr, "sync", lambda sd, wid: seen.append(wid) or 0)
    assert rw.states(world.sd, sync=False) == {name: "done"} and seen == []
    rw.states(world.sd); assert seen == ["W1"]
