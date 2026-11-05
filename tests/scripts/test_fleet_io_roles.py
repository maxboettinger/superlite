# tests/scripts/test_fleet_io_roles.py
import json, sys, types
import pytest
from test_fleet_io import assistant, io, rec, user, world  # noqa: F401  (world is a fixture)

FINDING = {"file": "src/c.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1}

def setw(world, wid, **kw):
    p = world.sd / "fleet.json"; data = json.loads(p.read_text()); data["workers"][wid].update(kw); p.write_text(json.dumps(data))

def worker(world, wid):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]

def stop_record(world, wid, transcript):
    with open(world.sd / "metrics.jsonl", "a") as f:
        f.write(json.dumps({"ev": "stop", "t": world.clock.t[0] + 10, "agent_id": wid, "type": "x", "transcript": str(transcript), "last": ""}) + "\n")

def brief(world, name, text="x\n"):
    p = world.sd / "briefs" / name; p.parent.mkdir(exist_ok=True); p.write_text(text); return p

@pytest.fixture
def stopped(monkeypatch):
    seen = []
    monkeypatch.setattr(io, "_stop_worker", lambda sd, wid: seen.append(wid), raising=False)
    return seen

def test_send_brief_marks_busy_and_prompts_the_role_message(world, capsys):
    setw(world, "W2", role="fixer", one_turn=True)
    b = brief(world, "fix-F-T3-1.md")
    assert io.send_brief(world.sd, "W2", str(b)) == "fix-F-T3-1"
    name, text, until = [c for c in world.fh.calls if c[0] == "prompt"][-1][1:]
    assert name == "sl-proj-w2" and until == ["working"] and text.startswith(f"Read {b.resolve()} and do what it says.")
    w = worker(world, "W2")
    assert (w["state"], w["task"], w["sent"]) == ("busy", "fix-F-T3-1", world.clock.t[0])
    assert "W2 fix-F-T3-1 sent" in capsys.readouterr().out

def test_send_brief_cli_label_and_missing_file(world, capsys):
    b = brief(world, "wave0.md", "skeleton\n")
    assert io.main(["send", "W1", "--brief", str(b), "--label", "T0"]) == 0
    assert worker(world, "W1")["task"] == "T0" and "W1 T0 sent" in capsys.readouterr().out
    pool = json.loads((world.sd / "pool.json").read_text())["agents"][0]
    assert pool["busy"] is True and pool["current"] == "T0"
    assert io.main(["send", "W2", "--brief", str(world.sd / "briefs" / "nope.md")]) == 2
    assert "brief not found" in capsys.readouterr().err and worker(world, "W2")["state"] == "ready"

def test_final_reviewer_report_becomes_json_and_worker_stops(world, tmp_path, capsys, stopped):
    setw(world, "W2", role="final-reviewer", one_turn=True, agent="superlite:final-reviewer")
    io.send_brief(world.sd, "W2", str(brief(world, "review-packet.md")), "FR1")
    tr = tmp_path / "w2.jsonl"
    body = {"status": "CHANGES_REQUESTED", "files": [], "tests": "", "findings": [FINDING], "summary": "1 finding"}
    rec(tr, user("review"), assistant("Verdict: CHANGES_REQUESTED\nsrc/c.py:12 - off by one - use <= - tier 1\nChecked:\nT3 diff: read\n```json\n" + json.dumps(body) + "\n```"))
    stop_record(world, "W2", tr); world.fh.states = [{"sl-proj-w2": "done"}]
    out = io.wait(world.sd, ["W2"], 5000)
    jp = world.sd / "fleet" / "reports" / "FR1.json"
    assert out[0]["status"] == "CHANGES_REQUESTED" and out[0]["findings"] == 1 and out[0]["report"] == str(jp)
    assert f"W2 FR1 CHANGES_REQUESTED findings=1 {jp}" in capsys.readouterr().out
    data = json.loads(jp.read_text())
    assert data["findings"] == [FINDING] and data["valid"] is True and (data["id"], data["label"], data["role"]) == ("W2", "FR1", "final-reviewer")
    assert data["report"] == str(world.sd / "fleet" / "reports" / "FR1.md") and stopped == ["W2"]

