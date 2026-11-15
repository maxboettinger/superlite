# tests/scripts/test_remote_apply.py
import os, subprocess, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import remote_apply as ra  # noqa: E402


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, env=env,
                          capture_output=True, text=True, check=True).stdout.strip()


def put(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"; r.mkdir()
    git(r, "init", "-q")
    for f in ("src/a.py", "src/b.py", "src/c.py", "docs/n.md", "a.py", "c.py"):
        put(r, f, "base\n")
    git(r, "add", "-A"); git(r, "commit", "-qm", "base")
    return r


def show(r, ref, path):
    return git(r, "show", f"{ref}:{path}")


def test_start_commit_keeps_index(repo):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "a.py", "edited\n"); put(repo, "new.py", "n\n"); git(repo, "add", "new.py")
    before = git(repo, "status", "--porcelain")
    (repo / "c.py").unlink()
    before = git(repo, "status", "--porcelain")
    sha = ra.start_commit(str(repo), base, ["a.py", "c.py", "new.py"], {".superlite/prime.md": b"x"}, "refs/superlite/remote/p/W2/start")
    assert git(repo, "status", "--porcelain") == before
    assert git(repo, "rev-parse", "HEAD") == base
    assert git(repo, "rev-parse", "refs/superlite/remote/p/W2/start") == sha
    assert git(repo, "rev-parse", sha + "^") == base
    assert show(repo, sha, "a.py") == "edited"
    assert show(repo, sha, ".superlite/prime.md") == "x"
    assert git(repo, "ls-tree", "--name-only", sha, "c.py") == ""
    assert show(repo, sha, "new.py") == "n"


def test_snapshot_excludes_superlite(repo):
    put(repo, "a.py", "edited\n"); put(repo, "b.py", "new\n"); (repo / "c.py").unlink()
    put(repo, ".superlite/x", "no\n")
    before = git(repo, "status", "--porcelain")
    sha = ra.snapshot(str(repo), "refs/superlite/remote/p/W2/stop")
    assert git(repo, "status", "--porcelain") == before
    assert git(repo, "rev-parse", sha + "^") == git(repo, "rev-parse", "HEAD")
    assert show(repo, sha, "a.py") == "edited" and show(repo, sha, "b.py") == "new"
    names = git(repo, "ls-tree", "-r", "--name-only", sha).split("\n")
    assert "c.py" not in names and not any(n.startswith(".superlite") for n in names)
    assert git(repo, "rev-parse", "refs/superlite/remote/p/W2/stop") == sha


def _stop(repo):
    start = git(repo, "rev-parse", "HEAD")
    put(repo, "src/a.py", "stop-a\n"); put(repo, "src/b.py", "stop-b\n"); put(repo, "docs/n.md", "stop-n\n")
    put(repo, ".superlite/z", "z\n")
    (repo / "src/c.py").unlink()
    stop = ra.snapshot(str(repo), "refs/x/stop")
    git(repo, "reset", "-q", "--hard", start)
    return start, stop


def test_apply_allowed_and_skipped(repo):
    start, stop = _stop(repo)
    r = ra.apply(str(repo), start, stop, ["src/*.py"])
    assert r == {"applied": ["src/a.py", "src/b.py", "src/c.py"], "skipped": ["docs/n.md"], "conflicts": []}
    assert (repo / "src/a.py").read_text() == "stop-a\n"
    assert not (repo / "src/c.py").exists()
    assert (repo / "docs/n.md").read_text() == "base\n"


def test_apply_none_allows_all_but_superlite(repo):
    start, stop = _stop(repo)
    r = ra.apply(str(repo), start, stop, None)
    assert "docs/n.md" in r["applied"] and r["conflicts"] == [] and r["skipped"] == []
    assert (repo / "docs/n.md").read_text() == "stop-n\n"


def test_apply_conflict_writes_nothing(repo):
    start, stop = _stop(repo)
    put(repo, "src/b.py", "local-edit\n")
    r = ra.apply(str(repo), start, stop, ["src/*.py"])
    assert r["conflicts"] == ["src/b.py"] and r["applied"] == []
    assert (repo / "src/a.py").read_text() == "base\n"
    assert (repo / "src/b.py").read_text() == "local-edit\n"
    assert (repo / "src/c.py").read_text() == "base\n"


def test_apply_local_equal_to_stop_is_applied(repo):
    start, stop = _stop(repo)
    put(repo, "src/a.py", "stop-a\n")
    r = ra.apply(str(repo), start, stop, ["src/a.py"])
    assert r["applied"] == ["src/a.py"] and r["conflicts"] == []


def test_main_snapshot(repo, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    put(repo, "a.py", "e\n")
    assert ra.main(["snapshot", "--ref", "refs/x/s"]) == 0
    assert capsys.readouterr().out.strip() == git(repo, "rev-parse", "refs/x/s")


def test_main_failure(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ra.main(["snapshot", "--ref", "refs/x/s"]) == 1
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_symlink_survives_start_commit_and_apply(repo):
    os.symlink("a.py", repo / "ln")
    git(repo, "add", "ln"); git(repo, "commit", "-qm", "ln")
    base = git(repo, "rev-parse", "HEAD")
    sha = ra.start_commit(str(repo), base, ["ln"], {}, "refs/x/start")
    assert git(repo, "ls-tree", sha, "ln").split()[0] == "120000"
    os.unlink(repo / "ln"); os.symlink("c.py", repo / "ln")
    stop = ra.snapshot(str(repo), "refs/x/stop")
    git(repo, "reset", "-q", "--hard", base)
    assert os.readlink(repo / "ln") == "a.py"
    r = ra.apply(str(repo), sha, stop, None)
    assert r["conflicts"] == [] and r["applied"] == ["ln"]
    assert (repo / "ln").is_symlink() and os.readlink(repo / "ln") == "c.py"


def test_executable_stays_executable(repo):
    start = git(repo, "rev-parse", "HEAD")
    put(repo, "run.sh", "#!/bin/sh\n"); os.chmod(repo / "run.sh", 0o755)
    stop = ra.snapshot(str(repo), "refs/x/stop")
    git(repo, "reset", "-q", "--hard", start); (repo / "run.sh").unlink()
    r = ra.apply(str(repo), start, stop, None)
    assert r["applied"] == ["run.sh"] and os.access(repo / "run.sh", os.X_OK)
