"""#1068: project_python finds the main checkout's .venv from a linked worktree or task tree; project_cmd falls back to uv run."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import _pyrun  # noqa: E402


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def touch(base, rel):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    return p


def linked(main, wt, name, gitdir_text=None):
    """wt laid out as git writes a linked worktree of main (no git run): wt/.git names main/.git/worktrees/<name>."""
    gitdir = main / ".git" / "worktrees" / name
    gitdir.mkdir(parents=True, exist_ok=True)
    (gitdir / "commondir").write_text("../..\n")
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {gitdir_text or gitdir}\n")
    return wt


def same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_lead_worktree_uses_main_checkout_venv(tmp_path):
    main = tmp_path / "main"
    py = touch(main, ".venv/bin/python")
    wt = linked(main, main / ".claude" / "worktrees" / "b1", "b1")
    assert same(_pyrun.main_checkout(wt), main)
    assert same(_pyrun.project_python(wt), py)


def test_task_tree_inside_a_lead_worktree_uses_main_checkout_venv(tmp_path):
    main = tmp_path / "main"
    py = touch(main, ".venv/bin/python")
    wt = linked(main, tmp_path / "wt", "wt")
    tree = linked(main, wt / ".superlite" / "trees" / "T1", "T1")
    assert same(_pyrun.project_python(tree), py)


def test_relative_gitdir_is_read_from_the_folder_holding_dot_git(tmp_path):
    main = tmp_path / "main"
    py = touch(main, ".venv/bin/python")
    wt = linked(main, tmp_path / "wt", "wt", gitdir_text="../main/.git/worktrees/wt")
    assert same(_pyrun.project_python(wt), py)


def test_own_venv_wins_over_main_checkout_venv(tmp_path):
    main = tmp_path / "main"
    touch(main, ".venv/bin/python")
    wt = linked(main, tmp_path / "wt", "wt")
    own = touch(wt, ".venv/bin/python")
    assert _pyrun.project_python(wt) == str(own)


def test_main_checkout_venv_wins_over_virtual_env(tmp_path, monkeypatch):
    main = tmp_path / "main"
    py = touch(main, ".venv/bin/python")
    other = tmp_path / "other"
    touch(other, "bin/python")
    monkeypatch.setenv("VIRTUAL_ENV", str(other))
    wt = linked(main, tmp_path / "wt", "wt")
    assert same(_pyrun.project_python(wt), py)


def test_main_checkout_without_venv_falls_through_to_virtual_env(tmp_path, monkeypatch):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    venv = tmp_path / "venv"
    vpy = touch(venv, "bin/python")
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    wt = linked(main, tmp_path / "wt", "wt")
    assert _pyrun.project_python(wt) == str(vpy)


def test_main_checkout_itself_and_a_subfolder(tmp_path):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    sub = main / "pkg"
    sub.mkdir()
    assert same(_pyrun.main_checkout(main), main)
    assert same(_pyrun.main_checkout(sub), main)
    assert _pyrun.project_python(main) == sys.executable
    py = touch(main, ".venv/bin/python")
    assert same(_pyrun.project_python(sub), py)


@pytest.mark.parametrize("dot_git", ["gitdir: {missing}\n", "not a gitdir line\n", "gitdir: {nocommon}\n"])
def test_unreadable_worktree_link_gives_no_main_checkout(tmp_path, dot_git):
    nocommon = tmp_path / "modules" / "sub"  # a submodule's gitdir: no commondir file
    nocommon.mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(dot_git.format(missing=tmp_path / "gone", nocommon=nocommon))
    assert _pyrun.main_checkout(wt) is None
    assert _pyrun.project_python(wt) == sys.executable


def test_bare_common_dir_gives_no_main_checkout(tmp_path):
    bare = tmp_path / "repo.git"
    gitdir = bare / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    touch(tmp_path, ".venv/bin/python")  # beside the bare repo: never used
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    assert _pyrun.main_checkout(wt) is None
    assert _pyrun.project_python(wt) == sys.executable


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_real_git_worktree(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def git(*args):
        subprocess.run(["git", *args], cwd=main, check=True, capture_output=True, env=env)
    git("init", "-q")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "base")
    git("worktree", "add", "-q", "--detach", str(tmp_path / "wt"))
    py = touch(main, ".venv/bin/python")
    assert same(_pyrun.main_checkout(tmp_path / "wt"), main)
    assert same(_pyrun.project_python(tmp_path / "wt"), py)


def test_project_cmd_is_the_found_interpreter(tmp_path, monkeypatch):
    py = touch(tmp_path, ".venv/bin/python")
    touch(tmp_path, "uv.lock")
    touch(tmp_path, "pyproject.toml")
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: "/opt/bin/uv")
    assert _pyrun.project_cmd(tmp_path) == [str(py)]


def test_project_cmd_uv_run_for_a_uv_project_without_venv(tmp_path, monkeypatch):
    touch(tmp_path, "uv.lock")
    touch(tmp_path, "pyproject.toml")
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: "/opt/bin/uv" if name == "uv" else None)
    assert _pyrun.project_cmd(tmp_path) == ["/opt/bin/uv", "run", "--frozen", "--project", str(tmp_path), "python"]


@pytest.mark.parametrize("files,uv", [(["uv.lock", "pyproject.toml"], None),
                                      (["pyproject.toml"], "/opt/bin/uv"),
                                      (["uv.lock"], "/opt/bin/uv")])
def test_project_cmd_without_uv_or_lock_is_our_interpreter(tmp_path, monkeypatch, files, uv):
    for f in files:
        touch(tmp_path, f)
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: uv)
    assert _pyrun.project_cmd(tmp_path) == [sys.executable]


def test_project_cmd_reads_project_python_through_the_module(tmp_path, monkeypatch):
    """The seam test_project_python_callers.py patches: project_cmd calls the module's project_python."""
    monkeypatch.setattr(_pyrun, "project_python", lambda root: "/x/venv/bin/python")
    assert _pyrun.project_cmd(tmp_path) == ["/x/venv/bin/python"]


def test_project_cmd_keeps_a_found_interpreter_that_is_our_own(tmp_path, monkeypatch):
    """Review: a session run inside the project's venv finds sys.executable itself; that is found, not the fallback, so no uv run."""
    py = touch(tmp_path, ".venv/bin/python")
    touch(tmp_path, "uv.lock")
    touch(tmp_path, "pyproject.toml")
    monkeypatch.setattr(_pyrun.sys, "executable", str(py))
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: "/opt/bin/uv")
    assert _pyrun.project_cmd(tmp_path) == [str(py)]


def test_undecodable_worktree_link_gives_no_main_checkout(tmp_path):
    """Review: a .git file that is not utf-8 is an unreadable link, not a traceback."""
    (tmp_path / ".git").write_bytes(b"\xff\xfe\x00gitdir: x")
    assert _pyrun.main_checkout(tmp_path) is None
