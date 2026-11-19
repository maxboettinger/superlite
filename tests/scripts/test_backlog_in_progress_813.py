# tests/scripts/test_backlog_in_progress_813.py
import os
import subprocess
import sys
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_in_progress as bip  # noqa: E402

ACLI_ERR = "acli jira workitem search failed: x"


def br(name):
    return {"kind": "branch", "name": name}


def test_match_jira_key_bounds():
    names = [br("feature/pix-2-login"), br("PIX-21"), br("XPIX-2"), br("bugfix/abc_PIX-2")]
    assert bip.match("PIX-2", names) == [br("feature/pix-2-login"), br("bugfix/abc_PIX-2")]


def test_match_github_number_last_part():
    names = [br(n) for n in ["fix/812-release", "issue-812", "gh_812", "812", "dependabot/x/action-1.2.812",
                             "superlite/b812-x", "node-812", "fix/8120-x"]]
    assert bip.match(812, names) == names[:4]


def test_match_worktree_hides_its_branch_hit():
    wt = {"kind": "worktree", "name": "/r/.claude/worktrees/7-login", "branch": "7-login"}
    assert bip.match(7, [wt, br("7-login")]) == [wt]
    wt2 = {"kind": "worktree", "name": "/r/wt/issue-7", "branch": "misc"}
    assert bip.match(7, [wt2, br("misc")]) == [wt2]


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", *args], cwd=cwd, env=env, check=True,
                   capture_output=True)


def test_git_names_reads_worktrees_and_branches(tmp_path, monkeypatch):
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "c")
    _git(repo, "branch", "5-x")
    w1, w2 = tmp_path / "w1", tmp_path / "w2"
    _git(repo, "worktree", "add", "-q", "-b", "6-y", str(w1))
    _git(repo, "worktree", "add", "-q", "--detach", str(w2))
    _git(repo, "update-ref", "refs/remotes/origin/7-z", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/HEAD", "HEAD")
    names, err = bip.git_names(repo)
    assert err is None
    assert [n for n in names if n["kind"] == "worktree"] == [
        {"kind": "worktree", "name": os.path.realpath(w1), "branch": "6-y"},
        {"kind": "worktree", "name": os.path.realpath(w2), "branch": ""}]
    branches = [n["name"] for n in names if n["kind"] == "branch"]
    assert sorted(branches) == ["5-x", "6-y", "7-z", "main"]


def test_git_names_outside_a_repo(tmp_path, monkeypatch):
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    names, err = bip.git_names(tmp_path)
    assert names == []
    assert "git worktree list" in err


def fake_acli(monkeypatch, reply, calls):
    def acli(args):
        calls.append(args)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(backlog, "_acli", acli)


def test_jira_in_progress_one_search(monkeypatch):
    calls = []
    fake_acli(monkeypatch, [{"key": "PIX-2", "fields": {"status": {"name": "In Review"}}}, {"key": "PIX-9"}], calls)
    assert bip.jira_in_progress(["PIX-2", "PIX-3"]) == ({"PIX-2": "In Review"}, None)
    assert calls == [["jira", "workitem", "search", "--jql", 'key in (PIX-2, PIX-3) AND statusCategory = "In Progress"',
                      "--fields", "key,status", "--paginate", "--json"]]
    calls.clear()
    fake_acli(monkeypatch, [{"key": "PIX-2"}], calls)
    assert bip.jira_in_progress(["PIX-2"]) == ({"PIX-2": "In Progress"}, None)
    calls.clear()
    assert bip.jira_in_progress([]) == ({}, None)
    assert calls == []


def test_jira_in_progress_failure(monkeypatch):
    fake_acli(monkeypatch, RuntimeError(ACLI_ERR), [])
    assert bip.jira_in_progress(["PIX-2"]) == ({}, ACLI_ERR)
    fake_acli(monkeypatch, {"a": 1}, [])
    assert bip.jira_in_progress(["PIX-2"]) == ({}, "acli search gave no issue list")


def test_label_cuts_and_cleans():
    evil = "a" * 50 + "\x1b[31m\n" + "b" * 150
    out = bip.label([br(evil)])
    assert out.startswith("branch ") and len(out) <= 87
    assert not any(ord(c) < 32 or ord(c) == 127 for c in out)
    hits = [{"kind": "status", "name": "In Progress"}, {"kind": "worktree", "name": "/r/wt/pix-2-login", "branch": "pix-2-login"},
            br("origin-only/PIX-2")]
    assert bip.label(hits) == "Jira status In Progress; worktree pix-2-login (+1 more)"


def test_hits_gate_off_reads_nothing(monkeypatch):
    monkeypatch.setenv("SUPERLITE_IN_PROGRESS_LIVE", "0")
    monkeypatch.setattr(bip, "git_names", lambda root: (_ for _ in ()).throw(AssertionError("git read")))
    monkeypatch.setattr(bip, "jira_in_progress", lambda keys: (_ for _ in ()).throw(AssertionError("acli read")))
    assert bip.hits([{"number": "PIX-2"}], True, Path(".")) == ({}, [])


def test_hits_lines_on_failures(monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)
    fake_acli(monkeypatch, RuntimeError(ACLI_ERR), [])
    monkeypatch.setattr(bip, "git_names", lambda root: ([], "git worktree list failed: boom"))
    assert bip.hits([{"number": "PIX-2"}], True, Path(".")) == ({}, [
        "in progress: Jira status not read (acli jira workitem search failed: x); worktrees and branches still checked",
        "in progress: worktrees and branches not read (git worktree list failed: boom)"])


def test_hits_example(monkeypatch):
    monkeypatch.delenv("SUPERLITE_IN_PROGRESS_LIVE", raising=False)
    monkeypatch.setattr(bip, "git_names", lambda root: ([br("feature/PIX-3-x")], None))
    monkeypatch.setattr(bip, "jira_in_progress", lambda keys: ({"PIX-2": "In Review"}, None))
    got = bip.hits([{"number": "PIX-2"}, {"number": "PIX-3"}], True, Path("."))
    assert got == ({"PIX-2": [{"kind": "status", "name": "In Review"}], "PIX-3": [br("feature/PIX-3-x")]}, [])
