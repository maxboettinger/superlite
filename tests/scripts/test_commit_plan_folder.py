"""commit_task ignores the plan's own folder (sibling spec, review) but still commits owned paths there."""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (PLAN_FIX, SCRIPTS, ENV, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = "docs/plans/p.md"


def repo_with_plan(tmp_path, extra=""):
    repo = make_repo(tmp_path)
    (repo / "docs" / "plans").mkdir(parents=True)
    text = (PLAN_FIX / "plan.md").read_text(encoding="utf-8").replace("`docs/`", "`doc/`") + extra  # T4 must not own docs/
    (repo / PLAN).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def commit(repo, task="T1", plan=PLAN):
    return run("commit_task", task, "--plan", plan, cwd=repo, env=ENV)


def test_untracked_sibling_spec_does_not_block(tmp_path):
    repo = repo_with_plan(tmp_path)
    write(repo, "docs/plans/p.spec.md", "spec\n")
    write(repo, "src/a.py", "X = 1\n")
    r = commit(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout
    assert r.stdout.strip() == git(repo, "rev-parse", "HEAD")
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "src/a.py"
    assert "docs/plans/p.spec.md" in git(repo, "status", "--porcelain")


def test_modified_plan_itself_does_not_block(tmp_path):
    repo = repo_with_plan(tmp_path)
    (repo / PLAN).write_text((repo / PLAN).read_text(encoding="utf-8") + "\nedit\n")
    write(repo, "src/a.py", "X = 1\n")
    r = commit(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "src/a.py"


def test_owned_path_in_plan_folder_is_committed(tmp_path):
    extra = ("\n### T7 · notes · Complexity 1 · Est. context 5k · Est. time 1 min\n\n"
             "**Owns:** `docs/plans/notes.md`\n")
    repo = repo_with_plan(tmp_path, extra)
    write(repo, "docs/plans/notes.md", "notes\n")
    write(repo, "docs/plans/p.spec.md", "spec\n")
    r = commit(repo, "T7")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "docs/plans/notes.md"


def test_root_plan_keeps_blocking_unowned_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "other.txt", "oops\n")
    r = commit(repo, plan="plan.md")
    assert r.returncode == 1
    assert "out-of-scope other.txt" in r.stdout


def test_plan_folder_values(tmp_path, monkeypatch):
    repo = repo_with_plan(tmp_path)
    monkeypatch.chdir(repo)
    assert commit_task.plan_folder("docs/plans/2026-10-26-x.md") == "docs/plans/"
    assert commit_task.plan_folder("plan.md") == ""
    assert commit_task.plan_folder("/tmp/elsewhere/plan.md") == ""


def test_changed_files_skip_prefix(tmp_path, monkeypatch):
    repo = repo_with_plan(tmp_path)
    write(repo, "docs/plans/x.spec.md", "s\n")
    write(repo, "src/a.py", "X\n")
    monkeypatch.chdir(repo)
    assert commit_task.changed_files("docs/plans/") == ["src/a.py"]
    assert commit_task.changed_files("") == ["docs/plans/x.spec.md", "src/a.py"]


def test_plan_folder_abs_subdir_backslash_root(tmp_path, monkeypatch):
    repo = repo_with_plan(tmp_path)
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo)
    assert commit_task.plan_folder(str(repo / PLAN)) == "docs/plans/"
    assert commit_task.plan_folder("docs\\plans\\p.md") == "docs/plans/"
    monkeypatch.chdir(repo / "sub")
    assert commit_task.plan_folder("../docs/plans/p.md") == "docs/plans/"
    assert commit_task.plan_folder(str(repo / "plan.md")) == ""
