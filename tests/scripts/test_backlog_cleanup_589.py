"""#589: git-only cleanup, owed cleanups, start check."""
import subprocess, sys, types
from pathlib import Path
import pytest
from backlog_fixtures import APPROVED, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402
from test_backlog_run import bk, get, put, run  # noqa: E402,F401  (bk is a fixture)


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.email=a@b", "-c", "user.name=n", *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "root"; r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "f").write_text("x"); git(r, "add", "f"); git(r, "commit", "-q", "-m", "i")
    wt = tmp_path / "wts" / "b1"
    git(r, "worktree", "add", "-q", str(wt), "-b", "superlite/b1")
    return types.SimpleNamespace(root=r, wt=wt)


def unmerged(repo):
    (repo.wt / "g").write_text("y"); git(repo.wt, "add", "g"); git(repo.wt, "commit", "-q", "-m", "g")


def test_clean_removal_deletes_the_branch(repo):
    assert br.remove_worktree(repo.root, repo.wt, "superlite/b1", "B1") == [f"B1 worktree {repo.wt} removed, branch superlite/b1 deleted"]


def test_pr_head_branch_is_force_deleted(repo):
    unmerged(repo); head = git(repo.wt, "rev-parse", "superlite/b1")
    assert br.remove_worktree(repo.root, repo.wt, "superlite/b1", "B1", head) == [f"B1 worktree {repo.wt} removed, branch superlite/b1 deleted (PR head)"]
    assert git(repo.root, "branch", "--list", "superlite/b1") == ""


def test_unmerged_branch_kept_without_head(repo, monkeypatch):
    unmerged(repo)
    calls = []
    real = br._run
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: calls.append(cmd) or real(cmd, cwd))
    assert br.remove_worktree(repo.root, repo.wt, "superlite/b1", "B1") == [f"B1 worktree {repo.wt} removed, branch superlite/b1 kept (not merged)"]
    assert not any("-D" in c for c in calls)
    assert git(repo.root, "branch", "--list", "superlite/b1") != ""


def test_other_head_keeps_the_branch(repo):
    unmerged(repo)
    assert br.remove_worktree(repo.root, repo.wt, "superlite/b1", "B1", "0" * 40)[0].endswith("kept (not merged)")


def test_remove_failure_keeps_gits_error_line(tmp_path, monkeypatch):
    wt = tmp_path / "w"; wt.mkdir()
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (128, "hint: x\nfatal: x\nmore"))
    assert br.remove_worktree(tmp_path, wt, "superlite/b1", "B1") == [f"B1 worktree {wt} kept: fatal: x"]


def shipped_setup(bk, tmp_path):
    wt = tmp_path / "wt1"; wt.mkdir()
    put(bk, b("B1", ["a.py"], "running", lead=None, worktree=str(wt), branch="superlite/b1", cleaned=True))
    return wt


def test_done_path_never_runs_maxapp(bk, tmp_path, monkeypatch):
    wt = shipped_setup(bk, tmp_path)
    calls = []
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: calls.append(cmd) or (0, ""))
    out = br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), wt, push=False)
    assert not any(c[0] == "maxapp" for c in calls)
    assert calls[0][:3] == ["git", "worktree", "remove"]
    assert out[-1] == f"B1 worktree {wt} removed, branch superlite/b1 deleted"
    assert "cleanup_owed" not in get(bk, "B1")


def test_done_path_passes_head(bk, tmp_path, monkeypatch):
    wt = shipped_setup(bk, tmp_path)
    def fake(cmd, cwd):
        if cmd[:3] == ["git", "branch", "-d"]:
            return 1, "not fully merged"
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "abc"
        return 0, ""
    monkeypatch.setattr(br, "_run", fake)
    out = br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), wt, push=False, head="abc")
    assert out[-1].endswith("deleted (PR head)")


