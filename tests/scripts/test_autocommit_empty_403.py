"""#403: autocommit apply writes no commit whose tree equals its parent's."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autocommit import SCRIPTS, make_repo, write, git, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


def cp(repo, monkeypatch, tid, contents, files=None):
    monkeypatch.chdir(repo)
    for rel, text in contents.items():
        write(repo, rel, text)
    return autocommit.checkpoint(tid, f"{tid.lower()} work", files or list(contents), "plan.md")


def subjects(repo, base):
    return git(repo, "log", "--format=%s", f"{base}..HEAD").splitlines()


def test_restored_task_gets_no_commit(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", {"README.md": "v1\n"})
    cp(repo, monkeypatch, "T1", {"README.md": "base\n"})
    cp(repo, monkeypatch, "T2", {"b.py": "b\n"})
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T2: t2 work"]
    assert "apply: skipped T1: t1 work (no change left)" in r.stdout
    assert "applied 1 commit(s) on " in r.stdout
    assert "- T1: t1 work" not in r.stdout
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "for-each-ref", "refs/superlite") == ""


def test_every_task_restored_leaves_head(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", {"README.md": "v1\n"})
    cp(repo, monkeypatch, "T1", {"README.md": "base\n"})
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "rev-parse", "HEAD") == base
    assert "applied 0 commit(s) on " in r.stdout
    assert "apply: skipped T1: t1 work (no change left)" in r.stdout
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "for-each-ref", "refs/superlite") == ""
    assert not (repo / ".superlite" / "checkpoints.json").exists()


def test_new_file_deleted_again_gets_no_commit(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", {"n.py": "n\n"})
    (repo / "n.py").unlink()
    cp(repo, monkeypatch, "T1", {}, files=["n.py"])
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "rev-parse", "HEAD") == base
    assert "apply: skipped T1: t1 work (no change left)" in r.stdout


def test_no_squash_skips_an_unchanged_checkpoint(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", {"README.md": "base\n"})
    cp(repo, monkeypatch, "T2", {"b.py": "b\n"})
    r = run("autocommit", "apply", "--no-squash", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T2: t2 work"]
    assert "apply: skipped T1: t1 work (no change left)" in r.stdout


def test_revert_checkpoint_kept_without_squash(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", {"README.md": "v1\n"})
    cp(repo, monkeypatch, "T1", {"README.md": "base\n"})
    r = run("autocommit", "apply", "--no-squash", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T1: t1 work", "T1: t1 work"]
    assert "skipped" not in r.stdout


def test_unborn_head_all_skipped_stays_unborn(tmp_path, monkeypatch):
    repo = tmp_path / "u"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    monkeypatch.chdir(repo)
    write(repo, "n.py", "n\n")
    autocommit.checkpoint("T1", "t1 work", ["n.py"], "plan.md")
    (repo / "n.py").unlink()
    autocommit.checkpoint("T1", "t1 work", ["n.py"], "plan.md")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    head = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=repo, capture_output=True, text=True)
    assert head.returncode != 0
    assert "applied 0 commit(s) on " in r.stdout
    assert "apply: skipped T1: t1 work (no change left)" in r.stdout


def test_moved_head_skips_restored_task(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    cp(repo, monkeypatch, "T1", {"a.py": "v1\n"})
    (repo / "a.py").unlink()
    cp(repo, monkeypatch, "T1", {}, files=["a.py"])
    cp(repo, monkeypatch, "T2", {"b.py": "b\n"})
    write(repo, "other.txt", "o\n")
    git(repo, "add", "other.txt")
    git(repo, "commit", "-q", "-m", "moved")
    moved = git(repo, "rev-parse", "HEAD")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, moved) == ["T2: t2 work"]
    assert "applied 1 commit(s) on " in r.stdout
