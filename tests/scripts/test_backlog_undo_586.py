import json, sys, types
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_undo  # noqa: E402
import backlog_run  # noqa: E402
import backlog_state as bs  # noqa: E402
import fleet  # noqa: E402
import fleet_state  # noqa: E402
import ship_lock  # noqa: E402


def test_unskip_removes_int_and_key():
    d = {"skipped": [5, "PIX-1"], "batches": []}
    assert backlog_undo.unskip_issue(d, 5) == ("unskipped #5: the next sl backlog plan triages it again; "
                                               "sl backlog plan --issues 5 --add plans it now")
    assert d["skipped"] == ["PIX-1"]
    assert backlog_undo.unskip_issue(d, "PIX-1").startswith("unskipped PIX-1: ")
    assert "--issues PIX-1 --add" in backlog_undo.unskip_issue({"skipped": ["PIX-1"]}, "PIX-1")


def test_unskip_not_skipped():
    with pytest.raises(ValueError, match="PIX-2 is not skipped"):
        backlog_undo.unskip_issue({"skipped": []}, "PIX-2")
    with pytest.raises(ValueError, match="#7 is not skipped"):
        backlog_undo.unskip_issue({"skipped": [5]}, 7)


FULL = {"id": "B1", "state": "running", "lead": "W1", "agent": "sl-m-W1", "branch": "superlite/b1-t", "pr": 7,
        "version": "1.0", "since": 5, "ship_runs": 2, "questions": 3, "merged": False, "reason": "x",
        "reprompted": True, "question_reprompted": True, "gone_seen": {"a": 1}, "gone_workers": ["W2"],
        "open_issues": [1], "followups": ["f"], "undone": ["u"], "cleaned": True, "parked_by": "main", "parked_at": 1,
        "issues": [1, 2], "files": ["a"], "depends": ["B0"], "decisions": [{"questions": []}], "answers": {"q": "a"},
        "answered_by": {"q": "main"}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "root"; (root / ".superlite").mkdir(parents=True)
    wt = tmp_path / "wt"; wt.mkdir()
    b = {**FULL, "worktree": str(wt), "pr": None}
    p = bs.path(root)
    p.write_text(json.dumps({**bs.default(), "repo": "o/r", "batches": [b]}))
    e = types.SimpleNamespace(root=root, wt=wt, p=p, git=[], calls=[], states=[{"sl-m-W1": "idle"}, {}],
                              git_rc={}, released=[], cleanup=None)
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(backlog_undo, "_sleep", lambda s: None)

    def run(cmd, cwd):
        e.git.append(cmd)
        key = " ".join(cmd[1:3])
        rc, msg = e.git_rc.get(key, (0, ""))
        if cmd[1:3] == ["worktree", "remove"] and rc == 0:
            pass
        return rc, msg
    monkeypatch.setattr(backlog_run, "_run", run)
    monkeypatch.setattr(backlog_run, "project_cleanup", lambda r, w, br, bid: e.cleanup)
    monkeypatch.setattr(fleet, "stop", lambda sd, ids=None, all_=False, **k: e.calls.append(("stop", str(sd), ids, all_)))
    monkeypatch.setattr(fleet_state, "workers", lambda sd, state=None: {"W1": {"pane_id": "p1"}})

    def states():
        if isinstance(e.states, Exception):
            raise e.states
        return e.states[0] if len(e.states) == 1 else e.states.pop(0)
    monkeypatch.setattr(fleet.hc, "agent_states", states)
    monkeypatch.setattr(fleet.hc, "exit_agent", lambda n: e.calls.append(("exit", n)))
    monkeypatch.setattr(fleet.hc, "close_pane", lambda pid: e.calls.append(("close", pid)))
    monkeypatch.setattr(ship_lock, "release", lambda lp, bid: e.released.append((lp, bid)))
    return e


def batch(e):
    return json.loads(e.p.read_text())["batches"][0]


def test_reset_happy_path(env):
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 0
    assert lines == ["B1 lead W1 stopped", f"B1 worktree {env.wt} removed", "B1 branch superlite/b1-t deleted",
                     "B1 reset: planned; sl backlog start B1 starts a fresh lead in a fresh worktree"]
    assert ["git", "worktree", "remove", str(env.wt)] in env.git
    assert ["git", "branch", "-d", "superlite/b1-t"] in env.git


def test_reset_clears_run_fields_keeps_decisions(env):
    backlog_undo.reset_batch(env.root, "B1")
    b = batch(env)
    assert b["state"] == "planned"
    for k in ("lead", "agent", "worktree", "branch", "pr", "version"):
        assert b[k] is None
    for k in ("since", "ship_runs", "questions"):
        assert b[k] == 0
    assert b["merged"] is False and b["reason"] == ""
    for k in ("reprompted", "question_reprompted", "gone_seen", "gone_workers", "open_issues", "followups", "undone",
              "cleaned", "parked_by", "parked_at"):
        assert k not in b
    for k in ("issues", "files", "depends", "decisions", "answers", "answered_by"):
        assert b[k] == FULL[k]


def test_reset_keeps_work_and_parks(env):
    env.git_rc["worktree remove"] = (1, "x\nfatal: contains modified or untracked files")
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 3
    assert lines == ["B1 lead W1 stopped",
                     f"B1 worktree {env.wt} kept: fatal: contains modified or untracked files",
                     "BLOCKED: B1 parked: reset kept its worktree; sl backlog reset B1 --discard drops it, "
                     "sl backlog start B1 resumes it"]
    b = batch(env)
    assert b["state"] == "parked" and b["worktree"] == str(env.wt) and b["branch"] == "superlite/b1-t"
    assert b["lead"] is None and b["agent"] is None and b["since"] == 0
    assert b["reprompted"] is False and b["question_reprompted"] is False


def test_reset_keeps_unmerged_branch(env):
    env.git_rc["branch -d"] = (1, "error: not fully merged")
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 3
    assert "B1 branch superlite/b1-t kept (not merged)" in lines
    assert lines[-1].startswith("BLOCKED: B1 parked: reset kept its branch;")
    assert batch(env)["state"] == "parked" and batch(env)["branch"] == "superlite/b1-t"


def test_discard_forces(env):
    backlog_undo.reset_batch(env.root, "B1", discard=True)
    assert ["git", "worktree", "remove", "--force", str(env.wt)] in env.git
    assert ["git", "branch", "-D", "superlite/b1-t"] in env.git


def test_lead_still_live_blocks_without_change(env):
    env.states = [{"sl-m-W1": "idle"}]
    before = env.p.read_text()
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert (rc, lines) == (3, ["BLOCKED: B1 lead W1 still runs after stop; close its Herdr pane, then rerun "
                               "sl backlog reset B1"])
    assert env.p.read_text() == before
    assert ("stop", str(env.root / ".superlite"), ["W1"], False) in env.calls
    assert env.calls.count(("exit", "sl-m-W1")) == 1 and env.calls.count(("close", "p1")) == 1
    assert env.git == []


def test_herdr_down_blocks(env):
    env.states = fleet.hc.HerdrError("E", "down")
    before = env.p.read_text()
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert (rc, lines) == (3, ["BLOCKED: Herdr not reachable (E: down); B1 keeps its state"])
    assert env.p.read_text() == before


def test_refusals(env, monkeypatch):
    before = env.p.read_text()
    assert backlog_undo.reset_batch(env.root, "B9") == (2, ["refused: unknown batch B9"])
    for patch, msg in (({"state": "shipped"}, "refused: B1 is shipped"),
                       ({"merged": True, "pr": 7}, "refused: B1 merged PR #7; sl backlog wait records it as shipped"),
                       ({"state": "planned", "lead": None, "worktree": None, "agent": None},
                        "refused: B1 is planned; nothing to reset")):
        d = json.loads(before); d["batches"][0].update(patch); env.p.write_text(json.dumps(d))
        snap = env.p.read_text()
        assert backlog_undo.reset_batch(env.root, "B1") == (2, [msg])
        assert env.p.read_text() == snap
    env.p.write_text(before)
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    assert backlog_undo.reset_batch(env.root, "B1") == (2, ["refused: sl backlog reset runs only in the main session"])
    assert env.p.read_text() == before and env.git == []


def test_main_checkout_is_never_removed(env):
    d = json.loads(env.p.read_text()); d["batches"][0]["worktree"] = str(env.root); env.p.write_text(json.dumps(d))
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 3 and f"B1 worktree {env.root} kept: it is the main checkout" in lines
    assert not any(c[1:3] == ["worktree", "remove"] for c in env.git)


def test_missing_worktree_prunes_then_deletes_branch(env):
    env.wt.rmdir()
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 0
    assert env.git == [["git", "worktree", "prune"], ["git", "branch", "-d", "superlite/b1-t"]]


def test_parked_by_main_unparks(env):
    d = json.loads(env.p.read_text())
    d["batches"][0].update({"state": "parked", "reason": "dup", "parked_by": "main", "lead": None, "agent": None,
                            "worktree": None, "branch": None})
    env.p.write_text(json.dumps(d))
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert (rc, lines) == (0, ["B1 reset: planned; sl backlog start B1 starts a fresh lead in a fresh worktree"])
    assert batch(env)["state"] == "planned" and "parked_by" not in batch(env)


def test_ship_lock_released(env):
    backlog_undo.reset_batch(env.root, "B1")
    assert env.released == [(ship_lock.lock_path("o/r"), "B1")]


def test_cleanup_failure_line_shown(env):
    env.cleanup = "B1 project cleanup: exit 1"
    _, lines = backlog_undo.reset_batch(env.root, "B1")
    assert "B1 project cleanup: exit 1" in lines


def test_main_checkout_fleet_is_not_stopped(env):
    (env.root / ".superlite").mkdir(exist_ok=True)
    d = json.loads(env.p.read_text()); d["batches"][0]["worktree"] = str(env.root); env.p.write_text(json.dumps(d))
    backlog_undo.reset_batch(env.root, "B1")
    assert not any(c[0] == "stop" and c[3] for c in env.calls)


def test_fleet_stop_systemexit_still_blocks(env, monkeypatch):
    env.states = [{"sl-m-W1": "idle"}]

    def boom(*a, **k):
        raise SystemExit(2)
    monkeypatch.setattr(fleet, "stop", boom)
    rc, lines = backlog_undo.reset_batch(env.root, "B1")
    assert rc == 3 and lines[0].startswith("BLOCKED: B1 lead W1 still runs")
