# tests/scripts/test_fleet_io_b87.py: slow Herdr reply retry, own_stop, lead brief resend (B87 T3)
import json
import os
import pytest
from test_fleet_io import io, world  # noqa: F401

pytestmark = pytest.mark.skipif(os.environ.get("SUPERLITE_REAL") == "1", reason="scripted herdr replies")
SLOW = ("timeout", "timed out waiting for app response after 5000 ms")


def script(world, *outcomes, state=None):
    class Err(world.fh.HerdrError):
        def __init__(self, code, message=""):
            super().__init__(f"{code}: {message}")
            self.code, self.message = code, message
    records, queue = [], list(outcomes)

    def prompt(name, text, until, timeout_ms):
        records.append(text)
        o = queue.pop(0)
        if o == "ok":
            return "working"
        raise Err(*o)

    def agent_state(name):
        if isinstance(state, Exception) or state is None:
            raise Err("timeout", "no state")
        return state
    world.fh.prompt, world.fh.agent_state = prompt, agent_state
    return records


def worker(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def test_send_slow_reply_resent_once(world, capsys):
    records = script(world, SLOW, "ok", state="idle")
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert "W1 T3 sent" in capsys.readouterr().out
    assert len(records) == 2 and records[0] == records[1]
    assert worker(world)["state"] == "busy" and worker(world)["task"] == "T3"


def test_send_slow_reply_that_landed_not_resent(world):
    records = script(world, SLOW, state="working")
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert len(records) == 1 and worker(world)["state"] == "busy"


def test_send_brief_slow_twice_propagates(world):
    records = script(world, SLOW, SLOW, state=None)
    with pytest.raises(world.fh.HerdrError):
        io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert len(records) == 2 and worker(world)["state"] == "ready"


def test_send_text_stall_resent(world):
    records = script(world, ("agent_prompt_stalled", "x"), "ok")
    io.send_text(world.sd, "W1", "hello")
    assert len(records) == 2 and records[0] == records[1]


def test_own_stop():
    w = {"worktree": "/wt/b1"}
    assert io.own_stop({"transcript": "/u/p/-wt-b1/s.jsonl"}, w) is True
    assert io.own_stop({"transcript": "/u/p/-tmp-x-scratchpad/s.jsonl"}, w) is False
    assert io.own_stop({}, w) is True
    assert io.own_stop({"transcript": "/u/p/-x/s.jsonl"}, {}) is True
    assert io.own_stop({"transcript": "/u/p/-x/s.jsonl"}, None) is True
    assert io.project_dir("/Users/a/.claude/w-1") == "-Users-a--claude-w-1"


def lead(world, last_status):
    fj = json.loads((world.sd / "fleet.json").read_text())
    lsd = world.proj / "wt" / ".superlite"
    (lsd / "briefs").mkdir(parents=True)
    (lsd / "briefs" / "lead.md").write_text("brief")
    fj["workers"]["W1"].update({"role": "lead", "worktree": "/wt/b1", "lead_sd": str(lsd), "sent": 50})
    (world.sd / "fleet.json").write_text(json.dumps(fj))
    rows = [{"ev": "stop", "t": 100, "agent_id": "W1", "transcript": "/u/p/-wt-b1/s.jsonl", "last": last_status},
            {"ev": "stop", "t": 200, "agent_id": "W1", "transcript": "/u/p/-tmp-x-scratchpad/s.jsonl", "last": "READY"}]
    (world.sd / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return lsd


def test_latest_stop_skips_child_session_of_lead(world):
    lead(world, "Status: DONE")
    assert io.latest_stop(world.sd, "W1", 0)["t"] == 100
    assert io.latest_stop(world.sd, "W2", 0) is None
    fj = json.loads((world.sd / "fleet.json").read_text())
    fj["workers"]["W1"].pop("role")
    fj["workers"]["W1"].pop("worktree")
    (world.sd / "fleet.json").write_text(json.dumps(fj))
    assert io.latest_stop(world.sd, "W1", 0)["t"] == 200


def test_latest_stop_keeps_stops_of_non_lead_worker_with_worktree(world):
    lead(world, "Status: DONE")
    fj = json.loads((world.sd / "fleet.json").read_text())
    fj["workers"]["W1"].pop("role")
    (world.sd / "fleet.json").write_text(json.dumps(fj))
    assert io.latest_stop(world.sd, "W1", 0)["t"] == 200


def test_send_text_resends_brief_after_ready_stop(world, capsys):
    lsd = lead(world, "READY")
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records == [io.fleet_report.brief_message("lead", str((lsd / "briefs" / "lead.md").resolve()))]
    assert "W1 brief resent (its last stop said only READY)" in capsys.readouterr().out


def test_send_text_free_text_after_done_stop(world):
    lead(world, "Status: DONE")
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records[0].startswith("go on\n\n")
