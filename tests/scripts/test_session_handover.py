"""Plan-then-build hand-over: a session launched in the folder's own project takes over a binding whose owner was
launched elsewhere; an owner launched in the same directory still wins."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

ORCH = SCRIPTS / "orchestrator.py"
A, B = "aaaa-1111", "bbbb-2222"


@pytest.fixture
def repo(tmp_path):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    w = main / ".claude" / "worktrees" / "wa"
    (w / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (w / ".git").write_text(f"gitdir: {main}/.git/worktrees/wa\n")
    return main, w


def sl(launch, sid, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=sid, CLAUDE_PROJECT_DIR=str(launch))
    env.pop("SUPERLITE_SESSION_ID", None)
    env.pop("SUPERLITE_STATE_DIR", None)
    return subprocess.run([sys.executable, str(ORCH), *map(str, args)], capture_output=True, text=True,
                          cwd=launch, env=env, timeout=60)


def plan(w):
    return w / "docs" / "superpowers" / "plans" / "p.md"


def test_build_session_in_worktree_takes_over_plan_sessions_binding(repo):
    main, wa = repo
    assert sl(main, A, "set", "ai", "--plan", plan(wa)).returncode == 0
    assert state.owner(wa / ".superlite") == A
    r = sl(wa, B, "set", "ai")
    assert r.returncode == 0, r.stderr
    assert state.owner(wa / ".superlite") == B
    assert state.bound(A) is None
    assert state.bound(B) == wa / ".superlite"


def test_two_sessions_from_one_launch_dir_still_never_share(repo):
    main, wa = repo
    assert sl(main, A, "set", "human").returncode == 0
    r = sl(main, B, "set", "human")
    assert state.owner(main / ".superlite") == A
    assert state.bound(B) is None or state.bound(B) != main / ".superlite"
    assert r.returncode in (0, 2)
    r = sl(main, B, "bind")
    assert r.returncode == 2 and "belongs to session" in r.stderr


def test_old_binding_without_launch_dir_needs_force(repo, tmp_path):
    main, wa = repo
    assert sl(main, A, "set", "ai", "--plan", plan(wa)).returncode == 0
    b = state._binding(A)
    b.write_text(b.read_text().splitlines()[0] + "\n")  # an old two-line (path only) binding
    assert state.owner_launch_dir(A) is None
    r = sl(wa, B, "bind")
    assert r.returncode == 2 and "belongs to session" in r.stderr
    assert sl(wa, B, "bind", "--force").returncode == 0
    assert state.owner(wa / ".superlite") == B


def test_bind_without_plan_targets_launch_dir(repo):
    main, wa = repo
    r = sl(wa, B, "bind")
    assert r.returncode == 0, r.stderr
    assert str(wa / ".superlite") in r.stdout and "sessions" not in r.stdout
    assert state.owner_launch_dir(B) == wa


def test_force_still_takes_over_from_elsewhere(repo):
    main, wa = repo
    assert sl(wa, A, "set", "ai").returncode == 0
    r = sl(main, B, "bind")
    assert r.returncode == 0 and str(main / ".superlite") in r.stdout
    r = sl(main, B, "bind", "--force")
    assert r.returncode == 0 and state.owner(main / ".superlite") == B


def test_launch_dir_env_then_pwd(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert state.launch_dir() == tmp_path
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    monkeypatch.setenv("PWD", str(tmp_path / "w" / "sub"))
    assert state.launch_dir() == tmp_path / "w" / "sub"
