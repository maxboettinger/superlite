import json
import pytest
from test_fleet_io import assistant, io, rec, stop_at, user, world, HOOK  # noqa: F401  (world is a fixture)

REPORT_JSON = {"status": "DONE", "files": ["src/c.py"], "tests": "3 passed", "red": "", "findings": [], "summary": "ok"}
REPORT = "Status: DONE\n```json\n" + json.dumps(REPORT_JSON) + "\n```"
NOTE = {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": "<task-notification>\n<task-id>a1</task-id>\n</task-notification>"}}
STATUSES = "Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>"


def prompts(world):
    return [c for c in world.fh.calls if c[0] == "prompt"]


def worker(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def setw(world, wid, **kw):
    p = world.sd / "fleet.json"; data = json.loads(p.read_text()); data["workers"][wid].update(kw); p.write_text(json.dumps(data))


def sent_t3(world, tmp_path, *items, last="", state="idle", wid="W1", lag=10):
    io.send(world.sd, world.plan, wid, ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; rec(tr, *(items or (user("task"), assistant("Verify runs in the background."))))
    stop_at(world, tr, sent + lag, last=last)
    world.fh.states = [{"sl-proj-w1": state}]
    return sent, tr


def test_task_notification_does_not_start_a_turn(tmp_path):
    tr = tmp_path / "t.jsonl"
    rec(tr, user("task"), assistant(REPORT), NOTE, assistant("Background run done."))
    assert io.report_text(tr) == REPORT
    bare = {k: v for k, v in NOTE.items() if k != "origin"}
    rec(tr, user("task"), assistant(REPORT), bare, assistant("Background run done."))
    assert io.report_text(tr) == REPORT


def test_json_report_beats_a_later_bare_status(tmp_path):
    tr = tmp_path / "t.jsonl"
    rec(tr, user("task"), assistant(REPORT), HOOK, assistant("Uncommitted work warning\nStatus: DONE"))
    assert io.report_text(tr) == REPORT


def test_new_sender_turn_bounds_the_report(tmp_path):
    tr = tmp_path / "t.jsonl"
    rec(tr, user("task 1"), assistant(REPORT), user("task 2"), assistant("working on it"))
    assert io.report_text(tr) == "working on it"


def test_unreported_idle_stop_is_asked_once(world, tmp_path, capsys):
    sent, _ = sent_t3(world, tmp_path)
    assert io.wait(world.sd, ["W1"], 5000) == []
    assert "W1 T3 ASKED (turn ended without a report; asked once)" in capsys.readouterr().out
    ps = prompts(world)
    assert len(ps) == 2 and ps[-1][2].startswith(io.ASK) and STATUSES in ps[-1][2]
    w = worker(world); assert w["asked"] == w["sent"] and w["sent"] >= sent and w["state"] == "busy"
    assert not (world.sd / "fleet" / "reports" / "T3.md").exists()


def test_answer_after_ask_is_collected(world, tmp_path, capsys):
    sent_t3(world, tmp_path)
    io.wait(world.sd, ["W1"], 5000); asked = worker(world)["sent"]
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("waiting"), user(io.ASK + " x"), assistant(REPORT))
    stop_at(world, tr, asked + 10)
    out = io.wait(world.sd, ["W1"], 5000)
    assert [(r["status"], r["source"]) for r in out] == [("DONE", "transcript")] and len(prompts(world)) == 2


def test_second_miss_is_unknown(world, tmp_path, capsys):
    sent_t3(world, tmp_path)
    io.wait(world.sd, ["W1"], 5000); asked = worker(world)["sent"]
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), user(io.ASK + " x"), assistant("still waiting"))
    stop_at(world, tr, asked + 10)
    out = io.wait(world.sd, ["W1"], 5000)
    assert [r["status"] for r in out] == ["UNKNOWN"] and "(turn ended without a report)" in capsys.readouterr().out
    assert len(prompts(world)) == 2


def test_other_state_asks_after_settle(world, tmp_path, capsys):
    sent_t3(world, tmp_path, state="unknown")
    assert io.wait(world.sd, ["W1"], io.SETTLE_MS - 4000) == [] and len(prompts(world)) == 1
    capsys.readouterr()
    io.wait(world.sd, ["W1"], 2 * io.SETTLE_MS)
    assert "ASKED" in capsys.readouterr().out and len(prompts(world)) == 2


