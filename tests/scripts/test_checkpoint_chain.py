"""Hidden checkpoints: the chain survives a respelled plan path (#83) and a git-mv'd owned file (#82)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_autocommit import git, make_repo, run, write  # noqa: E402


def commit(repo, task, plan="plan.md"):
    r = run("commit_task", task, "--plan", plan, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip()


def files_in(repo, sha):
    return git(repo, "ls-tree", "-r", "--name-only", sha).splitlines()


def test_absolute_plan_path_keeps_the_chain(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    s1 = commit(repo, "T1", "plan.md")
    write(repo, "src/b.py", "B = 1\n")
    s2 = commit(repo, "T2", str(repo / "plan.md"))
    assert git(repo, "rev-parse", f"{s2}^") == s1
    assert "src/a.py" in files_in(repo, s2)


def test_respelled_plan_path_keeps_every_entry(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    commit(repo, "T1", str(repo / "plan.md"))
    write(repo, "src/b.py", "B = 1\n")
    commit(repo, "T2", "./plan.md")
    st = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert [e["task"] for e in st["entries"]] == ["T1", "T2"]


def test_second_checkpoint_after_git_mv_of_owned_file(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "pkg/d.py", "D = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add d")
    git(repo, "mv", "pkg/d.py", "pkg/e.py")
    s1 = commit(repo, "T4")
    write(repo, "pkg/e.py", "E = 2\n")
    s2 = commit(repo, "T4")
    assert git(repo, "rev-parse", f"{s2}^") == s1
    assert "pkg/d.py" not in files_in(repo, s2)
    assert git(repo, "show", f"{s2}:pkg/e.py") == "E = 2"


def test_removed_owned_directory_is_staged_as_deletion(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "pkg/d.py", "D = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add d")
    (repo / "pkg" / "d.py").unlink()
    (repo / "pkg").rmdir()
    monkeypatch.chdir(repo)
    sys.path.insert(0, str(HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts"))
    import autocommit
    sha = autocommit.checkpoint("T1", "rm", ["pkg"], "plan.md")
    assert "pkg/d.py" not in files_in(repo, sha)
