"""autocommit accepts --plan (#290)."""
import json
import sys

from test_autocommit import SCRIPTS, git, make_repo, run, write, two_tasks  # noqa: F401

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


def refs(repo):
    return git(repo, "for-each-ref", "refs/superlite")


def test_apply_accepts_plan_dot_superlite(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", "--plan", ".superlite", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert "applied 2 commit(s)" in r.stdout
    assert git(repo, "log", "-2", "--format=%s").splitlines() == ["T2: lexer", "T1: parser"]
    assert refs(repo) == ""


def test_apply_accepts_plan_equals_form(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", "--no-squash", "--plan=plan.md", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert "applied 2 commit(s)" in r.stdout


def test_plan_before_the_command(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "--plan", ".superlite", "apply", cwd=repo)
    assert r.returncode == 0, r.stderr


def test_plan_from_another_cwd(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    other = tmp_path / "elsewhere"
    other.mkdir()
    r = run("autocommit", "apply", "--plan", str(repo / ".superlite"), cwd=other)
    assert r.returncode == 0, r.stderr
    assert git(repo, "rev-list", "--count", "HEAD") == "3"
    assert not (other / ".superlite").exists()


def test_on_from_another_cwd_writes_the_checkout(tmp_path):
    repo = make_repo(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    r = run("autocommit", "on", "--plan", str(repo / "plan.md"), cwd=other)
    assert r.returncode == 0, r.stderr
    assert json.loads((repo / ".superlite/autocommit.json").read_text()) == {"autocommit": True}
    assert not (other / ".superlite").exists()


def test_status_and_clean_accept_plan(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "status", "--plan", ".superlite", cwd=repo)
    assert r.returncode == 0 and "checkpoints for run" in r.stdout
    r = run("autocommit", "clean", "--plan", ".superlite", cwd=repo)
    assert r.returncode == 0
    assert refs(repo) == ""


def test_plan_without_value_is_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", "--plan", cwd=repo)
    assert r.returncode == 2
    assert "usage" in r.stderr and "[--plan P]" in r.stderr
    assert refs(repo) != ""


def test_unknown_arg_with_plan_is_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", "--bogus", "--plan", ".superlite", cwd=repo)
    assert r.returncode == 2
    assert refs(repo) != ""


def test_plan_outside_any_checkout_stays_in_cwd(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "status", "--plan", str(tmp_path / "loose" / "plan.md"), cwd=repo)
    assert r.returncode == 0, r.stderr
    assert "checkpoints for run" in r.stdout


def test_split_plan_table():
    sp = autocommit.split_plan
    assert sp(["apply", "--plan", ".superlite", "--no-squash"]) == (["apply", "--no-squash"], ".superlite")
    assert sp(["--plan=plan.md", "status"]) == (["status"], "plan.md")
    assert sp(["apply", "--plan"]) == (["apply"], "")
    assert sp(["apply"]) == (["apply"], None)
    assert sp(["--plan", "a", "--plan", "b"]) == ([], "b")
    assert sp(["--plan="]) == ([], "")


def test_plan_followed_by_option_is_missing_value(tmp_path):
    assert autocommit.split_plan(["apply", "--plan", "--no-squash"]) == (["apply", "--no-squash"], "")
    repo = make_repo(tmp_path)
    two_tasks(repo)
    r = run("autocommit", "apply", "--plan", "--no-squash", cwd=repo)
    assert r.returncode == 2
    assert refs(repo) != ""
