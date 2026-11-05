"""autocommit apply: unrelated changes stay in the tree (named, never committed); a checkpointed file edited again refuses."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autocommit import SCRIPTS, make_repo, two_tasks, write, git, run  # noqa: E402


def tracked_repo(tmp_path):
    """A repo whose base commit tracks package.json, with two checkpointed tasks on top."""
    repo = make_repo(tmp_path)
    write(repo, "package.json", '{"version": "1.0.0"}\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "package")
    two_tasks(repo)
    return repo


def test_apply_keeps_version_bump_uncommitted(tmp_path):
    repo = tracked_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    write(repo, "package.json", '{"version": "1.0.1"}\n')  # the version bump, after the run
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "rev-list", "--count", f"{base}..HEAD") == "2"
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == "M package.json"
    assert git(repo, "diff", "--name-only", base, "HEAD").splitlines() == ["src/a.py", "src/b.py", "tests/test_a.py"]
    assert git(repo, "show", "HEAD:package.json") == '{"version": "1.0.0"}'
    left = [ln for ln in r.stdout.splitlines() if "left uncommitted" in ln]
    assert len(left) == 1 and "package.json" in left[0]
    assert git(repo, "for-each-ref", "refs/superlite") == ""


def test_apply_keeps_untracked_stray(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    write(repo, "notes.txt", "mine\n")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == "?? notes.txt"
    assert (repo / "notes.txt").read_text() == "mine\n"
    assert any("left uncommitted" in ln and "notes.txt" in ln for ln in r.stdout.splitlines())
    assert "notes.txt" not in git(repo, "ls-tree", "-r", "--name-only", "HEAD")


def test_apply_keeps_staged_stray_staged(tmp_path):
    repo = tracked_repo(tmp_path)
    write(repo, "package.json", '{"version": "1.0.1"}\n')
    git(repo, "add", "package.json")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == "M  package.json"


def test_apply_without_stray_names_nothing_left(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left uncommitted" not in r.stdout
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_apply_refuses_dirty_checkpointed_file(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    head = git(repo, "rev-parse", "HEAD")
    write(repo, "src/a.py", "def parse(t):\n    return t.strip()\n")  # edited again after its checkpoint
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode != 0 and "src/a.py" in r.stderr
    assert "src/b.py" not in r.stderr and "stash" not in r.stderr + r.stdout
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "for-each-ref", "refs/superlite") != ""


def test_no_message_suggests_stash():
    src = (SCRIPTS / "autocommit.py").read_text(encoding="utf-8")
    assert "stash" not in src
