import time
# tests/scripts/test_fleet_io.py
import json, os, sys, types
from pathlib import Path
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402
REAL = os.environ.get("SUPERLITE_REAL") == "1"

class FakeHerdr:
    def __init__(self): self.calls, self.states, self.screen = [], [{"sl-proj-w1": "working", "sl-proj-w2": "working"}], "prompt text\n> Allow once?\n"
    def prompt(self, name, text, until, timeout_ms): self.calls.append(("prompt", name, text, until)); return "working"
    def agent_states(self): self.calls.append(("agent_states",)); return self.states.pop(0) if len(self.states) > 1 else self.states[0]
    def read_screen(self, name, lines=40, source="visible"): self.calls.append(("read_screen", name)); return self.screen
    def send_keys(self, name, keys): self.calls.append(("send_keys", name, keys))

def transcript(path, text):
    path.write_text(json.dumps({"type": "user", "message": {"content": "task"}}) + "\n" + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}) + "\n")

@pytest.fixture
def world(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; (sd / "fleet").mkdir(parents=True)
    plan = make_plan(proj, [{"id": "T3", "title": "c", "owns": "src/c.py, tests/test_c.py"}, {"id": "T4", "title": "d", "owns": "src/d.py"}])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "label": "sl:x", "workspace_id": "w6", "root_pane": "w6:p1", "accounts": ["claude1"], "next": 3,
        "workers": {"W1": {"name": "sl-proj-w1", "pane_id": "w6:p1", "account": "claude1", "agent": "superlite:implementer", "tier": "sonnet", "state": "ready", "task": None, "started": 1000},
                    "W2": {"name": "sl-proj-w2", "pane_id": "w6:p2", "account": "claude1", "agent": "superlite:implementer", "tier": "sonnet", "state": "ready", "task": None, "started": 1000}}}))
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "W1", "tier": "sonnet", "tasks": [], "files": [], "context_k": 20, "idle_min": 0, "busy": False, "backend": "herdr"},
                                                        {"id": "W2", "tier": "sonnet", "tasks": [], "files": [], "context_k": 20, "idle_min": 0, "busy": False, "backend": "herdr"}]}))
    fh = FakeHerdr(); monkeypatch.setattr(io, "hc", fh); monkeypatch.chdir(proj)
    clock = types.SimpleNamespace(t=[2_000_000])
    monkeypatch.setattr(io, "now_ms", lambda: clock.t[0]); monkeypatch.setattr(io, "sleep", lambda s: clock.t.__setitem__(0, clock.t[0] + int(s * 1000)))
    return types.SimpleNamespace(proj=proj, sd=sd, plan=plan, fh=fh, clock=clock)

def test_task_message_shape(world):
    m = io.task_message(world.plan, ["T3"], "/sl/sl", "/sl")
    assert m.startswith("# Task T3") and "SUPERLITE=/sl" in m and f"PLAN={world.plan.resolve()}" in m
    assert f"/sl/sl task T3 --plan {world.plan.resolve()}" in m and "Owns:" in m and "Do not touch:" in m and "src/d.py" in m
    assert "/sl/sl run_tests --fast tests/test_c.py --task T3 --background" in m and "Status: DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED" in m

def test_haiku_message_inlines_block(world):
    assert "### T3" in io.task_message(world.plan, ["T3"], "/sl/sl", "/sl", tier="haiku")

def test_last_assistant_text(tmp_path):
    p = tmp_path / "t.jsonl"; transcript(p, "Status: DONE\nFiles: a.py"); assert io.last_assistant_text(p) == "Status: DONE\nFiles: a.py"
    p.write_text("not json\n"); assert io.last_assistant_text(p) == ""

def rec(path, *items):
    path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")

def user(content, **kw): return {"type": "user", "message": {"role": "user", "content": content}, **kw}
def assistant(*blocks): return {"type": "assistant", "message": {"role": "assistant", "content": [b if isinstance(b, dict) else {"type": "text", "text": b} for b in blocks]}}
HOOK = user("Stop hook feedback:\n[command hook 1]: session-leftovers-check: this session would leave behind:\n- 1 uncommitted file", isMeta=True)
LEFTOVERS = "> \u26a0\ufe0f **Uncommitted work. Do /commit-merge now?**"

def test_report_skips_trailing_user_block(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"
    rec(tr, user("task"), assistant({"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}), user([{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]),
        assistant("Status: DONE\nFiles: a.py"), HOOK, assistant(LEFTOVERS))
    assert io.report_text(tr) == "Status: DONE\nFiles: a.py"
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 10, "agent_id": "W1", "type": "x", "transcript": str(tr), "last": LEFTOVERS}) + "\n")
    world.fh.states = [{"sl-proj-w1": "done"}]
    out = io.wait(world.sd, ["W1"], 5000)
    assert out[0]["status"] == "DONE" and "W1 T3 DONE" in capsys.readouterr().out
    assert (world.sd / "fleet" / "reports" / "T3.md").read_text() == "Status: DONE\nFiles: a.py"

