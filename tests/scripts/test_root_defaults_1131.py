"""#1131: project-root defaults (testcmd, trees, autocommit, commit_task) go through state.default_root()."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test_session_state import state  # noqa: F401
from test_state_plugin_folder_1116 import plug  # noqa: F401

import autocommit
import commit_task
import testcmd
import trees


def _git_init(p: Path):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=env)


def _clean(tmp):
    return not any((tmp / "plugin" / "skills").rglob(".superlite"))


def test_testcmd_write_from_plugin_writes_project_config(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    testcmd.main(["--write", "--test", "pytest -q", "--test-file", "pytest {files}", "--language", "python"])
    assert (proj / ".superlite" / "test-cmd.json").exists()
    assert _clean(tmp)


def test_testcmd_write_outside_plugin_unchanged(tmp_path, monkeypatch):
    w = tmp_path / "w"
    w.mkdir()
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    testcmd.main(["--write", "--test", "pytest -q", "--test-file", "pytest {files}", "--language", "python"])
    assert (w / ".superlite" / "test-cmd.json").exists()


def test_trees_clean_from_plugin_works_in_project(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert trees.main(["clean"]) == 0
    assert _clean(tmp)


def test_autocommit_on_from_plugin_writes_project_config(plug, monkeypatch):
    tmp, _, _, proj = plug
    (proj / ".git").rmdir()
    _git_init(proj)
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    autocommit.main(["on"])
    assert (proj / ".superlite" / "autocommit.json").exists()
    assert _clean(tmp)


def test_commit_task_from_plugin_works_in_project(plug, monkeypatch):
    tmp, _, _, proj = plug
    (proj / ".git").rmdir()
    _git_init(proj)
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    try:
        commit_task.main(["T9"])
    except SystemExit:
        pass
    assert Path.cwd().resolve() == proj.resolve()
    assert _clean(tmp)


def test_commit_task_outside_plugin_keeps_cwd(tmp_path, monkeypatch):
    w = tmp_path / "w"
    w.mkdir()
    _git_init(w)
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    try:
        commit_task.main(["T9"])
    except SystemExit:
        pass
    assert Path.cwd().resolve() == w.resolve()
