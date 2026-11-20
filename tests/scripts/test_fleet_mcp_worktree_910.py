"""fleet_mcp.worktree_previews: the main checkout when a linked worktree's workers get the xcode server (#910)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_mcp  # noqa: E402

XCODE_CFG = {"test": "pytest", "mcp": ["xcode"]}


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "no-user-cfg.json"))


def git(*args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    git("init", "-q", str(main))
    git("-C", str(main), "config", "user.name", "t")
    git("-C", str(main), "config", "user.email", "t@example.com")
    (main / "a.txt").write_text("a")
    git("-C", str(main), "add", "a.txt")
    git("-C", str(main), "commit", "-q", "-m", "a")
    git("-C", str(main), "worktree", "add", "-q", "../wt", "-b", "b276")
    return main, tmp_path / "wt"


def cfg(p, d):
    (p / ".superlite").mkdir(parents=True, exist_ok=True)
    (p / ".superlite" / "test-cmd.json").write_text(json.dumps(d))


def test_linked_worktree_with_xcode_gives_main(repos):
    main, wt = repos
    cfg(wt, XCODE_CFG)
    assert fleet_mcp.worktree_previews(wt) == main.resolve()
    assert fleet_mcp.worktree_previews(str(wt)) == main.resolve()


def test_main_checkout_gives_none(repos):
    main, _ = repos
    cfg(main, XCODE_CFG)
    assert fleet_mcp.worktree_previews(main) is None


def test_no_xcode_gives_none(repos):
    _, wt = repos
    cfg(wt, {"test": "pytest", "mcp": []})
    assert fleet_mcp.worktree_previews(wt) is None


def test_no_git_gives_none(tmp_path):
    p = tmp_path / "plain"
    cfg(p, XCODE_CFG)
    assert fleet_mcp.worktree_previews(p) is None


def test_bad_mcp_is_quiet(repos, monkeypatch, capsys):
    _, wt = repos
    cfg(wt, {"test": "pytest", "mcp": "xcode"})
    monkeypatch.setattr(fleet_mcp.sys, "platform", "linux")
    assert fleet_mcp.worktree_previews(wt) is None
    assert capsys.readouterr().err == ""


def test_git_failure_gives_none(repos, monkeypatch):
    _, wt = repos
    cfg(wt, XCODE_CFG)
    monkeypatch.setattr(fleet_mcp, "_main_key", lambda p: (_ for _ in ()).throw(OSError("x")))
    assert fleet_mcp.worktree_previews(wt) is None


def test_note_names_worktree_rule():
    note = fleet_mcp.XCODE_NOTE
    assert "unless your checkout is a linked git worktree" in note
    assert "RenderPreview" in note
    assert not any(c in note for c in "`'\"$!#\n")