def test_working_state_is_never_asked(world, tmp_path, capsys):
    sent_t3(world, tmp_path, state="working")
    assert io.wait(world.sd, ["W1"], 2 * io.SETTLE_MS) == []
    assert "TIMEOUT W1" in capsys.readouterr().out and len(prompts(world)) == 1


def test_screen_without_status_is_asked_once(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    world.fh.screen = "⏺ Waiting\n"; world.fh.states = [{"sl-proj-w1": "idle"}]
    assert io.wait(world.sd, ["W1"], 5000) == [] and len(prompts(world)) == 1
    io.wait(world.sd, ["W1"], 2 * io.SETTLE_MS)
    assert "W1 T3 ASKED" in capsys.readouterr().out and len(prompts(world)) == 2
    setw(world, "W2", state="busy", task="T4", sent=1)
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl")
    world.fh.screen = "Status: DONE"; world.fh.states = [{"sl-proj-w2": "idle"}]
    out = io.wait(world.sd, ["W2"], 2 * io.SETTLE_MS)
    assert [(r["status"], r["source"]) for r in out] == [("DONE", "screen")] and "(screen)" in capsys.readouterr().out


def test_lead_is_never_asked(world, tmp_path, capsys):
    setw(world, "W1", role="lead")
    sent_t3(world, tmp_path)
    out = io.wait(world.sd, ["W1"], 5000)
    assert [r["status"] for r in out] == ["UNKNOWN"] and len(prompts(world)) == 1


def test_ask_herdr_error_finishes_unknown(world, tmp_path, capsys, monkeypatch):
    sent_t3(world, tmp_path)
    def boom(name, msg):
        raise io.hc.HerdrError("nope")
    monkeypatch.setattr(io, "_prompt", boom)
    out = io.wait(world.sd, ["W1"], 5000)
    assert [r["status"] for r in out] == ["UNKNOWN"] and "(turn ended without a report)" in capsys.readouterr().out


def test_concerns_in_wait_line(world, tmp_path, capsys, monkeypatch):
    sent_t3(world, tmp_path, user("task"), assistant("Status: DONE_WITH_CONCERNS"))
    real = io.fleet_report.parse
    fake = lambda concerns: lambda text, label="", allow_json=True: {**real(text, label, allow_json), "status": "DONE_WITH_CONCERNS", "concerns": concerns}
    monkeypatch.setattr(io.fleet_report, "parse", fake(["a", "b"]))
    io.wait(world.sd, ["W1"], 5000)
    assert "findings=0 concerns=2 " in capsys.readouterr().out
    setw(world, "W1", state="busy", sent=1)
    monkeypatch.setattr(io.fleet_report, "parse", fake([]))
    io.wait(world.sd, ["W1"], 5000)
    assert "concerns=" not in capsys.readouterr().out


def test_send_brief_full(world, tmp_path, capsys, monkeypatch):
    setw(world, "W2", role="final-reviewer", one_turn=True)
    monkeypatch.setattr(io.fleet_report, "brief_message", lambda role, path, full=False: f"{role}|{path}|{full}")
    p = tmp_path / "packet.md"; p.write_text("x\n"); P = str(world.plan)
    assert io.main(["send", "W2", "--brief", str(p), "--full", "--plan", P]) == 0
    assert prompts(world)[-1][2] == f"final-reviewer|{p.resolve()}|True"
    assert io.main(["send", "W2", "--brief", str(p), "--plan", P]) == 0
    assert prompts(world)[-1][2].endswith("|False")
    n = len(prompts(world)); capsys.readouterr()
    for argv in (["T3", "--full"], ["--text", "hi", "--full"], ["--full"]):
        assert io.main(["send", "W2", *argv, "--plan", P]) == 2
        assert "error: --full needs --brief" in capsys.readouterr().err
    assert io.main(["send", "W1", "--brief", str(p), "--full", "--plan", P]) == 2
    assert "error: --full is for a final-reviewer worker (W1 is implementer)" in capsys.readouterr().err
    assert len(prompts(world)) == n
