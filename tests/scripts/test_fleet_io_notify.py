# tests/scripts/test_fleet_io_notify.py
import json, sys
import pytest
from test_fleet_io import world, FakeHerdr, rec, user, assistant, transcript  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402


@pytest.fixture
def cw(world):
    world.fh.call = lambda args: (world.fh.calls.append(("call", args)), {})[1]
    return world


def renames(w): return [c[1] for c in w.fh.calls if c[0] == "call"]


def stop(w, wid, tr, t):
    with open(w.sd / "metrics.jsonl", "a") as f:
        f.write(json.dumps({"ev": "stop", "t": t, "agent_id": wid, "type": "x", "transcript": str(tr), "last": ""}) + "\n")


def test_send_labels_pane(cw):
    io.send(cw.sd, cw.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert ("call", ["pane", "rename", "w6:p1", "W1 T3"]) in cw.fh.calls


def test_finish_labels_reported(cw, tmp_path):
    io.send(cw.sd, cw.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = cw.clock.t[0]
    tr = tmp_path / "w1.jsonl"; transcript(tr, "Status: DONE")
    stop(cw, "W1", tr, sent + 10); cw.fh.states = [{"sl-proj-w1": "done"}]
    io.wait(cw.sd, ["W1"], 5000)
    assert ["pane", "rename", "w6:p1", "W1 T3 reported, waiting for coordinator"] in renames(cw)


def test_blocked_ui_labels(cw):
    io.send(cw.sd, cw.plan, "W2", ["T4"], "/sl/sl", "/sl")
    cw.fh.states = [{"sl-proj-w2": "blocked"}]
    io.wait(cw.sd, ["W2"], 5000)
    assert ["pane", "rename", "w6:p2", "W2 T4 BLOCKED-UI"] in renames(cw)


def test_label_failure_never_breaks_send(world, capsys):
    def boom(args): raise world.fh.HerdrError("no")
    world.fh.call = boom
    assert io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl") == "T3"
    assert "W1 T3 sent" in capsys.readouterr().out
    assert io.pane_label(world.sd, "W1", "x") is False
    assert io.pane_label(world.sd, "W9", "x") is False  # an unknown worker


def test_label_programming_errors_are_not_hidden(world):
    del type(world.fh).call  # hc without `call` (a wrong verb or a missing function) must surface
    try:
        with pytest.raises(AttributeError):
            io.pane_label(world.sd, "W1", "x")
    finally:
        type(world.fh).call = lambda self, args, timeout_ms=30000, env=None: (self.calls.append(("call", args)), {})[1]


def test_wait_any_returns_first(cw, tmp_path, capsys):
    io.send(cw.sd, cw.plan, "W1", ["T3"], "/sl/sl", "/sl"); io.send(cw.sd, cw.plan, "W2", ["T4"], "/sl/sl", "/sl"); sent = cw.clock.t[0]
    tr = tmp_path / "w1.jsonl"; transcript(tr, "Status: DONE")
    stop(cw, "W1", tr, sent + 10); cw.fh.states = [{"sl-proj-w1": "done", "sl-proj-w2": "working"}]
    out = io.wait(cw.sd, None, 60000, any_=True)
    assert len(out) == 1 and out[0]["id"] == "W1"
    assert capsys.readouterr().out.strip().splitlines()[-1] == "BUSY W2"
    assert json.loads((cw.sd / "fleet.json").read_text())["workers"]["W2"]["state"] == "busy"
    assert [c for c in cw.fh.calls if c[0] == "agent_states"] == [("agent_states",)]


def test_wait_any_cli_flag(world, monkeypatch):
    seen = {}
    monkeypatch.setattr(io, "wait", lambda *a, **k: seen.update(k))
    assert io.main(["wait", "--any", "--timeout", "5000"]) == 0
    assert seen["any_"] is True


def test_ready_k_first_turn(tmp_path):
    p = tmp_path / "a.jsonl"
    rec(p, user("Read /x/.superlite/prime.md, then reply READY"),
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "READY"}], "usage": {"input_tokens": 3, "cache_read_input_tokens": 12000, "cache_creation_input_tokens": 2400}}},
        user("# Task T1"),
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Status: DONE"}], "usage": {"input_tokens": 5, "cache_read_input_tokens": 40000}}})
    assert io.ready_k(str(p)) == 14.4
    q = tmp_path / "b.jsonl"
    rec(q, user("Read prime"), {"type": "assistant", "message": {"content": [{"type": "text", "text": "READY"}], "usage": {"input_tokens": 1000, "cache_read_input_tokens": 9000}}})
    assert io.ready_k(str(q)) == 10.0
    assert io.ready_k("/missing.jsonl") is None
    r = tmp_path / "c.jsonl"  # a tool pair inside the READY turn does not end it
    rec(r, user("Read prime"),
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}], "usage": {"input_tokens": 1000}}},
        user([{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]),
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "READY"}], "usage": {"input_tokens": 2000, "cache_read_input_tokens": 3000}}},
        user("# Task"), {"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}], "usage": {"input_tokens": 99000}}})
    assert io.ready_k(str(r)) == 5.0


def test_baseline_k_caches(world, tmp_path):
    tr = tmp_path / "w1.jsonl"
    rec(tr, user("Read prime"),
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "READY"}], "usage": {"input_tokens": 3, "cache_read_input_tokens": 12000, "cache_creation_input_tokens": 2400}}},
        user("# Task T1"), {"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}], "usage": {"input_tokens": 50000}}})
    stop(world, "W1", tr, 1500)
    assert io.baseline_k(world.sd, "W9") is None
    assert io.baseline_k(world.sd, "W1") == 14.4
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["baseline_k"] == 14.4
    tr.unlink()
    assert io.baseline_k(world.sd, "W1") == 14.4
    assert "baseline_k" not in json.loads((world.sd / "fleet.json").read_text())["workers"]["W2"]
    assert io.baseline_k(world.sd, "W2") is None
    assert "baseline_k" not in json.loads((world.sd / "fleet.json").read_text())["workers"]["W2"]


def test_baseline_k_uses_latest_stop_after_fleet_off(world, tmp_path):  # an old W1 stays in metrics.jsonl
    def tr_for(name, tokens):
        p = tmp_path / name
        rec(p, user("Read prime"), {"type": "assistant", "message": {"content": [{"type": "text", "text": "READY"}], "usage": {"input_tokens": tokens}}})
        return p
    stop(world, "W1", tr_for("old.jsonl", 10000), 1000)
    stop(world, "W1", tr_for("new.jsonl", 14400), 2000)
    assert io.baseline_k(world.sd, "W1") == 14.4
