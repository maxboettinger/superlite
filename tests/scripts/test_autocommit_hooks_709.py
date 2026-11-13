"""`sl autocommit apply` runs the project's commit hooks before HEAD moves (#709)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autocommit import ENV, SCRIPTS, git, make_repo, run, two_tasks  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402

GIT_VERSION = autocommit.git_version(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)


def hooks(repo, tmp_path, **scripts):
    """Write each hook (`pre_commit` -> pre-commit) into tmp_path/hooks and point core.hooksPath at it."""
    d = tmp_path / "hooks"
    d.mkdir(exist_ok=True)
    for name, body in scripts.items():
        p = d / name.replace("_", "-")
        p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        p.chmod(0o755)
    git(repo, "config", "core.hooksPath", str(d))
    return d


def state(repo):
    return {"head": git(repo, "rev-parse", "HEAD"), "index": git(repo, "ls-files", "--stage"),
            "refs": git(repo, "for-each-ref", "refs/superlite"),
            "checkpoints": (repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8")}


def fake_old_git(tmp_path):
    """PATH with a git that reports 2.30.0 and has no `hook` command."""
    real = shutil.which("git")
    b = tmp_path / "bin"
    b.mkdir()
    g = b / "git"
    g.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "git version 2.30.0"; exit 0; fi\n'
                 'if [ "$1" = "hook" ]; then echo "git: hook is not a git command" >&2; exit 1; fi\n'
                 f'exec "{real}" "$@"\n', encoding="utf-8")
    g.chmod(0o755)
    return {**ENV, "PATH": f"{b}{os.pathsep}{ENV.get('PATH', '')}"}


def test_git_version_reads_the_first_two_numbers():
    assert autocommit.git_version("git version 2.54.0 (Apple Git-157)") == (2, 54)
    assert autocommit.git_version("git version 2.30.1") == (2, 30)
    assert autocommit.git_version("no version here") == (0, 0)


def test_clean_message_like_git_whitespace_cleanup():
    assert autocommit.clean_message("T1: parser\n\n\nChange-Id: I1  \n\n") == "T1: parser\n\nChange-Id: I1\n"
    assert autocommit.clean_message("\n\nT1: parser") == "T1: parser\n"
    assert autocommit.clean_message(" \n\n") == ""


def test_failing_pre_commit_stops_apply_and_keeps_state(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, pre_commit='echo "pre-commit says no"\nexit 1')
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pre-commit says no" in r.stderr
    assert ("apply: the pre-commit hook failed (exit 1) for T1: parser; HEAD and the checkpoints are unchanged: "
            "fix the cause, then rerun `sl autocommit apply`") in r.stderr
    assert state(repo) == before
    assert not (repo / ".superlite" / "apply-hook.index").exists()


def test_failure_names_the_later_task_and_writes_no_commit(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, pre_commit='if git ls-files --error-unmatch src/b.py >/dev/null 2>&1; then exit 3; fi')
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "apply: the pre-commit hook failed (exit 3) for T2: lexer;" in r.stderr
    assert state(repo) == before


def test_rerun_after_the_fix_applies_the_same_checkpoints(tmp_path):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    two_tasks(repo)
    d = hooks(repo, tmp_path, pre_commit="exit 1")
    assert run("autocommit", "apply", cwd=repo).returncode == 1
    (d / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "applied 2 commit(s)" in r.stdout
    assert git(repo, "log", "--format=%s", f"{base}..HEAD").split("\n") == ["T2: lexer", "T1: parser"]
    assert git(repo, "for-each-ref", "refs/superlite") == ""


def test_hooks_run_in_git_order_with_the_temporary_index(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    log = tmp_path / "log"
    hooks(repo, tmp_path,
          pre_commit=f'echo "pre-commit $GIT_INDEX_FILE $(git ls-files | tr "\\n" " ")" >> "{log}"',
          prepare_commit_msg=f'echo "prepare-commit-msg $2 $(head -n 1 "$1")" >> "{log}"',
          commit_msg=f'echo "commit-msg $(head -n 1 "$1")" >> "{log}"',
          post_commit=f'echo "post-commit" >> "{log}"')
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert [ln.split()[0] for ln in lines] == ["pre-commit", "prepare-commit-msg", "commit-msg",
                                               "pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"]
    assert lines[0].split()[1] == str((repo / ".superlite" / "apply-hook.index").resolve())
    assert "src/a.py" in lines[0] and "src/b.py" not in lines[0]
    assert "src/a.py" in lines[3] and "src/b.py" in lines[3]
    assert lines[1] == "prepare-commit-msg message T1: parser"
    assert lines[2] == "commit-msg T1: parser"
    assert lines[5] == "commit-msg T2: lexer"


def test_commit_msg_hook_edit_is_kept(tmp_path):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    two_tasks(repo)
    hooks(repo, tmp_path, commit_msg='printf "\\nChange-Id: I0123\\n\\n\\n" >> "$1"')
    r = run("autocommit", "apply", "--trailer", "Signed-off-by: A <a@example.com>", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    first = git(repo, "rev-list", "--reverse", f"{base}..HEAD").split("\n")[0]
    assert git(repo, "log", "-1", "--format=%B", first) == (
        "T1: parser\n\nSigned-off-by: A <a@example.com>\n\nChange-Id: I0123")


def test_failing_commit_msg_hook_stops_apply(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, commit_msg='echo "message rejected"; exit 1')
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "message rejected" in r.stderr
    assert "apply: the commit-msg hook failed (exit 1) for T1: parser;" in r.stderr
    assert state(repo) == before


def test_pre_commit_that_changes_the_staged_files_stops_apply(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, pre_commit="git rm -q --cached tests/test_a.py")
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "apply: the pre-commit hook changed the staged files for T1: parser: tests/test_a.py;" in r.stderr
    assert state(repo) == before
    assert (repo / "tests" / "test_a.py").exists()


def test_empty_message_after_commit_msg_stops_apply(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, commit_msg=': > "$1"')
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert ("apply: the commit message for T1: parser is empty after the commit-msg hook; "
            "HEAD and the checkpoints are unchanged") in r.stderr
    assert state(repo) == before


def test_post_commit_failure_is_ignored(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    hooks(repo, tmp_path, post_commit='echo "post-commit failed"; exit 1')
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "applied 2 commit(s)" in r.stdout
    assert "post-commit failed" in r.stderr


def test_default_hooks_folder_without_hooks_path(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    mark = tmp_path / "mark"
    h = repo / ".git" / "hooks" / "pre-commit"
    h.write_text(f'#!/bin/sh\necho "$GIT_INDEX_FILE" > "{mark}"\n', encoding="utf-8")
    h.chmod(0o755)
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    r = run("autocommit", "apply", cwd=repo, env={**ENV, "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert mark.read_text(encoding="utf-8").strip().endswith("apply-hook.index")


def test_old_git_runs_the_hook_file(tmp_path):
    repo = make_repo(tmp_path)
    two_tasks(repo)
    log = tmp_path / "log"
    hooks(repo, tmp_path, pre_commit=f'echo "$GIT_INDEX_FILE $(pwd)" >> "{log}"',
          commit_msg='echo "old git says no"; exit 2')
    before = state(repo)
    r = run("autocommit", "apply", cwd=repo, env=fake_old_git(tmp_path))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "old git says no" in r.stderr
    assert "apply: the commit-msg hook failed (exit 2) for T1: parser;" in r.stderr
    idx, cwd = log.read_text(encoding="utf-8").split()
    assert idx.endswith("apply-hook.index")
    assert Path(cwd).resolve() == repo.resolve()
    assert state(repo) == before


@pytest.mark.skipif(GIT_VERSION < (2, 36), reason="git hook run needs git 2.36")
def test_hook_in_a_linked_worktree_sees_git_dir(tmp_path):
    repo = make_repo(tmp_path)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    two_tasks(wt)
    log = tmp_path / "log"
    hooks(repo, tmp_path, pre_commit=f'echo "$GIT_DIR" >> "{log}"')
    r = run("autocommit", "apply", cwd=wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert log.read_text(encoding="utf-8").splitlines()[0].endswith("/.git/worktrees/wt")
