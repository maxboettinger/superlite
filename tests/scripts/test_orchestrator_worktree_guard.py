"""#199: without --plan, `sl orchestrator end` and `set` never act on another worktree's run. When the cwd is in a linked
worktree and the folder found (the session binding, $SUPERLITE_STATE_DIR) lies outside it, they refuse with one line
naming both folders; a folder inside the worktree and the session's private folder still pass."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from test_session_state import A, B, ORCH, repo, sl, state  # noqa: F401  (repo is a fixture)


def trees(repo):
    return tuple(p.resolve() for p in repo)


def bound_run(main, w, markers=("stable.json", "pool.json")):
    """Session A bound to worktree w's planned run (set ai --plan), with run markers and a ledger; returns its folder."""
    assert sl(main, A, "set", "ai", "--plan", w / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    sd = w / ".superlite"
    for f in markers:
        (sd / f).write_text("{}\n")
    (sd / "progress.md").write_text("ledger\n")
    return sd


def test_end_from_another_worktree_refuses_and_names_both(repo):
    main, wa, wb = trees(repo)
    sb = bound_run(main, wb)
    (wa / ".superlite").mkdir()
    (wa / ".superlite" / "inline-flow.json").write_text('{"flow": "small"}\n')
    r = sl(wa, A, "end")
    assert r.returncode == 2, r.stdout
    assert len(r.stderr.strip().splitlines()) == 1, r.stderr
    assert f"cwd is in worktree {wa}," in r.stderr and f"found is {sb} (session binding)" in r.stderr
    assert "not ended" in r.stderr and f"--plan {wa / '.superlite'} " in r.stderr and r.stderr.strip().endswith(f"--plan {sb}")
    assert sorted(p.name for p in sb.iterdir()) == ["orchestrator.json", "pool.json", "progress.md", "session", "stable.json"]
    assert state.bound(A) == sb and (wa / ".superlite" / "inline-flow.json").exists()


def test_end_with_this_worktrees_folder_leaves_the_bound_run(repo):
    main, wa, wb = trees(repo)
    sb = bound_run(main, wb)
    sa = wa / ".superlite"
    sa.mkdir()
    (sa / "inline-flow.json").write_text('{"flow": "small"}\n')
    (sa / "progress.md").write_text("inline ledger\n")
    r = sl(wa, A, "end", "--plan", sa)
    assert r.returncode == 0 and "run ended; 1 files moved" in r.stdout, r.stderr
    assert not (sa / "inline-flow.json").exists() and not (sa / "progress.md").exists()
    assert (sb / "stable.json").exists() and (sb / "progress.md").exists() and state.bound(A) == sb


@pytest.mark.parametrize("sub", ["", "docs"])
def test_end_inside_the_bound_worktree_still_ends(repo, sub):
    main, _, wb = trees(repo)
    sb = bound_run(main, wb)
    r = sl(wb / sub, A, "end")
    assert r.returncode == 0 and "run ended" in r.stdout, r.stderr
    assert not (sb / "stable.json").exists() and state.bound(A) is None


def test_set_from_another_worktree_refuses_and_keeps_the_gate(repo):
    main, wa, wb = trees(repo)
    assert sl(main, A, "set", "human", "--plan", wb / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    sb = wb / ".superlite"
    r = sl(wa, A, "set", "ai")
    assert r.returncode == 2 and "not set" in r.stderr and f"found is {sb} (session binding)" in r.stderr, r.stderr
    assert json.loads((sb / "orchestrator.json").read_text())["mode"] == "human"
    assert state.bound(A) == sb and not (wa / ".superlite").exists()


def test_state_dir_from_another_worktree_refuses(repo, monkeypatch):
    _, wa, wb = trees(repo)
    sb = wb / ".superlite"
    sb.mkdir()
    (sb / "stable.json").write_text("{}\n")
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(sb))
    r = sl(wa, None, "end")
    assert r.returncode == 2 and f"found is {sb} (SUPERLITE_STATE_DIR)" in r.stderr, r.stderr
    assert (sb / "stable.json").exists()


def test_a_folder_inside_the_worktree_passes(repo):
    main, wa, _ = trees(repo)
    plans = wa / "app" / "docs" / "plans"
    plans.mkdir(parents=True)
    assert sl(main, A, "set", "ai", "--plan", plans / "p.md").returncode == 0
    sd = wa / "app" / ".superlite"
    (sd / "stable.json").write_text("{}\n")
    r = sl(wa, A, "end")
    assert r.returncode == 0 and "run ended" in r.stdout, r.stderr
    assert not (sd / "stable.json").exists()


def test_the_sessions_private_folder_passes(repo):
    _, wa, _ = trees(repo)
    assert sl(wa, B, "set", "human").returncode == 0  # B, launched in wa, owns wa/.superlite
    r = sl(wa, A, "set", "ai")
    assert r.returncode == 0, r.stderr
    assert state.bound(A) == state.private_dir(A)
    assert json.loads((wa / ".superlite" / "orchestrator.json").read_text())["mode"] == "human"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinked_cwd_into_the_bound_worktree_passes(repo, tmp_path):
    main, _, wb = trees(repo)
    sb = bound_run(main, wb, markers=())
    link = tmp_path / "link"
    link.symlink_to(wb, target_is_directory=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A, PWD=str(link))
    r = subprocess.run([sys.executable, str(ORCH), "end"], capture_output=True, text=True, cwd=link, env=env, timeout=60)
    assert r.returncode == 0 and "run ended" in r.stdout, r.stderr
    assert not (sb / "progress.md").exists()


def test_a_submodule_checkout_is_not_a_linked_worktree(repo):
    """A submodule's `.git` file points into `.git/modules`, not `.git/worktrees`: its cwd is never refused."""
    main, _, _ = trees(repo)
    sub = main / "vendor" / "sub"
    sub.mkdir(parents=True)
    (sub / ".git").write_text(f"gitdir: {main}/.git/modules/sub\n")
    (main / ".superlite").mkdir()
    (main / ".superlite" / "stable.json").write_text("{}\n")
    r = sl(sub, A, "end", "--plan", main / ".superlite")
    assert r.returncode == 0, r.stderr
    assert sl(main, A, "set", "ai", "--plan", main / ".superlite").returncode == 0
    r = sl(sub, A, "end")
    assert r.returncode == 0 and "run ended" in r.stdout, r.stderr
