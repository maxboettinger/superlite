"""#769: backlog wait re-prompts a live lead that is silent (no shell child, no session-file write, no stop record) once, then parks it."""
import json
import os
import re
import sys
import types

import pytest

from backlog_fixtures import Q, batch as b
from test_backlog_run import bk, put, get, run, running  # noqa: F401
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402
import state  # noqa: E402

SID = "0b0c4d1e-aaaa-bbbb-cccc-000000000769"
T0 = 1_700_000_000  # transcript mtime, epoch seconds
MIN = 60_000
SNAP = {"id": "t-1", "cache_ttl": {}, "workers": {}}


def _slug(p):
    return re.sub(r"[^A-Za-z0-9]", "-", str(p))  # fleet_io.project_dir's rule


@pytest.fixture
def idle(bk, monkeypatch, tmp_path):
    wt = running(bk)
    cfg = tmp_path / "cfg"
    tr = cfg / "projects" / _slug(wt) / f"{SID}.jsonl"
    tr.parent.mkdir(parents=True)
    tr.write_text("{}\n")
    os.utime(tr, (T0, T0))
    bk.fleets[str(bk.sd)] = {"workers": {"W1": {"name": "sl-m-W1", "role": "lead", "worktree": str(wt),
                                                 "launch": {"cwd": str(wt), "env": {"CLAUDE_CONFIG_DIR": str(cfg)}}}}}
    hc = sys.modules["fleet"].hc
    monkeypatch.setattr(hc, "agents", lambda: [{"name": "sl-m-W1", "agent_status": "done", "agent_session": {"value": SID}}], raising=False)
    monkeypatch.setattr(hc, "session_of", lambda row: (row.get("agent_session") or {}).get("value"), raising=False)
    monkeypatch.setattr(sys.modules["fleet_io"], "project_dir", _slug, raising=False)
    ns = types.SimpleNamespace(wt=wt, tr=tr, holder=None, procs=[(os.getpid() + 100000, os.getpid(), 0, "caffeinate")])
    monkeypatch.setattr(sys.modules["ship_lock"], "holder", lambda p: ns.holder, raising=False)
    monkeypatch.setitem(sys.modules, "machine_load", types.SimpleNamespace(_ps=lambda: ns.procs))
    (state.home() / "sessions").mkdir(parents=True, exist_ok=True)
    (state.home() / "sessions" / SID).write_text(f"{wt / '.superlite'}\n{os.getpid()}\n")
    (wt / ".superlite" / "run-config.json").write_text(json.dumps({**SNAP, "lead": {"idle_minutes": 10}}))
    monkeypatch.setattr(br, "_now_ms", lambda: T0 * 1000 + 12 * MIN)
    return ns


def _texts(bk):
    return [c[1] for c in bk.calls if c[0] == "text"]


def test_silent_lead_is_reprompted_once_then_parked(bk, idle, capsys, monkeypatch):
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 idle 12 min: re-prompted\n")
    x = get(bk, "B1")
    assert x["state"] == "running" and x["idle_reprompted"] is True and x["idle_at"] == T0 * 1000 + 12 * MIN
    t = _texts(bk)
    assert len(t) == 1 and t[0][:3] == ["send", "W1", "--text"] and "12 min" in t[0][3] and "Status:" in t[0][3]
    assert t[0][4:] == ["--plan", str(bk.sd)]
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    monkeypatch.setattr(br, "_now_ms", lambda: T0 * 1000 + 23 * MIN)
    assert run(capsys, "wait", "--timeout", "0") == (
        0, "B1 parked: idle 11 min after an idle re-prompt (no child process, no session-file write, no stop event)\n")
    assert get(bk, "B1")["state"] == "parked" and ("stop", ["W1"]) in bk.calls and len(_texts(bk)) == 1


def test_a_write_after_the_reprompt_starts_a_new_idle_period(bk, idle, capsys, monkeypatch):
    assert run(capsys, "wait", "--timeout", "0")[1] == "B1 idle 12 min: re-prompted\n"
    os.utime(idle.tr, (T0 + 20 * 60, T0 + 20 * 60))
    monkeypatch.setattr(br, "_now_ms", lambda: T0 * 1000 + 29 * MIN)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    monkeypatch.setattr(br, "_now_ms", lambda: T0 * 1000 + 30 * MIN)
    assert run(capsys, "wait", "--timeout", "0")[1].startswith("B1 parked: idle 10 min after an idle re-prompt")


