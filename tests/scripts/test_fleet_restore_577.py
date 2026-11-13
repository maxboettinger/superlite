# tests/scripts/test_fleet_restore_577.py: sl fleet restore re-launches the run's panes after a Herdr restart
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import fleet_restore as fr  # noqa: E402
import fleet_report  # noqa: E402
import fleet_state as fs  # noqa: E402

SL = str(Path(fr.__file__).resolve().parent / "sl")
TRUST = "Yes, I trust this folder"


class HE(Exception):
    def __init__(self, code, message=""):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


class Fake:
    """Stands in for herdr_client: records the writes, scripted agents, panes and failures."""
    def __init__(self):
        self.calls, self.agents, self.panes, self.sessions = [], [], set(), {}
        self.start_errors, self.tab_error, self.screen, self.prompt_error = [], None, "READY\n", None
        self.n = 0

    def all_agents(self): return list(self.agents)
    def pane_exists(self, pane): return pane in self.panes
    def agent_session(self, name): return self.sessions.get(name)
    def split_pane(self, pane, direction, cwd, env):
        self.calls.append(("split_pane", pane, direction, cwd, env)); self.n += 1; return f"w6:p{self.n + 1}"
    def close_pane(self, pane): self.calls.append(("close_pane", pane))
    def create_tab(self, ws, cwd, env):
        self.calls.append(("create_tab", ws))
        if self.tab_error: raise HE(self.tab_error, "gone")
        self.n += 1; return (f"t{self.n}", f"w7:p{self.n}")
    def create_workspace(self, label, cwd, env):
        self.calls.append(("create_workspace", label)); return ("w9", "w9:p1")
    def start_agent(self, name, pane, argv, timeout_ms=90000):
        self.calls.append(("start_agent", name, pane, argv))
        if self.start_errors:
            e = self.start_errors.pop(0)
            raise HE(*e)
        return "idle"
    def read_screen(self, name, lines=40, source="visible"): return self.screen
    def prompt(self, name, text, until, timeout_ms):
        self.calls.append(("prompt", name, text, until, timeout_ms))
        if self.prompt_error: raise HE("boom", self.prompt_error)
        return "working"
    def send_keys(self, name, keys): self.calls.append(("send_keys", name, keys))
    def wait_state(self, name, until, timeout_ms): self.calls.append(("wait_state", name, until)); return "idle"

    def writes(self): return [c for c in self.calls if c[0] != "prompt"]


def worker(**kw):
    w = {"name": "sl-a-w1", "account": "a", "agent": "superlite:implementer", "tier": "sonnet", "state": "busy", "task": "T3",
         "role": "implementer", "one_turn": False, "pane_id": "w6:p1", "sent": 1000, "brief": "b.md", "session": "s1",
         "launch": {"argv": ["--agent", "superlite:implementer", "--model", "sonnet"], "env": {"K": "v"}, "cwd": "/p"}}
    w.update(kw)
    return w


class World:
    def __init__(self, tmp_path, monkeypatch):
        self.sd = (tmp_path / "proj" / ".superlite").resolve()
        self.sd.mkdir(parents=True)
        self.fake = Fake()
        self.fake.panes = {"w6:p1", "w6:p2"}
        self.pauses = []
        monkeypatch.delenv("HERDR_PANE_ID", raising=False)
        monkeypatch.setattr(fr, "_test_lines", lambda sd: [])
        monkeypatch.setattr(fr, "_layer_alive", lambda sd, wid, w: None)
        monkeypatch.setattr(fr, "_pause", lambda s: self.pauses.append(s))
        self.save({"W1": worker()})

    def save(self, workers, sd=None, **top):
        sd = Path(sd or self.sd)
        sd.mkdir(parents=True, exist_ok=True)
        data = {**fs.default(), "on": True, "workers": workers, "workspace_id": "w6", **top}
        (sd / "fleet.json").write_text(json.dumps(data))

    def data(self, sd=None): return json.loads((Path(sd or self.sd) / "fleet.json").read_text())
    def stop(self, wid, t, transcript="/t/abc-123.jsonl", sd=None):
        with open(Path(sd or self.sd) / "metrics.jsonl", "a") as f:
            f.write(json.dumps({"ev": "stop", "t": t, "agent_id": wid, "transcript": transcript}) + "\n")
    def run(self, sd=None, prefix=""): return fr.restore(Path(sd or self.sd), self.fake, prefix)