def test_report_falls_back_to_last_text(tmp_path):
    tr = tmp_path / "t.jsonl"; rec(tr, user("task"), assistant("working..."), assistant("All set"))
    assert io.report_text(tr) == "All set"
    assert io.report_text(tmp_path / "missing.jsonl") == ""

def test_report_stays_in_latest_turn(tmp_path):
    tr = tmp_path / "t.jsonl"
    rec(tr, user("first task"), assistant("Status: DONE"), user([{"type": "text", "text": "second task"}]), assistant("Status: BLOCKED - no tests"))
    assert io.report_text(tr) == "Status: BLOCKED - no tests"
    rec(tr, user("first task"), assistant("Status: DONE"), user("second task"), assistant("still working"))
    assert io.report_text(tr) == "still working"

def test_report_survives_a_broken_json_line_in_the_latest_turn(tmp_path):
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps(user("task")) + "\n" + json.dumps(assistant("Status: DONE")) + "\n{broken json\n" + json.dumps(assistant("Files: a.py")) + "\n", encoding="utf-8")
    assert io.report_text(tr) == "Status: DONE"

def test_report_empty_turn_returns_empty_and_wait_uses_last(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("Status: DONE"), user("next"), assistant({"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}))
    assert io.report_text(tr) == ""
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 10, "agent_id": "W1", "type": "x", "transcript": str(tr), "last": "Status: BLOCKED - from last"}) + "\n")
    world.fh.states = [{"sl-proj-w1": "done"}]
    assert io.wait(world.sd, ["W1"], 5000)[0]["status"] == "BLOCKED"

def test_verify_line_lists_test_folder_files(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T2", "owns": "scripts/test_layers.py, tests/scripts/test_test_layers.py, docs/testing.md"}, {"id": "T5", "owns": "src/a_test.go, src/a.go"}, {"id": "T6", "owns": "src/x.py, docs/x.md"}])
    assert "`/sl/sl run_tests --fast tests/scripts/test_test_layers.py --task T2 --background`" in io.task_message(plan, ["T2"], "/sl/sl", "/sl")
    assert "run_tests --fast src/a_test.go --task T5 --background" in io.task_message(plan, ["T5"], "/sl/sl", "/sl")
    assert "run_tests --fast src/x.py docs/x.md --task T6 --background" in io.task_message(plan, ["T6"], "/sl/sl", "/sl")

def test_verify_line_skips_fixture_data_in_test_folder(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T2", "owns": "src/h.py, tests/scripts/test_h.py, tests/scripts/fixtures/fleet/herdr"}, {"id": "T3", "owns": "src/h.py, tests/scripts/fixtures/fleet/herdr"}])
    assert "run_tests --fast tests/scripts/test_h.py --task T2 --background" in io.task_message(plan, ["T2"], "/sl/sl", "/sl")
    m = io.task_message(plan, ["T3"], "/sl/sl", "/sl")
    assert "run_tests --fast src/h.py --task T3" in m and "run_tests --fast src/h.py tests/scripts/fixtures" not in m

def test_send_marks_busy_and_prompts_until_working(world, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    c = world.fh.calls[0]; assert c[:2] == ("prompt", "sl-proj-w1") and c[3] == ["working"] and "# Task T3" in c[2]
    assert json.loads((world.sd / "pool.json").read_text())["agents"][0]["busy"] is True
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]; assert (w["state"], w["task"]) == ("busy", "T3")
    assert "W1 T3 sent" in capsys.readouterr().out

def test_concurrent_sends_keep_both_pool_busy_flags(world, monkeypatch):
    import threading
    import pool as poolmod
    real = poolmod.load
    monkeypatch.setattr(poolmod, "load", lambda p: (lambda d: (time.sleep(0.2), d)[1])(real(p)))
    ts = [threading.Thread(target=io.send, args=(world.sd, world.plan, w, [t], "/sl/sl", "/sl")) for w, t in (("W1", "T3"), ("W2", "T4"))]
    [x.start() for x in ts]; [x.join() for x in ts]
    ag = {a["id"]: a for a in json.loads((world.sd / "pool.json").read_text())["agents"]}
    assert ag["W1"]["busy"] is True and ag["W2"]["busy"] is True

def test_wait_reads_report_from_transcript(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; transcript(tr, "Status: DONE\nFiles changed: src/c.py")
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 10, "agent_id": "W1", "type": "fleet:superlite:implementer", "transcript": str(tr), "last": "Status: DONE"}) + "\n")
    world.fh.states = [{"sl-proj-w1": "working", "sl-proj-w2": "idle"}, {"sl-proj-w1": "done", "sl-proj-w2": "idle"}]
    out = io.wait(world.sd, ["W1"], 10000)
    assert out == [{"id": "W1", "task": "T3", "status": "DONE", "report": str(world.sd / "fleet" / "reports" / "T3.md"), "source": "transcript"}]
    assert (world.sd / "fleet" / "reports" / "T3.md").read_text() == "Status: DONE\nFiles changed: src/c.py"
    assert f"W1 T3 DONE {world.sd / 'fleet' / 'reports' / 'T3.md'}" in capsys.readouterr().out
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"

