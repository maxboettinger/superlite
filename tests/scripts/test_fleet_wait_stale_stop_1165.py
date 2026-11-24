# tests/scripts/test_fleet_wait_stale_stop_1165.py - a stop record that ended a turn which began before the latest send is not the answer to that send (#1165)
import json
from datetime import datetime, timezone
from pathlib import Path
from test_fleet_io import world, io, rec, user, assistant  # noqa: F401  (world is a fixture)
import fleet  # noqa: E402

REPORT = "Status: DONE\n```json\n" + json.dumps({"status": "DONE", "files": ["src/c.py"], "tests": "3 passed", "red": "", "findings": [], "summary": "ok"}) + "\n```"
NOTE = {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": "<task-notification>\n<task-id>a1</task-id>\n</task-notification>"}}


def at(e, secs):  # E with an ISO timestamp SECS seconds after the epoch
    return {**e, "timestamp": datetime.fromtimestamp(secs, timezone.utc).isoformat().replace("+00:00", "Z")}


def stops(world, tr, *ts):  # stop records at the given ms
    (world.sd / "metrics.jsonl").write_text("".join(json.dumps({"ev": "stop", "t": t, "agent_id": "W1", "type": "x", "transcript": str(tr), "last": "x"}) + "\n" for t in ts))


def sent(world):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); return world.clock.t[0]


def prompts(world):
    return [c for c in world.fh.calls if c[0] == "prompt"]


def test_stop_turn_examples(tmp_path):
    p = tmp_path / "t.jsonl"
    head = [at(user("# Task T13"), 10.0), at(assistant("Status: BLOCKED"), 11.0), at(NOTE, 20.0), at(assistant("Status: BLOCKED (notification)"), 21.0)]
    rec(p, *head, at(user("Ruling for T13 ..."), 21.218))
    assert io.stop_turn(p, 21200) == "after"
    rec(p, *head)
    assert io.stop_turn(p, 21200) == "note"
    rec(p, at(user("# Task T13"), 10.0), at(assistant("Status: DONE"), 11.0))
    assert io.stop_turn(p, 11500) == "answer"
    assert io.stop_turn("/missing.jsonl", 5) == "answer"
    rec(p, user("task"), assistant("x"), NOTE)
    assert io.stop_turn(p, 5) == "answer" and io.NOTE_MS == 3000


def test_run_of_machine_state_dir_needs_remote_parent():
    assert io.run_of({"machine": "m1", "state_dir": "/r/a/.superlite"}) == Path("/r/a/.superlite")
    assert io.run_of({"machine": "m1", "state_dir": "/r/a/.superlite/remote/W9"}) == Path("/r/a/.superlite")


def field(world, tmp_path):  # the field shape: a notification turn, the send, its repeated answer, the stop, then the queued send lands
    s = sent(world); tr = tmp_path / "w1.jsonl"; base = s / 1000
    items = [at(user("# Task T3"), base - 100), at(assistant("Status: BLOCKED"), base - 90), at(NOTE, base - 3), at(assistant("Status: BLOCKED (notification)"), base + 0.7), at(user("Ruling for T3 ..."), base + 0.753)]
    rec(tr, *items); stops(world, tr, s + 700)
    return s, tr, items


def test_wait_skips_stop_before_queued_send(world, tmp_path, capsys):
    s, tr, items = field(world, tmp_path); world.fh.states = [{"sl-proj-w1": "working"}]
    capsys.readouterr(); n = len(prompts(world))  # the send's own prompt is not an ask
    assert io.wait(world.sd, ["W1"], 30000) == [] and "TIMEOUT W1" in capsys.readouterr().out
    assert not (world.sd / "fleet" / "reports" / "T3.md").exists() and len(prompts(world)) == n
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "busy"
    base = s / 1000
    rec(tr, *items, at(assistant(REPORT), base + 59)); stops(world, tr, s + 700, s + 60000)
    out = io.wait(world.sd, ["W1"], 30000)
    assert [(r["id"], r["status"]) for r in out] == [("W1", "DONE")] and "W1 T3 DONE" in capsys.readouterr().out


def test_wait_holds_note_stop_then_takes_it(world, tmp_path, capsys):
    s = sent(world); tr = tmp_path / "w1.jsonl"; base = s / 1000
    rec(tr, at(user("# Task T3"), base + 0.1), at(assistant(REPORT), base + 1), at(NOTE, base + 5), at(assistant("Background run done."), base + 6))
    stops(world, tr, s + 6100); world.fh.states = [{"sl-proj-w1": "working"}]
    assert io.wait(world.sd, ["W1"], io.NOTE_MS - 1000) == []
    t0 = world.clock.t[0]
    out = io.wait(world.sd, ["W1"], 60000)
    assert [r["status"] for r in out] == ["DONE"] and world.clock.t[0] - t0 >= io.NOTE_MS and "W1 T3 DONE" in capsys.readouterr().out


def test_wait_takes_repeated_blocked_answer(world, tmp_path):
    s = sent(world); tr = tmp_path / "w1.jsonl"; base = s / 1000
    rec(tr, at(NOTE, base - 3), at(assistant("Status: BLOCKED - old"), base - 2), at(user("# Task T3"), base + 0.1), at(assistant("Status: BLOCKED - again"), base + 0.5))
    stops(world, tr, s + 600); world.fh.states = [{"sl-proj-w1": "working"}]
    t0 = world.clock.t[0]
    out = io.wait(world.sd, ["W1"], 60000)
    assert [r["status"] for r in out] == ["BLOCKED"] and world.clock.t[0] == t0


def test_lag_window_unchanged(world, tmp_path, capsys):
    s = sent(world); tr = tmp_path / "w1.jsonl"; base = s / 1000
    rec(tr, at(user("# Task T3"), base + 0.1)); stops(world, tr, s + 1000); world.fh.states = [{"sl-proj-w1": "done"}]
    out = io.wait(world.sd, ["W1"], 60000)
    assert out[0]["status"] == "UNKNOWN" and capsys.readouterr().out.splitlines()[-1].endswith("(transcript unread)")


def test_ended_stop_skips_stale(world, tmp_path):
    s, tr, items = field(world, tmp_path)
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert fleet._ended_stop(world.sd, "W1", w) is None
    rec(tr, *items[:2]); stops(world, tr, s + 700)
    assert fleet._ended_stop(world.sd, "W1", w)["t"] == s + 700


def test_wait_reads_stop_turn_once_per_stop_record(world, tmp_path, monkeypatch):  # a pending worker with an unreported answer stop is not re-read each poll
    s = sent(world); tr = tmp_path / "w1.jsonl"; base = s / 1000
    rec(tr, at(user("# Task T3"), base + 0.1), at(assistant("still thinking, no status"), base + 1))
    stops(world, tr, s + 1500); world.fh.states = [{"sl-proj-w1": "working"}]
    calls = []; real = io.stop_turn
    monkeypatch.setattr(io, "stop_turn", lambda *a: calls.append(a) or real(*a))
    io.wait(world.sd, ["W1"], 20000)
    assert len(calls) == 1


def test_stop_turn_whole_second_stop_reads_as_end_of_that_second(tmp_path):  # the whole-second `date +%s000` fallback of capture-worker-stop
    p = tmp_path / "t.jsonl"
    rec(p, at(user("# Task T13"), 10.4), at(assistant("Status: DONE"), 10.7))
    assert io.stop_turn(p, 10000) == "answer"
    rec(p, at(user("# Task T13"), 21.218))
    assert io.stop_turn(p, 21200) == "after"