@pytest.fixture
def w(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def idle_agent(pane="w6:p1", session="s1", status="idle", name="sl-a-w1"):
    return {"name": name, "pane_id": pane, "agent_status": status, "agent_session": {"kind": "id", "value": session}}


def test_busy_worker_resumed_and_continued(w):
    w.fake.agents = [idle_agent()]
    lines, blocked = w.run()
    assert (lines, blocked) == (["W1 restored pane=w6:p2 session=s1 busy, continued", f"re-arm: {SL} fleet wait --wave --timeout 540000 --plan {w.sd}"], False)
    argv = ["--agent", "superlite:implementer", "--model", "sonnet", "--resume", "s1"]
    assert w.fake.calls[:3] == [("split_pane", "w6:p1", "down", "/p", {"K": "v"}), ("close_pane", "w6:p1"), ("start_agent", "sl-a-w1", "w6:p2", argv)]
    assert w.fake.calls[3] == ("prompt", "sl-a-w1", fr.CONTINUE + "\n\n" + fleet_report.WORK, ["working"], 15000)
    rec = w.data()["workers"]["W1"]
    assert (rec["pane_id"], rec["state"], rec["task"], rec["brief"], rec["session"]) == ("w6:p2", "busy", "T3", "b.md", "s1")
    assert rec["sent"] > 1000


def test_ready_worker_not_prompted(w):
    w.save({"W1": worker(state="ready", task=None)})
    w.fake.agents = [idle_agent()]
    lines, blocked = w.run()
    assert lines == ["W1 restored pane=w6:p2 session=s1 ready"] and not blocked
    assert not any(c[0] == "prompt" for c in w.fake.calls)


def test_reported_turn_not_prompted(w):
    w.fake.agents = [idle_agent()]
    w.stop("W1", 2000)
    lines, _ = w.run()
    assert lines[0] == "W1 restored pane=w6:p2 session=s1 busy, reported"
    assert not any(c[0] == "prompt" for c in w.fake.calls)
    assert w.data()["workers"]["W1"]["sent"] == 1000


def test_session_falls_back_to_record_then_stop_record(w):
    lines, _ = w.run()  # no live agent: the recorded session
    assert lines[0].startswith("W1 restored pane=w6:p2 session=s1 ")
    w.save({"W1": worker(session=None)})
    w.stop("W1", 2000, "/t/abc-123.jsonl")
    w.stop("W1", 1500, "/t/old-1.jsonl")
    lines, _ = w.run()
    start = [c for c in w.fake.calls if c[0] == "start_agent"][-1]
    assert " session=abc-123 " in lines[0] and start[3][-2:] == ["--resume", "abc-123"]
    w.save({"W1": worker(session=None)})
    (w.sd / "metrics.jsonl").unlink()
    lines, blocked = w.run()
    assert blocked and lines[0] == "BLOCKED: W1 not restored (no session id)"


def test_existing_resume_pair_replaced(w):
    launch = {"argv": ["--agent", "x", "--resume", "old", "--model", "sonnet"], "env": {}, "cwd": "/p"}
    w.save({"W1": worker(launch=launch)})
    w.fake.agents = [idle_agent()]
    w.run()
    start = next(c for c in w.fake.calls if c[0] == "start_agent")
    assert start[3] == ["--agent", "x", "--model", "sonnet", "--resume", "s1"]


def test_no_old_pane_opens_tab_then_workspace(w):
    w.fake.panes = set()
    lines, _ = w.run()
    assert ("create_tab", "w6") in w.fake.calls and not any(c[0] in ("split_pane", "close_pane") for c in w.fake.calls)
    assert lines[0].startswith("W1 restored pane=w7:p1 ")
    w.fake.calls.clear()
    w.fake.tab_error = "workspace_not_found"
    lines, _ = w.run()
    assert ("create_workspace", "sl:fleet") in w.fake.calls and lines[0].startswith("W1 restored pane=w9:p1 ")
    assert w.data()["workspace_id"] == "w9"


def test_working_agent_skipped(w):
    w.fake.agents = [idle_agent(status="working")]
    lines, blocked = w.run()
    assert lines[0] == "W1 skipped (its agent is working in pane w6:p1)" and not blocked
    assert w.fake.calls == []


def test_own_pane_never_closed(w, monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "w6:p1")
    w.fake.agents = [idle_agent()]
    lines, blocked = w.run()
    assert blocked and lines[0] == "BLOCKED: W1 not restored (its pane is this session's pane)"
    assert w.fake.calls == []


def test_shell_retry_and_start_failure(w):
    w.fake.agents = [idle_agent()]
    w.fake.start_errors = [("agent_not_ready", "not an available shell")]
    lines, blocked = w.run()
    assert not blocked and lines[0].startswith("W1 restored") and w.pauses == [fr.fleet.SHELL_PAUSE_S]
    assert sum(1 for c in w.fake.calls if c[0] == "start_agent") == 2
    w.save({"W1": worker()})
    w.fake.calls.clear()
    w.fake.start_errors = [("exit", "kaboom")]
    lines, blocked = w.run()
    assert blocked and lines[0] == "BLOCKED: W1 not restored (startup: kaboom)"
    new = next(c for c in w.fake.calls if c[0] == "start_agent")[2]
    assert w.fake.calls[-1] == ("close_pane", new) and new != "w6:p1"
    assert w.data()["workers"]["W1"]["state"] == "blocked"


def test_trust_dialog_accepted(w):
    w.fake.agents = [idle_agent()]
    w.fake.screen = f"{TRUST}\n"
    w.run()
    assert ("send_keys", "sl-a-w1", ["Down", "Enter"]) in w.fake.calls


def test_dead_worker_restored_with_was_and_task(w):
    w.save({"W1": worker(state="stopped", dead=True, was="busy", task=None, last_task="T3")})
    lines, _ = w.run()
    assert lines[0] == "W1 restored pane=w6:p2 session=s1 busy, continued"
    rec = w.data()["workers"]["W1"]
    assert (rec["state"], rec["task"]) == ("busy", "T3") and not rec.get("dead") and "W1" in (w.sd / "pool.json").read_text()
    w.save({"W1": worker(state="stopped", dead=True, was="busy", task=None, last_task="T3"), "W4": worker(name="sl-a-w4", state="busy", task="T3", pane_id="w6:p3")})
    w.fake.calls.clear()
    lines, blocked = w.run()
    assert [x for x in lines if x.startswith("W1")] == ["W1 skipped (its task T3 went to W4)"] and not blocked
    assert not any(c[0] in ("split_pane", "start_agent") for c in w.fake.calls if c[1:2] == ("sl-a-w1",) or c[0] == "split_pane")


def test_lead_fleet_first_and_lead_prompt(w):
    lsd = w.sd.parent / "wt" / ".superlite"
    w.save({"W1": worker(name="sl-a-lead", role="lead", agent="lead", lead_sd=str(lsd), session="ls1", pane_id="w6:p1")})
    w.save({"W2": worker(name="sl-a-w2", pane_id="w6:p2", session="s2")}, sd=lsd)
    w.fake.panes = {"w6:p1", "w6:p2"}
    lines, blocked = w.run()
    assert not blocked
    assert lines[0].startswith("W1 W2 restored pane=") and lines[0].endswith("busy, continued")
    assert lines[1].startswith("W1 restored pane=") and lines[1].endswith("busy, continued")
    assert lines[-1] == f"re-arm: {SL} backlog wait" and f"--plan {lsd}" not in " ".join(lines)
    lead_prompt = next(c for c in w.fake.calls if c[0] == "prompt" and c[1] == "sl-a-lead")[2]
    assert lead_prompt.startswith(fr.LEAD_CONTINUE) and f"re-arm: {SL} fleet wait --wave --timeout 540000 --plan {lsd}" in lead_prompt
    assert lead_prompt.endswith("Then continue your brief where you stopped.")
    worker_prompt = next(c for c in w.fake.calls if c[0] == "prompt" and c[1] == "sl-a-w2")[2]
    assert worker_prompt.startswith(fr.CONTINUE)


def test_dead_layer_stopped(w, monkeypatch):
    w.save({"W3": {"role": "layer", "layer": "headless", "state": "busy", "task": "layer-headless", "sent": 5, "pane_id": "w6:p1", "agent": None}})
    monkeypatch.setattr(fr, "_layer_alive", lambda sd, wid, wk: False)
    lines, blocked = w.run()
    assert lines == [f"W3 layer-headless died with the restart; rerun: {SL} fleet run --layer headless --plan {w.sd}"] and not blocked
    assert w.data()["workers"]["W3"]["state"] == "stopped" and w.fake.calls == []


def test_main_fleet_off_and_nothing(w, capsys):
    w.save({}, on=False)
    assert fr.main(["--plan", str(w.sd)]) == 3
    assert capsys.readouterr().out.strip() == f"BLOCKED: fleet is off in {w.sd}; nothing to restore"
    w.save({})
    assert fr.main(["--plan", str(w.sd)]) == 0
    assert capsys.readouterr().out.strip() == f"fleet restore: nothing to restore in {w.sd}"


def test_main_exit_3_on_blocked(w, capsys, monkeypatch):
    monkeypatch.setattr(fr, "_client", lambda: w.fake)
    w.save({"W2": {k: v for k, v in worker().items() if k != "launch"}})
    assert fr.main(["--plan", str(w.sd)]) == 3
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED: W2 not restored (no launch record; spawned before restore existed); start a fresh one: sl fleet spawn")
    monkeypatch.setattr(fr, "_test_lines", lambda sd: ["test run ended: x tests (full): 7 passed, 0 failed"])
    w.save({"W1": worker(state="ready", task=None)})
    w.fake.agents = [idle_agent()]
    assert fr.main(["--plan", str(w.sd)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "test run ended: x tests (full): 7 passed, 0 failed"


def dead_w1(**kw): return worker(state="stopped", dead=True, was="busy", task=None, last_task="T3", **kw)


def test_dead_worker_skipped_when_task_committed_in_ledger(w):
    w.save({"W1": dead_w1()})
    (w.sd / "progress.md").write_text("- commit T3 abc1234 done by a now-ready worker\n")
    lines, blocked = w.run()
    assert [x for x in lines if x.startswith("W1")] == ["W1 skipped (its task T3 went to ledger)"] and not blocked
    assert not any(c[0] in ("split_pane", "start_agent", "prompt") for c in w.fake.calls)


def test_dead_worker_skipped_when_other_worker_last_task_holds_it(w):
    w.save({"W1": dead_w1(), "W4": worker(name="sl-a-w4", state="ready", task=None, last_task="T3", pane_id="w6:p3")})
    w.fake.panes.add("w6:p3")
    lines, blocked = w.run()
    assert [x for x in lines if x.startswith("W1")] == ["W1 skipped (its task T3 went to W4)"] and not blocked
    assert not any(c[0] in ("start_agent", "prompt") and c[1] == "sl-a-w1" for c in w.fake.calls)


def test_recorded_pane_of_another_session_is_not_closed(w):
    w.fake.agents = [idle_agent(pane="w6:p1", session="other", name="sl-b-w9")]
    lines, blocked = w.run()
    assert lines[0].startswith("W1 restored pane=w7:p1 ") and not blocked
    assert ("create_tab", "w6") in w.fake.calls
    assert not any(c[0] in ("close_pane", "split_pane") for c in w.fake.calls)


def test_dead_worker_with_joined_label_skipped_when_one_id_committed(w):
    w.save({"W1": worker(state="stopped", dead=True, was="busy", task=None, last_task="T3,T4")})
    (w.sd / "progress.md").write_text("- commit T3 abc1234 done\n")
    lines, blocked = w.run()
    assert [x for x in lines if x.startswith("W1")] == ["W1 skipped (its task T3,T4 went to ledger)"] and not blocked
    assert not any(c[0] in ("split_pane", "start_agent", "prompt") for c in w.fake.calls)


def test_dead_worker_with_joined_label_restored_when_none_taken(w):
    w.save({"W1": worker(state="stopped", dead=True, was="busy", task=None, last_task="T3,T4")})
    lines, _ = w.run()
    assert lines[0].startswith("W1 restored")


def test_two_dead_workers_same_last_task_only_newer_restored(w):
    w.save({"W1": dead_w1(sent=1000), "W2": dead_w1(name="sl-a-w2", sent=2000, pane_id="w6:p2", session="s2")})
    lines, _ = w.run()
    assert [x for x in lines if x.startswith("W1")] == ["W1 skipped (its task T3 went to W2)"]
    assert any(x.startswith("W2 restored") for x in lines)