def test_cleanup_line_carries_git_error(bk, tmp_path, monkeypatch):
    wt = shipped_setup(bk, tmp_path)
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (1, "fatal: this operation must be run in a work tree\nmaxapp: worktree remove failed"))
    out = br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), wt)
    line = "B1 cleanup: maxapp: worktree remove failed: fatal: this operation must be run in a work tree"
    assert out[-1] == line
    assert get(bk, "B1")["cleanup_owed"] == line


def test_cleanup_line_names_the_bare_cause(bk, tmp_path, monkeypatch):
    wt = shipped_setup(bk, tmp_path)
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (1, "maxapp: failed"))
    monkeypatch.setitem(sys.modules, "worktree", types.SimpleNamespace(bare_flag=lambda s: "core.bare=true in /r/.git/config"))
    out = br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), wt)
    assert out[-1] == "B1 cleanup: maxapp: failed; cause: core.bare=true in /r/.git/config"


def test_clean_cleanup_pops_the_owed_record(bk, tmp_path, monkeypatch):
    wt = shipped_setup(bk, tmp_path)
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").__setitem__("cleanup_owed", "old"))
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (0, "ok"))
    br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), wt)
    assert "cleanup_owed" not in get(bk, "B1")


def test_status_shows_owed_cleanup(tmp_path):
    wt = tmp_path / "wt"; wt.mkdir()
    gone = tmp_path / "gone"
    d = {"repo": "o/r", "approved_ship": APPROVED, "round": ["B2"], "batches": [
        b("B1", ["a"], "shipped", worktree=str(wt), cleanup_owed="B1 cleanup: boom"),
        b("B3", ["c"], "shipped", worktree=str(gone), cleanup_owed="B3 cleanup: boom"),
        b("B2", ["b"], "planned")]}
    lines = bs.status_lines(d)
    row = [x for x in lines if x.startswith("B1 |")]
    assert len(row) == 1 and row[0].endswith("cleanup owed")
    i = lines.index(row[0])
    assert f"cleanup owed: B1 {wt}: B1 cleanup: boom; fix it, then maxapp ship -C {wt}" in lines
    assert not any(x.startswith("B3 |") or x.startswith("cleanup owed: B3") for x in lines)
    assert any(x.startswith("B2 |") for x in lines) and i


class BareCheckout(Exception):
    pass


def fake_wt(monkeypatch, ensure, bare=""):
    ns = types.SimpleNamespace(ensure=ensure, BareCheckout=BareCheckout, Taken=type("Taken", (Exception,), {}),
                               BadBranch=type("BadBranch", (Exception,), {}), PARENT=".claude/worktrees", bare_flag=lambda s: bare)
    monkeypatch.setitem(sys.modules, "worktree", ns)


def test_start_blocks_on_bare_flag(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]), b("B2", ["b.py"]))
    def ensure(topic, start):
        if topic.startswith("b1"):
            raise BareCheckout("core.bare=true in /r/.git/config: fix it")
        wt = Path(start) / ".claude" / "worktrees" / f"superlite-{topic}"; (wt / ".superlite").mkdir(parents=True, exist_ok=True); return wt, "created"
    fake_wt(monkeypatch, ensure)
    rc, out = run(capsys, "start", "B1", "B2")
    assert rc == 2
    assert "BLOCKED: B1 not started: core.bare=true in /r/.git/config: fix it" in out.splitlines()
    assert get(bk, "B1")["state"] == "planned" and get(bk, "B2")["state"] == "running"


def test_start_blocks_on_root_path(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    fake_wt(monkeypatch, lambda topic, start: (Path(start), "no-repo"), bare="core.bare=true in x")
    rc, out = run(capsys, "start", "B1")
    assert rc == 2
    assert out.splitlines() == [f"BLOCKED: B1 not started: worktree ensure gave {bk.root} (no-repo), not a linked worktree under {bk.root}/.claude/worktrees; cause: core.bare=true in x"]
    assert get(bk, "B1")["state"] == "planned"
