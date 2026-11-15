"""trees.stage: the task tree's git index holds the overlay (#799)."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import trees  # noqa: E402


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env).stdout


@pytest.fixture(autouse=True)
def clean_git_env(monkeypatch):
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".git" / "info").mkdir(exist_ok=True)
    (tmp_path / ".git" / "info" / "exclude").write_text(".superlite/\n")
    (tmp_path / "a.py").write_text("1\n")
    (tmp_path / "b.py").write_text("B\n")
    (tmp_path / ".gitattributes").write_text("*.bin filter=fake\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "config", "filter.fake.clean", "sed s/^/CLEAN:/")
    git(tmp_path, "config", "filter.fake.smudge", "cat")
    return tmp_path


def test_new_overlay_file_is_in_tree_index(repo):
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert git(tree, "ls-files", "img.bin").strip() == "img.bin"


def test_overlay_runs_the_clean_filter(repo):
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert git(tree, "cat-file", "-p", ":img.bin") == "CLEAN:x\n"
    assert (tree / "img.bin").read_bytes() == b"x\n"


def test_modified_tracked_file_is_staged(repo):
    (repo / "a.py").write_text("2\n")
    tree = trees.prepare(repo, "T1", ["a.py"])
    assert git(tree, "diff", "--cached", "--name-only") == "a.py\n"
    assert git(tree, "diff", "--name-only") == ""


def test_deleted_file_leaves_tree_index(repo):
    (repo / "b.py").unlink()
    tree = trees.prepare(repo, "T1", ["b.py"])
    assert git(tree, "ls-files", "b.py") == ""


def test_reuse_drops_last_overlay(repo):
    (repo / "c.py").write_text("c\n")
    tree = trees.prepare(repo, "T1", ["c.py"])
    assert git(tree, "ls-files", "c.py").strip() == "c.py"
    (repo / "c.py").unlink()
    tree = trees.prepare(repo, "T1", ["c.py"])
    assert git(tree, "ls-files", "c.py") == ""
    assert not (tree / "c.py").exists()


def test_literal_names_stage(repo):
    (repo / "my file.py").write_text("1\n")
    (repo / ":odd.py").write_text("1\n")
    tree = trees.prepare(repo, "T1", ["my file.py", ":odd.py"])
    listed = git(tree, "ls-files").splitlines()
    assert "my file.py" in listed and ":odd.py" in listed


def test_failed_stage_keeps_the_tree(repo, capsys):
    git(repo, "config", "filter.fake.clean", "false")
    git(repo, "config", "filter.fake.required", "true")
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert (tree / "img.bin").read_bytes() == b"x\n"
    assert "trees: T1 tree index not updated: " in capsys.readouterr().err


def test_stage_with_nothing_calls_no_git(tmp_path):
    assert trees.stage(tmp_path / "plain", [], []) == ""


def test_hanging_clean_filter_times_out(repo, capsys, monkeypatch):
    monkeypatch.setattr(trees, "STAGE_TIMEOUT", 1)
    git(repo, "config", "filter.fake.clean", "sleep 30")
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert (tree / "img.bin").read_bytes() == b"x\n"
    assert "git add timed out after 1 s" in capsys.readouterr().err


def test_timeout_removes_index_lock_and_next_prepare_stages(repo, capsys, monkeypatch):
    monkeypatch.setattr(trees, "STAGE_TIMEOUT", 1)
    git(repo, "config", "filter.fake.clean", "sleep 30")
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    err = capsys.readouterr().err
    assert "git add timed out after 1 s; removed " in err
    lock = git(tree, "rev-parse", "--path-format=absolute", "--git-path", "index.lock").strip()
    assert not os.path.exists(lock)
    git(repo, "config", "filter.fake.clean", "sed s/^/CLEAN:/")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert git(tree, "ls-files", "img.bin").strip() == "img.bin"
    assert "not updated" not in capsys.readouterr().err


def test_timeout_without_killpg_falls_back_to_kill(repo, capsys, monkeypatch):
    monkeypatch.setattr(trees, "STAGE_TIMEOUT", 1)
    monkeypatch.delattr(os, "killpg")
    git(repo, "config", "filter.fake.clean", "sleep 5")
    (repo / "img.bin").write_text("x\n")
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert (tree / "img.bin").read_bytes() == b"x\n"
    assert "git add timed out after 1 s" in capsys.readouterr().err


def test_never_ending_filter_without_killpg_does_not_hang_the_reap(repo, capsys, monkeypatch):
    import time

    monkeypatch.setattr(trees, "STAGE_TIMEOUT", 1)
    monkeypatch.delattr(os, "killpg")
    git(repo, "config", "filter.fake.clean", "sleep 40")
    (repo / "img.bin").write_text("x\n")
    t0 = time.monotonic()
    tree = trees.prepare(repo, "T1", ["img.bin"])
    assert time.monotonic() - t0 < 1 + 15
    assert (tree / "img.bin").read_bytes() == b"x\n"
    assert "git add timed out after 1 s" in capsys.readouterr().err