def test_implementer_line_gains_findings_and_json_but_keeps_running(world, tmp_path, capsys, stopped):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("Status: DONE\nFiles: src/c.py"))
    stop_record(world, "W1", tr); world.fh.states = [{"sl-proj-w1": "done"}]
    io.wait(world.sd, ["W1"], 5000)
    jp = world.sd / "fleet" / "reports" / "T3.json"
    assert f"W1 T3 DONE findings=0 {jp}" in capsys.readouterr().out
    assert json.loads(jp.read_text())["valid"] is False and (world.sd / "fleet" / "reports" / "T3.md").read_text() == "Status: DONE\nFiles: src/c.py"
    assert stopped == [] and worker(world, "W1")["state"] == "ready"

def test_unknown_report_keeps_the_worker(world, tmp_path, capsys, stopped):
    setw(world, "W2", role="fixer", one_turn=True)
    io.send_brief(world.sd, "W2", str(brief(world, "b.md")))
    tr = tmp_path / "w2.jsonl"; rec(tr, user("fix"), assistant("I looked at it."))
    stop_record(world, "W2", tr); world.fh.states = [{"sl-proj-w2": "done"}]
    io.wait(world.sd, ["W2"], 5000)
    assert "W2 b UNKNOWN findings=0" in capsys.readouterr().out and stopped == []

def test_screen_fallback_takes_status_but_no_json(world, capsys, stopped):
    setw(world, "W2", role="research", one_turn=True)
    io.send_brief(world.sd, "W2", str(brief(world, "r1.md")))
    world.fh.screen = 'Status: DONE\n```json\n{"status": "BLOCKED", "files": [], "tests": "", "findings": [], "summary": ""}\n```\n'
    world.fh.states = [{"sl-proj-w2": "idle"}]
    io.wait(world.sd, ["W2"], 60000)
    out = capsys.readouterr().out
    assert "W2 r1 DONE findings=0" in out and out.rstrip().endswith("(screen)") and stopped == ["W2"]

def test_text_answer_marks_busy_so_a_bare_wait_waits(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("Status: NEEDS_CONTEXT - which API?"))
    stop_record(world, "W1", tr); world.fh.states = [{"sl-proj-w1": "done"}]
    io.wait(world.sd, ["W1"], 5000)
    world.clock.t[0] += 1000
    assert io.main(["send", "W1", "--text", "use v2"]) == 0
    w = worker(world, "W1")
    assert (w["state"], w["task"], w["sent"]) == ("busy", "T3", world.clock.t[0])
    rec(tr, user("task"), assistant("Status: NEEDS_CONTEXT - which API?"), user("use v2"), assistant("Status: DONE"))
    stop_record(world, "W1", tr); world.fh.states = [{"sl-proj-w1": "done"}]
    capsys.readouterr(); io.wait(world.sd, None, 5000)
    assert "W1 T3 DONE findings=0" in capsys.readouterr().out

def test_layer_worker_reports_exit_and_last_line(world, monkeypatch, capsys, stopped):
    p = world.sd / "fleet.json"; data = json.loads(p.read_text())
    data["workers"]["W3"] = {"role": "layer", "layer": "headless", "pane_id": "w6:p3", "account": "claude1", "state": "busy",
                             "task": "layer-headless", "sent": world.clock.t[0], "one_turn": True}
    p.write_text(json.dumps(data))
    results = [None, {"status": "RED", "exit": 1, "last": "FAILED tests/e2e/test_headless.py::test_x - assert 1 == 2",
                      "log": "/r/.superlite/fleet/layers/W3-headless.log"}]
    monkeypatch.setitem(sys.modules, "fleet_layer", types.SimpleNamespace(result=lambda sd, wid, w: results.pop(0)))
    out = io.wait(world.sd, None, 60000)
    text = capsys.readouterr().out
    assert "W3 layer-headless RED exit=1 /r/.superlite/fleet/layers/W3-headless.log\n  FAILED tests/e2e/test_headless.py::test_x - assert 1 == 2" in text
    assert out[0]["status"] == "RED" and stopped == ["W3"] and worker(world, "W3")["state"] == "ready"
    assert json.loads((world.sd / "fleet" / "reports" / "layer-headless.json").read_text())["exit"] == 1
