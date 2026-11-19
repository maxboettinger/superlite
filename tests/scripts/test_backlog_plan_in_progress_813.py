import os
import subprocess
import sys
import pytest
import test_backlog_cli as tc
from test_backlog_cli import bk, briefed, cli, load, BATCH, bl  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_in_progress as bip  # noqa: E402
import backlog_intake as bi  # noqa: E402

GHLINE = "in progress: #7 (branch 7-login): not planned, another session builds it; sl backlog plan --issues 7 --add plans it anyway"
JLINE = "in progress: PIX-2 (Jira status In Progress): not planned, another session builds it; sl backlog plan --issues PIX-2 --add plans it anyway"


def item(n, **kw):
    return {"number": n, "title": "T", "body": "", **kw}


def test_split_drops_busy_unpinned():
    busy = [{"kind": "status", "name": "In Progress"}]
    assert bi.split_shipped([item("PIX-2", busy=busy)], [], {}, []) == (
        [], [{"number": "PIX-2", "title": "T", "reason": "not planned (in progress: Jira status In Progress)"}],
        ["in progress: PIX-2 (Jira status In Progress): not planned, another session builds it; sl backlog plan --issues PIX-2 --add plans it anyway"])


def test_split_keeps_busy_pinned():
    assert bi.split_shipped([item(5, busy=[{"kind": "branch", "name": "5-x"}])], [], {}, [5]) == (
        [item(5)], [], ["in progress?: #5 (branch 5-x): planned anyway (pinned); sl backlog skip 5 drops it"])


def test_split_ignores_own_batch_branch_and_worktree(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    real = os.path.realpath(wt)
    busy = [{"kind": "branch", "name": "superlite/b3-5-x"}, {"kind": "worktree", "name": real, "branch": "other"}]
    batches = [{"id": "B3", "state": "parked", "issues": [5], "branch": "superlite/b3-5-x", "worktree": str(wt)}]
    assert bi.split_shipped([item(5, busy=busy)], batches, {}, []) == ([item(5)], [], [])


def test_split_shipped_wins_over_busy():
    batches = [{"id": "B7", "state": "shipped", "issues": [5], "pr": 9}]
    kept, dropped, lines = bi.split_shipped([item(5, busy=[{"kind": "branch", "name": "5-x"}])], batches, {}, [])
    assert kept == [] and dropped == []
    assert lines == ["already shipped: #5 in B7 (PR #9): not planned again"]


def test_split_reopened_busy_unpinned_is_left_out():
    batches = [{"id": "B7", "state": "shipped", "issues": [5]}]
    it = item(5, reopened=True, busy=[{"kind": "branch", "name": "5-x"}])
    kept, dropped, lines = bi.split_shipped([it], batches, {}, [])
    assert kept == [] and dropped[0]["reason"] == "not planned (in progress: branch 5-x)"
    assert len(lines) == 1 and lines[0].startswith("in progress: #5")


def test_split_never_returns_busy_key():
    busy = [{"kind": "branch", "name": "5-x"}]
    kept, _, _ = bi.split_shipped([item(5, busy=busy), item(6, busy=busy), item(7)], [], {}, [5])
    assert [k["number"] for k in kept] == [5, 7]
    assert all("busy" not in k for k in kept)


def test_with_comments_attaches_busy(monkeypatch):
    seen = []

    def hits(items, jira, root):
        seen.append(jira)
        return {5: [{"kind": "branch", "name": "5-x"}]}, ["in progress: worktrees and branches not read (x)"]
    monkeypatch.setattr(bip, "hits", hits)
    monkeypatch.setattr(backlog, "_gh", lambda a: {"data": {"repository": {}}})
    out, lines = bi.with_comments([item(5), item(6)], "o/r", True)
    assert out[0]["busy"] == [{"kind": "branch", "name": "5-x"}] and "busy" not in out[1]
    assert lines[-1] == "in progress: worktrees and branches not read (x)"
    monkeypatch.setattr(backlog, "_acli", lambda a: {"comments": []})
    bi.with_comments([item("PIX-1")], "", False, True)
    assert seen == [False, True]


def test_with_comments_empty_reads_nothing(monkeypatch):
    monkeypatch.setattr(bip, "hits", lambda *a: (_ for _ in ()).throw(AssertionError("read")))
    assert bi.with_comments([], "o/r", True) == ([], [])


def test_with_comments_gate_off_runs_no_git(monkeypatch):
    monkeypatch.setenv("SUPERLITE_IN_PROGRESS_LIVE", "0")
    monkeypatch.setattr(backlog, "_root", lambda: (_ for _ in ()).throw(AssertionError("git")))
    monkeypatch.setattr(backlog, "_gh", lambda a: {"data": {"repository": {}}})
    out, lines = bi.with_comments([item(5)], "o/r", True)
    assert all("busy" not in o for o in out) and not any(line.startswith("in progress") for line in lines)


def test_with_comments_outside_git_fails_soft(monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)

    def no_root():
        raise RuntimeError("not in a git repository")
    monkeypatch.setattr(backlog, "_root", no_root)
    monkeypatch.setattr(bip, "hits", lambda *a: (_ for _ in ()).throw(AssertionError("read")))
    monkeypatch.setattr(backlog, "_gh", lambda a: {"data": {"repository": {}}})
    out, lines = bi.with_comments([item(5)], "o/r", True)
    assert all("busy" not in o for o in out)
    assert lines[-1] == "in progress: worktrees and branches not read (not in a git repository)"


def git_root(root, *branches):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "c"], *[["branch", b] for b in branches]):
        subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", *args], cwd=root, env=env, check=True, capture_output=True)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR",
              "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: [])


