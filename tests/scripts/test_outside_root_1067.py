"""The project root never counts as outside: a linked worktree's main checkout root itself passes the #1015 scan (#1067)."""
import os, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import fleet_roles  # noqa: E402

GENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, check=True, env=GENV).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    main = tmp_path / "main"; main.mkdir()
    git(main, "init", "-q"); (main / "a.md").write_text("a\n")
    git(main, "add", "a.md"); git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    wt = main / ".claude" / "worktrees" / "b1"
    git(main, "worktree", "add", "-q", "-b", "b1", str(wt))
    (wt / ".superlite").mkdir()
    monkeypatch.setattr(fleet_roles, "SKILLS", tmp_path / "plug" / "skills")
    return main.resolve(), wt.resolve()


def test_main_checkout_of_a_worktree(repo):
    main, wt = repo
    assert fleet.main_checkout(wt) == main
    assert fleet.main_checkout(main) is None


def test_main_checkout_without_a_gitdir_line_is_none(tmp_path):
    assert fleet.main_checkout(tmp_path) is None
    (tmp_path / ".git").write_text("not a gitdir line\n")
    assert fleet.main_checkout(tmp_path) is None


def test_main_checkout_root_itself_is_not_outside(repo):
    main, wt = repo
    text = f"Read code here, not in {main}. Also not in {main}/ and `{main}`.\n"
    assert fleet.outside_paths(text, wt, wt / ".superlite") == []


def test_paths_below_the_main_checkout_stay_outside(repo):
    main, wt = repo
    assert fleet.outside_paths(f"Read {main}/a.md\n", wt, wt / ".superlite") == [f"{main}/a.md"]


def test_project_root_itself_passes_in_a_main_run(repo):
    main, _ = repo
    (main / ".superlite").mkdir()
    assert fleet.outside_paths(f"Project: {main} and {main}/ and {main}/a.md\n", main, main / ".superlite") == []


def test_brief_naming_the_main_checkout_root_is_accepted(repo):
    main, wt = repo
    b = wt / ".superlite" / "briefs" / "r.md"; b.parent.mkdir(parents=True)
    b.write_text(f"Read code in {wt}, not in {main}.\n")
    assert fleet_io.brief_refusal(wt / ".superlite", b, "research") is None
    b.write_text(f"Read {main}/a.md\n")
    assert "names paths outside the project" in fleet_io.brief_refusal(wt / ".superlite", b, "research")


def test_submodule_style_git_file_is_not_a_worktree(tmp_path):
    sup = tmp_path / "super"
    (sup / ".git" / "modules" / "sub").mkdir(parents=True)
    sub = sup / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert fleet.main_checkout(sub) is None