@pytest.mark.parametrize("now_min,want", [(9, "TIMEOUT\n"), (10, "B1 idle 10 min: re-prompted\n")])
def test_default_idle_time_is_ten_minutes(bk, idle, capsys, monkeypatch, now_min, want):
    (idle.wt / ".superlite" / "run-config.json").write_text(json.dumps({**SNAP, "lead": {}}))
    monkeypatch.setattr(br, "_now_ms", lambda: T0 * 1000 + now_min * MIN)
    assert run(capsys, "wait", "--timeout", "0") == (0, want)


@pytest.mark.parametrize("case", ["shell child", "login shell child", "fresh write", "subagent write", "ship lock", "off",
                                  "no pid", "dead pid", "no transcript", "no herdr row", "unanswered", "lock unreadable"])
def test_lead_that_works_or_cannot_be_read_is_never_idle(bk, idle, capsys, monkeypatch, case):
    sess = state.home() / "sessions" / SID
    if case == "shell child":
        idle.procs = [(os.getpid() + 100000, os.getpid(), 0, "/bin/zsh")]
    elif case == "login shell child":
        idle.procs = [(os.getpid() + 100000, os.getpid(), 0, "-bash")]
    elif case == "fresh write":
        os.utime(idle.tr, (T0 + 300, T0 + 300))
    elif case == "subagent write":
        sub = idle.tr.parent / SID / "subagents" / "agent-1.jsonl"
        sub.parent.mkdir(parents=True)
        sub.write_text("{}\n")
        os.utime(sub, (T0 + 300, T0 + 300))
    elif case == "ship lock":
        idle.holder = {"batch": "B1", "lead": "W1"}
    elif case == "off":
        (idle.wt / ".superlite" / "run-config.json").write_text(json.dumps({**SNAP, "lead": {"idle_minutes": 0}}))
    elif case == "no pid":
        sess.unlink()
    elif case == "dead pid":
        sess.write_text(f"{idle.wt / '.superlite'}\n99999999\n")
    elif case == "no transcript":
        idle.tr.unlink()
    elif case == "no herdr row":
        monkeypatch.setattr(sys.modules["fleet"].hc, "agents", lambda: [])
    elif case == "unanswered":
        bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"decisions": [{"questions": [{"question": "Which?"}]}], "answers": {}}))
    elif case == "lock unreadable":
        def boom(p):
            raise OSError("unreadable")
        monkeypatch.setattr(sys.modules["ship_lock"], "holder", boom)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert not [c for c in bk.calls if c[0] in ("text", "stop")]
    assert not get(bk, "B1").get("idle_reprompted")


@pytest.mark.parametrize("owner,want", [(SID, "B1 idle 12 min: re-prompted\n"), ("another-session", "TIMEOUT\n")])
def test_lead_pid_falls_back_to_its_fleet_owner_of_the_same_session(bk, idle, capsys, owner, want):
    (state.home() / "sessions" / SID).unlink()
    (idle.wt / ".superlite" / "fleet.json").write_text(json.dumps({"on": True, "workers": {}, "owner_session": owner, "owner_pid": os.getpid()}))
    assert run(capsys, "wait", "--timeout", "0") == (0, want)


def test_failed_send_parks_at_once(bk, idle, capsys, monkeypatch):
    monkeypatch.setattr(sys.modules["fleet_io"], "main", lambda argv: bk.calls.append(("text", argv)) or 1)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: idle 12 min: re-prompt not delivered\n")


def test_start_and_answer_reset_the_idle_keys(bk, capsys, tmp_path):
    wt = running(bk, idle_reprompted=True, idle_at=4000)
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    (wt / ".superlite" / "question.json").write_text(json.dumps(Q))
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {"Keep the v1 API?": "Drop"}, "by": "user"}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert get(bk, "B1")["idle_reprompted"] is False and get(bk, "B1")["idle_at"] == 0
    put(bk, b("B2", ["b.py"], idle_reprompted=True, idle_at=4000))
    assert run(capsys, "start", "B2")[0] == 0
    assert get(bk, "B2")["idle_reprompted"] is False and get(bk, "B2")["idle_at"] == 0