def test_plan_jira_leaves_out_in_progress(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)
    (bk.root / "f").write_text("x")
    git_root(bk.root)
    acli_issues = [{"key": "PIX-1", "fields": {"summary": "One", "description": None}},
                   {"key": "PIX-2", "fields": {"summary": "Two", "description": None}}]

    def acli(args):
        if args[:3] == ["jira", "workitem", "search"] and "statusCategory" in args[4]:
            return [{"key": "PIX-2", "fields": {"status": {"name": "In Progress"}}}]
        return acli_issues if args[:3] == ["jira", "workitem", "search"] else {"comments": []}
    monkeypatch.setattr(bl, "_acli", acli)
    bk.batches = [{**BATCH, "issues": ["PIX-1"]}]
    rc, out = cli(capsys, "plan", "--jql", "project = PIX")
    assert rc == 0 and JLINE in out
    assert [b["number"] for b in briefed(bk)] == ["PIX-1"]
    assert {"number": "PIX-2", "title": "Two", "reason": "not planned (in progress: Jira status In Progress)"} in [
        {k: o[k] for k in ("number", "title", "reason") if k in o} for o in load(bk)["outside"]]


def test_plan_github_leaves_out_issue_with_branch(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)
    monkeypatch.setattr(bl, "_gh", lambda a: _gh(bk, a))
    (bk.root / "f").write_text("x")
    git_root(bk.root, "7-login")
    bk.batches = [{**BATCH, "issues": [8]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and GHLINE in out
    assert [b["number"] for b in briefed(bk)] == [8]


def test_plan_pinned_in_progress_is_planned(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)
    monkeypatch.setattr(bl, "_gh", lambda a: _gh(bk, a))
    (bk.root / "f").write_text("x")
    git_root(bk.root, "7-login")
    bk.batches = [{**BATCH, "issues": [7]}]
    rc, out = cli(capsys, "plan", "--issues", "7")
    assert rc == 0
    assert "in progress?: #7 (branch 7-login): planned anyway (pinned); sl backlog skip 7 drops it" in out
    assert load(bk)["batches"][0]["issues"] == [7]


def _gh(ns, args):
    ns.gh.append(args)
    if args[:2] == ["repo", "view"]:
        return {"nameWithOwner": "o/r", "visibility": ns.vis}
    if args[:2] == ["api", "graphql"]:
        return {"data": {"repository": {}}}
    return [{"number": n, "title": f"I{n}", "author": {"login": "max"}, "authorAssociation": "OWNER", "body": f"b{n}"} for n in (7, 8)]