def test_wait_ignores_stop_older_than_send(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "old.jsonl"; transcript(tr, "Status: DONE old task")
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent - 5000, "agent_id": "W1", "type": "x", "transcript": str(tr), "last": ""}) + "\n")
    world.fh.screen = "⏺ T3: DONE_WITH_CONCERNS, one flaky test\n"; world.fh.states = [{"sl-proj-w1": "working"}, {"sl-proj-w1": "done"}]
    out = io.wait(world.sd, ["W1"], 60000)
    assert out[0]["source"] == "screen" and out[0]["status"] == "DONE_WITH_CONCERNS" and "(screen)" in capsys.readouterr().out
    assert "old task" not in (world.sd / "fleet" / "reports" / "T3.md").read_text()

def test_wait_blocked_prints_screen_and_marks_blocked(world, capsys):
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl")
    world.fh.states = [{"sl-proj-w2": "working"}, {"sl-proj-w2": "blocked"}]
    out = io.wait(world.sd, ["W2"], 10000)
    assert out[0]["status"] == "BLOCKED-UI" and (world.sd / "fleet" / "screens" / "W2.txt").read_text() == world.fh.screen
    o = capsys.readouterr().out; assert f"W2 T4 BLOCKED-UI {world.sd / 'fleet' / 'screens' / 'W2.txt'}" in o and "Allow once?" in o
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W2"]["state"] == "blocked"

def test_wait_timeout_lists_rest(world, capsys):
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); world.fh.states = [{"sl-proj-w2": "working"}]
    assert io.wait(world.sd, None, 5000) == [] and "TIMEOUT W2" in capsys.readouterr().out

def test_status_parsed_from_lead_line(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; transcript(tr, "T3: DONE_WITH_CONCERNS. Files: src/c.py")
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 1, "agent_id": "W1", "type": "x", "transcript": str(tr), "last": ""}) + "\n")
    world.fh.states = [{"sl-proj-w1": "done"}]
    assert io.wait(world.sd, ["W1"], 5000)[0]["status"] == "DONE_WITH_CONCERNS"

def test_send_text_and_keys_cli(world):
    assert io.main(["send", "W1", "--text", "use the fake", "--plan", str(world.plan)]) == 0
    assert world.fh.calls[-1][:3] == ("prompt", "sl-proj-w1", "use the fake") and json.loads((world.sd / "pool.json").read_text())["agents"][0]["busy"] is False
    assert io.main(["keys", "W1", "Down", "Enter"]) == 0 and world.fh.calls[-1] == ("send_keys", "sl-proj-w1", ["Down", "Enter"])

def test_real_herdr_binary_argv(world, tmp_path, monkeypatch):
    if not REAL:
        pytest.skip("SUPERLITE_REAL=1 runs the real herdr_client against the fake binary")
    import herdr_client
    log = tmp_path / "log"; monkeypatch.setenv("SUPERLITE_HERDR_BIN", str(FIXTURES / "fleet" / "herdr")); monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setattr(io, "hc", herdr_client)
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    argv = json.loads(log.read_text().splitlines()[0]); assert argv[:3] == ["agent", "prompt", "sl-proj-w1"] and "--until" in argv and "working" in argv

def test_wait_blocked_reads_the_screen_by_agent_name(world):
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); world.fh.states = [{"sl-proj-w2": "blocked"}]
    io.wait(world.sd, ["W2"], 10000)
    assert ("read_screen", "sl-proj-w2") in world.fh.calls

def test_keys_for_an_unknown_worker_is_exit_2(world, capsys):
    assert io.main(["keys", "W9", "Enter"]) == 2 and "unknown worker" in capsys.readouterr().err and not world.fh.calls

def test_send_reaches_a_worker_record_without_a_stored_name(world):
    data = json.loads((world.sd / "fleet.json").read_text()); del data["workers"]["W1"]["name"]; (world.sd / "fleet.json").write_text(json.dumps(data))
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    assert world.fh.calls[0][:2] == ("prompt", "sl-proj-w1")

def test_keys_takes_plan_to_find_the_run(world, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert io.main(["keys", "W1", "Enter", "--plan", str(world.plan)]) == 0 and world.fh.calls[-1] == ("send_keys", "sl-proj-w1", ["Enter"])
