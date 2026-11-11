"""#502: sl worktree ensure --dir NAME names the worktree folder, case kept."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import worktree  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    (r / "a.txt").write_text("one\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "init")
    return r


def test_dir_keeps_case(repo):
    path, state = worktree.ensure("KEY-1632 some topic", repo, folder="KEY-1632-topic")
    assert state == "created"
    assert path.name == "KEY-1632-topic" and path.parent.name == "worktrees" and path.parent.parent.name == ".claude"
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD").strip() == "superlite/key-1632-some-topic"


def test_dir_with_branch(repo):
    path, _ = worktree.ensure("x", repo, branch="feat/KEY-1-slug", folder="KEY-1-slug")
    assert path.name == "KEY-1-slug"
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/KEY-1-slug"


def test_dir_reused(repo):
    first, _ = worktree.ensure("x", repo, folder="Run-A")
    again, state = worktree.ensure("x", repo, folder="Run-A")
    assert again == first and state == "exists"


@pytest.mark.parametrize("bad", ["../x", "a/b", ".hidden", "", "x" * 81])
def test_dir_rejects_bad_names(repo, bad, capsys):
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--dir", bad]) == 2
    assert f"worktree: invalid folder name: {bad}" in capsys.readouterr().err
    assert not (repo / ".claude" / "worktrees").exists() or not any((repo / ".claude" / "worktrees").iterdir())


def test_dir_cli_prints_path(repo, capsys):
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--dir", "My-Run"]) == 0
    assert capsys.readouterr().out.strip().endswith("/.claude/worktrees/My-Run")
