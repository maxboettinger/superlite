import os, sys
import pytest
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
import backlog_tracker  # noqa: E402
import backlog_run  # noqa: E402

REAL = os.environ.get("SUPERLITE_REAL") == "1"

def seed(bk, batches):
    p = bs.path(bk.root)
    def fn(d):
        d["repo"] = "o/r"
        d["batches"] = batches
    bs.update(p, fn)

def shipped(bid, issues, open_):
    return {"id": bid, "topic": "t", "issues": issues, "files": [], "depends": [], "decisions": [],
            "state": "shipped", "version": "1.0", "open_issues": open_}

def fake_open(monkeypatch, fn):
    if not REAL:
        monkeypatch.setattr(backlog_tracker, "open_now", fn, raising=False)
    else:  # the real open_now runs; only its two outside reads are faked
        monkeypatch.setattr(backlog_tracker, "_gh_closed", lambda repo, nums, root: set(nums) - set(fn(repo, nums, root)))
        monkeypatch.setattr(backlog_tracker, "_jira_done", lambda keys: set(keys) - set(fn("", keys, None)))

def test_status_drops_closed_markers_and_keeps_failed_reads(bk, capsys, monkeypatch):
    seed(bk, [shipped("B1", [5, 6], [5, 6])])
    calls = []
    def f(repo, issues, root):
        calls.append((repo, list(issues)))
        return [5]
    fake_open(monkeypatch, f)
    rc, out = cli(capsys, "status")
    assert rc == 0 and "OPEN #5" in out and "#6" not in out.split("OPEN")[1]
    assert load(bk)["batches"][0]["open_issues"] == [5]
    assert calls == [("o/r", [5, 6])]

def test_status_all_refreshes_earlier_rounds(bk, capsys, monkeypatch):
    seed(bk, [shipped("B1", [1], [1]), shipped("B2", [2], [2])])
    data = load(bk); data["round"] = ["B2"]
    bs.update(bs.path(bk.root), lambda d: d.update(round=["B2"]))
    fake_open(monkeypatch, lambda repo, issues, root: [])
    cli(capsys, "status", "--all")
    assert [b["open_issues"] for b in load(bk)["batches"]] == [[], []]

def test_refresh_skips_a_list_changed_meanwhile(bk, monkeypatch):
    seed(bk, [shipped("B1", [5, 6], [5, 6])])
    def f(repo, issues, root):
        bs.update(bs.path(bk.root), lambda d: d["batches"][0].update(open_issues=[7]))
        return []
    fake_open(monkeypatch, f)
    assert bl.refresh_open(bk.root) == {}
    assert load(bk)["batches"][0]["open_issues"] == [7]

def test_refresh_without_markers_imports_nothing(bk, monkeypatch):
    seed(bk, [shipped("B1", [5], [])])
    monkeypatch.delitem(sys.modules, "backlog_tracker", raising=False)
    assert bl.refresh_open(bk.root) == {}
    assert "backlog_tracker" not in sys.modules

def test_refresh_returns_changed_batches(bk, monkeypatch):
    seed(bk, [shipped("B1", [5, "PIX-9"], [5, "PIX-9"])])
    fake_open(monkeypatch, lambda repo, issues, root: [])
    assert bl.refresh_open(bk.root) == {"B1": []}

def parked(bid, wt=None):
    b = {"id": bid, "topic": "t", "issues": [9], "files": ["z.py"], "depends": [], "decisions": [], "state": "parked"}
    if wt:
        b["worktree"] = wt
    return b

def test_reset_removes_dropped_worktrees(bk, capsys, monkeypatch, tmp_path):
    wt = tmp_path / "b2"
    wt.mkdir()
    seed(bk, [parked("B2", str(wt))])
    seen = []
    real = getattr(backlog_run, "drop_worktree", None)
    def drop(root, b):  # REAL: wraps the real drop_worktree, only its git and cleanup calls are faked
        seen.append(b["id"])
        return real(root, b) if REAL else [f"B2 worktree {wt} removed"]
    if REAL:
        monkeypatch.setattr(backlog_run, "_run", lambda cmd, cwd: (0, ""))
        monkeypatch.setattr(backlog_run, "project_cleanup", lambda root, wt, br, bid: None)
    monkeypatch.setattr(backlog_run, "drop_worktree", drop, raising=False)
    rc, out = cli(capsys, "plan", "--reset")
    assert rc == 0 and seen == ["B2"] and out.rstrip().splitlines()[-1] == f"B2 worktree {wt} removed"

def test_reset_skips_batches_without_worktree(bk, capsys, monkeypatch):
    seed(bk, [parked("B2")])
    seen = []
    if not REAL:
        monkeypatch.setattr(backlog_run, "drop_worktree", lambda root, b: seen.append(b["id"]) or [], raising=False)
    assert cli(capsys, "plan", "--reset")[0] == 0 and seen == []

def test_plain_plan_drops_nothing(bk, capsys, monkeypatch):
    seed(bk, [])
    seen = []
    if not REAL:
        monkeypatch.setattr(backlog_run, "drop_worktree", lambda root, b: seen.append(b["id"]) or [], raising=False)
    assert cli(capsys, "plan")[0] == 0 and seen == []
