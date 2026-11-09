"""commit_task --plan P works in the checkout holding P (#365)."""
import json
import re
import shutil
import sys

from test_autocommit import ENV, SCRIPTS, git, make_repo, run, write  # noqa: F401

sys.path.insert(0, str(SCRIPTS))


def pair(tmp_path):
    repo = make_repo(tmp_path)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "feat")
    (wt / ".superlite").mkdir()
    write(wt, ".superlite/stable.json", "{}")
    write(wt, "src/a.py", "A = 1\n")
    write(wt, "tests/test_a.py", "def test_a():\n    assert 1\n")
    return repo, wt, str(wt / "plan.md")


def first(tmp_path):
    repo, wt, plan = pair(tmp_path)
    r = run("commit_task", "T1", "--plan", plan, cwd=repo)
    return repo, wt, plan, r


def test_absolute_plan_from_main_checkout(tmp_path):
    repo, wt, plan, r = first(tmp_path)
    assert r.returncode == 0, r.stderr
    sha = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert git(wt, "show", sha + ":src/a.py") == "A = 1"
    cps = json.loads((wt / ".superlite/checkpoints.json").read_text())
    assert "T1" in json.dumps(cps)
    assert not (repo / ".superlite/checkpoints.json").exists()
    assert any(ln.startswith("- commit T1 ") for ln in (wt / ".superlite/progress.md").read_text().splitlines())
    assert git(repo, "status", "--porcelain") == ""


def test_apply_from_main_checkout(tmp_path):
    repo, wt, plan, r = first(tmp_path)
    assert r.returncode == 0, r.stderr
    head = git(repo, "rev-parse", "HEAD")
    r = run("autocommit", "apply", "--plan", plan, cwd=repo)
    assert r.returncode == 0, r.stderr
    assert git(wt, "show", "feat:src/a.py") == "A = 1"
    assert git(repo, "rev-parse", "HEAD") == head


def test_plan_from_a_subdirectory(tmp_path):
    repo, wt, plan = pair(tmp_path)
    r = run("commit_task", "T1", "--plan", "../plan.md", cwd=wt / "src")
    assert r.returncode == 0, r.stderr
    sha = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert git(wt, "show", sha + ":src/a.py") == "A = 1"
    assert not (wt / "src/.superlite").exists()


def test_relative_ledger_keeps_callers_cwd(tmp_path):
    repo, wt, plan = pair(tmp_path)
    r = run("commit_task", "T1", "--plan", plan, "--ledger", "notes/ledger.md", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert "- commit T1 " in (repo / "notes/ledger.md").read_text()
    assert not (wt / "notes").exists()


def test_absolute_also_into_plan_checkout(tmp_path):
    repo, wt, plan = pair(tmp_path)
    write(wt, "src/c.py", "C = 1\n")
    r = run("commit_task", "T1", "--plan", plan, "--also", str(wt / "src/c.py"), "--ruling", "test", cwd=repo)
    assert r.returncode == 0, r.stderr
    sha = r.stdout.strip().split()[-1]
    assert "src/c.py" in git(wt, "ls-tree", "-r", "--name-only", sha)


def test_plan_outside_any_checkout_keeps_cwd(tmp_path):
    repo = make_repo(tmp_path)
    (tmp_path / "outside").mkdir()
    shutil.copy(repo / "plan.md", tmp_path / "outside" / "plan.md")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "tests/test_a.py", "def test_a():\n    assert 1\n")
    r = run("commit_task", "T1", "--plan", str(tmp_path / "outside" / "plan.md"), cwd=repo)
    assert r.returncode == 0, r.stderr
    sha = r.stdout.strip()
    assert git(repo, "show", sha + ":src/a.py") == "A = 1"
