import json, subprocess, sys, types
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402


def cfg(root, obj):
    d = Path(root) / ".superlite"; d.mkdir(exist_ok=True)
    (d / "cleanup-cmd.json").write_text(obj if isinstance(obj, str) else json.dumps(obj))


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.email=a@b", "-c", "user.name=n", *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "root"; r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "f").write_text("x"); git(r, "add", "f"); git(r, "commit", "-q", "-m", "i")
    wt = tmp_path / "wts" / "b2"
    git(r, "worktree", "add", "-q", str(wt), "-b", "superlite/b2-x")
    stops = []
    monkeypatch.setattr(backlog_run, "_stop", lambda sd, lead: stops.append(lead))
    return types.SimpleNamespace(root=r, wt=wt, stops=stops, tmp=tmp_path)


def test_cleanup_cmd_missing_bad_json_and_empty(tmp_path, capsys):
    assert backlog_run.cleanup_cmd(tmp_path) is None
    assert capsys.readouterr().err == ""
    cfg(tmp_path, "{nope")
    assert backlog_run.cleanup_cmd(tmp_path) is None
    assert "cleanup-cmd.json ignored: " in capsys.readouterr().err
    for bad in ({"cleanup": ""}, {"cleanup": 3}, [1], {}):
        cfg(tmp_path, bad)
        assert backlog_run.cleanup_cmd(tmp_path) is None
        assert capsys.readouterr().err == 'cleanup-cmd.json ignored: needs a JSON object with a "cleanup" command\n'
    cfg(tmp_path, {"cleanup": "echo hi"})
    assert backlog_run.cleanup_cmd(tmp_path) == "echo hi"


def test_cleanup_without_config_is_none(repo):
    assert backlog_run.project_cleanup(repo.root, repo.wt, "superlite/b1-x", "B1") is None


def test_cleanup_quotes_a_worktree_path_with_spaces(tmp_path, monkeypatch):
    wt = tmp_path / "my wt"; wt.mkdir()
    cfg(tmp_path, {"cleanup": "printf %s {worktree} > out.txt; printf %s \"$SUPERLITE_WORKTREE|$SUPERLITE_BRANCH|$SUPERLITE_BATCH\" > env.txt"})
    assert backlog_run.project_cleanup(tmp_path, wt, "br", "B1") is None
    assert (wt / "out.txt").read_text() == str(wt)
    assert (wt / "env.txt").read_text() == f"{wt}|br|B1"


def test_cleanup_expands_branch_shell_quoted(tmp_path):
    wt = tmp_path / "wt"; wt.mkdir()
    cfg(tmp_path, {"cleanup": "printf %s {branch} > out.txt"})
    assert backlog_run.project_cleanup(tmp_path, wt, "feat x;y", "B1") is None
    assert (wt / "out.txt").read_text() == "feat x;y"


def test_cleanup_runs_nothing_for_an_empty_worktree(tmp_path, monkeypatch):
    cfg(tmp_path, {"cleanup": "printf x > out.txt"})
    monkeypatch.chdir(tmp_path)
    assert backlog_run.project_cleanup(tmp_path, Path(""), "br", "B1") is None
    assert not (tmp_path / "out.txt").exists()


def test_cleanup_failure_and_timeout_lines(tmp_path, monkeypatch):
    wt = tmp_path / "w"; wt.mkdir()
    cfg(tmp_path, {"cleanup": "echo oops; exit 3"})
    assert backlog_run.project_cleanup(tmp_path, wt, "br", "B1") == "B1 project cleanup: exit 3: oops"
    cfg(tmp_path, {"cleanup": "exit 4"})
    assert backlog_run.project_cleanup(tmp_path, wt, "br", "B1") == "B1 project cleanup: exit 4"
    monkeypatch.setattr(backlog_run, "CLEANUP_TIMEOUT", 1)
    cfg(tmp_path, {"cleanup": "sleep 5"})
    assert backlog_run.project_cleanup(tmp_path, wt, "br", "B1") == "B1 project cleanup: timed out after 1 s"


def B2(repo, **kw):
    return {"id": "B2", "worktree": str(repo.wt), "branch": "superlite/b2-x", **kw}


def test_drop_worktree_removes_a_clean_one_and_its_merged_branch(repo):
    assert backlog_run.drop_worktree(repo.root, B2(repo)) == [f"B2 worktree {repo.wt} removed, branch superlite/b2-x deleted"]
    assert not repo.wt.exists()


def test_drop_worktree_keeps_uncommitted_work(repo):
    (repo.wt / "new.txt").write_text("u")
    out = backlog_run.drop_worktree(repo.root, B2(repo))
    assert len(out) == 1 and out[0].startswith(f"B2 worktree {repo.wt} kept: ")
    assert repo.wt.is_dir()


def test_drop_worktree_keeps_an_unmerged_branch(repo):
    (repo.wt / "c.txt").write_text("c"); git(repo.wt, "add", "c.txt"); git(repo.wt, "commit", "-q", "-m", "c")
    assert backlog_run.drop_worktree(repo.root, B2(repo)) == [f"B2 worktree {repo.wt} removed, branch superlite/b2-x kept (not merged)"]


def test_drop_worktree_refuses_the_main_root(repo):
    b = {"id": "B2", "worktree": str(repo.root), "branch": "main"}
    assert backlog_run.drop_worktree(repo.root, b) == [f"B2 worktree {repo.root} kept: it is the main checkout"]
    assert repo.root.is_dir()


def test_drop_worktree_nothing_to_do(repo):
    assert backlog_run.drop_worktree(repo.root, {"id": "B2"}) == []
    assert backlog_run.drop_worktree(repo.root, {"id": "B2", "worktree": str(repo.tmp / "gone")}) == []


def test_drop_worktree_stops_the_lead_and_runs_the_cleanup_first(repo):
    cfg(repo.root, {"cleanup": "printf x > {worktree}/../ran.txt"})
    out = backlog_run.drop_worktree(repo.root, B2(repo, lead="W9"))
    assert repo.stops == ["W9"]
    assert (repo.wt.parent / "ran.txt").read_text() == "x"
    assert out[-1].startswith(f"B2 worktree {repo.wt} removed")


def test_shipped_runs_the_cleanup_unless_cleaned(repo, monkeypatch):
    calls = []
    monkeypatch.setattr(backlog_run, "_run", lambda cmd, cwd, timeout=None: calls.append(cmd) or (0, ""))
    sd = repo.root / ".superlite"
    cfg(repo.root, {"cleanup": "printf x > ran.txt; echo bad; exit 2"})
    import backlog_state as bs
    p = bs.path(repo.root)
    bs.update(p, lambda d: d["batches"].append({"id": "B2", "state": "running", "issues": [2], "files": []}))
    b = {"id": "B2", "lead": "W1", "worktree": str(repo.wt), "branch": "superlite/b2-x", "open_issues": [5]}
    out = backlog_run._shipped(p, sd, repo.root, b, repo.wt)
    assert (repo.wt / "ran.txt").exists()
    assert out[-1] == "B2 project cleanup: exit 2: bad"
    assert out.index("B2 OPEN #5") < len(out) - 1
    (repo.wt / "ran.txt").unlink()
    out = backlog_run._shipped(p, sd, repo.root, {**b, "cleaned": True}, repo.wt)
    assert not (repo.wt / "ran.txt").exists()
    assert not any("project cleanup" in x for x in out)
