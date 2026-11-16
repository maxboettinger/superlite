# tests/scripts/test_telemetry_fleet_933.py: fleet on/off, send, worker stop and review events (#933)
import json, sys
from datetime import datetime, timezone
from test_fleet_io import world, FakeHerdr  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as io  # noqa: E402
import telemetry  # noqa: E402


def lines(kind): return [e for e in telemetry.read_events() if e["kind"] == kind]


def iso(sec): return datetime.fromtimestamp(sec, timezone.utc).isoformat()


def usage_transcript(path, sent_s):
    def asst(i, text, ts, tools=0):
        blocks = [{"type": "text", "text": text}] + [{"type": "tool_use", "id": f"t{i}{k}", "name": "Bash", "input": {}} for k in range(tools)]
        return {"type": "assistant", "timestamp": iso(ts), "message": {"id": f"m{i}", "model": "claude-sonnet-5-5", "content": blocks,
                "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10}}}
    recs = [{"type": "user", "timestamp": iso(sent_s - 500), "message": {"content": "task"}},
            asst(0, "old turn before the send", sent_s - 400),
            {"type": "user", "timestamp": iso(sent_s + 1), "message": {"content": "task"}},
            asst(1, "Status: DONE", sent_s + 5, tools=2)]
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))


def finish(world, tmp_path, text, label="T3", wid="W1"):
    sent = world.clock.t[0]
    tr = tmp_path / "w.jsonl"; usage_transcript(tr, sent / 1000)
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 10, "agent_id": wid, "type": "x", "transcript": str(tr), "last": text}) + "\n")
    world.fh.states = [{"sl-proj-w1": "done"}]
    return sent


def test_kind_fleet_on_off(tmp_path, capsys):
    plan = tmp_path / "docs" / "p.md"
    assert fleet.main(["on", "--accounts", "a1,a2", "--plan", str(plan)]) == 0
    assert fleet.main(["off", "--plan", str(plan)]) == 0
    ev = lines("fleet")
    assert [e["on"] for e in ev] == [True, False]
    assert ev[0]["accounts"] == ["a1", "a2"] and ev[1]["accounts"] == ["a1", "a2"]
    assert all(telemetry.validate(e) == [] for e in ev)


def test_kind_dispatch_fleet_send(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3", "T4"], "/sl/sl", "/sl")
    ev = lines("dispatch")
    assert [e["task"] for e in ev] == ["T3", "T4"]
    for e in ev:
        assert telemetry.validate(e) == []
        assert (e["role"], e["agent_type"], e["model"], e["tier"], e["account"], e["label"], e["machine"]) == \
            ("implementer", "superlite:implementer", "sonnet", "sonnet", "claude1", "T3,T4", None)
    b = tmp_path / "b.md"; b.write_text("do it")
    io.send_brief(world.sd, "W2", b, "brief1")
    last = lines("dispatch")[-1]
    assert last["label"] == "brief1" and last["task"] is None and telemetry.validate(last) == []


def test_kind_agent_stop_fleet_worker(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    sent = finish(world, tmp_path, "Status: DONE")
    out = io.wait(world.sd, ["W1"], 5000)
    assert out[0]["status"] == "DONE"
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert e["status"] == "DONE" and e["task"] == "T3" and e["role"] == "implementer" and e["account"] == "claude1" and e["machine"] is None
    assert e["duration_s"] == (world.clock.t[0] - sent) / 1000 or e["duration_s"] >= 0
    assert e["tokens"] == {"in": 100, "out": 20, "cache_read": 50, "cache_write": 10} and e["tool_calls"] == 2 and e["cost_usd"] > 0
    assert lines("review") == []


def test_kind_review_fleet_final(world, tmp_path):
    d = json.loads((world.sd / "fleet.json").read_text())
    d["workers"]["W1"].update(role="final-reviewer", one_turn=True)
    (world.sd / "fleet.json").write_text(json.dumps(d))
    io.send_brief(world.sd, "W1", tmp_path / "b.md" if (tmp_path / "b.md").write_text("x") else None, "FR2")
    finish(world, tmp_path, "Verdict: APPROVED")
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": world.clock.t[0] + 10, "agent_id": "W1", "type": "x", "transcript": str(tmp_path / "w.jsonl"), "last": "Verdict: APPROVED"}) + "\n")
    (tmp_path / "w.jsonl").write_text(json.dumps({"type": "user", "message": {"content": "task"}}) + "\n" + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Verdict: APPROVED"}]}}) + "\n")
    io.wait(world.sd, ["W1"], 5000)
    (e,) = lines("review")
    assert telemetry.validate(e) == []
    assert (e["review_kind"], e["verdict"], e["findings"], e["round"]) == ("final", "APPROVED", 0, 2)


def test_fleet_finish_twice_one_line(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    finish(world, tmp_path, "Status: DONE")
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    io._finish(world.sd, "W1", w, "Status: DONE", "transcript")
    io._finish(world.sd, "W1", w, "Status: DONE", "transcript")
    assert len(lines("agent_stop")) == 1


def test_fleet_telemetry_failure_keeps_output(world, capsys, monkeypatch):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    want = capsys.readouterr().out
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl")
    base = capsys.readouterr().out
    def boom(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr(telemetry, "emit", boom)
    monkeypatch.setattr(telemetry, "count", boom)
    d = json.loads((world.sd / "fleet.json").read_text())
    d["workers"]["W1"].update(state="ready", task=None); (world.sd / "fleet.json").write_text(json.dumps(d))
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert capsys.readouterr().out == want
    assert base == "W2 T4 sent\n"
