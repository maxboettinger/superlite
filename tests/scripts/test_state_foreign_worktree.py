"""#224 a writer never follows a session binding into another worktree; #225 a submodule `.git` file is no worktree."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_session_state import A, ORCH, repo, sl, state  # noqa: F401  (repo is a fixture)

SCRIPTS = ORCH.parent


def trees(repo):
    return tuple(p.resolve() for p in repo)


def bind_to(sd, sid=A):
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "stable.json").write_text("{}\n")
    assert state.bind(sd, sid) == sid
    return sd


@pytest.fixture
def at(monkeypatch):
    def go(cwd, sid=A):
        monkeypatch.chdir(cwd)
        monkeypatch.setenv("PWD", str(cwd))
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", sid)
        monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    return go


@pytest.mark.parametrize("text,want", [
    ("gitdir: /r/.git/worktrees/wa", True),
    ("gitdir: /r/.git/worktrees/wa/", True),
    (r"gitdir: C:\r\.git\worktrees\wa", True),
    ("gitdir: /r/.git/modules/sub", False),
    ("gitdir: /r/sub.git", False),
    ("garbage", False),
])
def test_linked_worktree_reads_the_gitdir(tmp_path, text, want):
    (tmp_path / ".git").write_text(text + "\n")
    assert state.linked_worktree(tmp_path) is want


def test_linked_worktree_folder_and_missing(tmp_path):
    assert state.linked_worktree(tmp_path) is False
    (tmp_path / ".git").mkdir()
    assert state.linked_worktree(tmp_path) is False


def test_worktree_run_skips_a_submodule(repo, at):
    main, _, wb = trees(repo)
    sub = main / "sub"
    (sub / ".superlite").mkdir(parents=True)
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    (sub / ".superlite" / "stable.json").write_text("{}\n")
    bind_to(main / ".superlite")
    at(sub)
    assert state.worktree_run() is None
    assert state.worktree_top(".") is None
    assert state.resolve() == main / ".superlite"


def test_resolve_refuses_a_binding_in_another_worktree(repo, at, capsys):
    main, wa, wb = trees(repo)
    bind_to(wb / ".superlite")
    at(wa)
    with pytest.raises(state.Foreign) as ei:
        state.resolve()
    assert ei.value.code == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1
    assert f"cwd is in worktree {wa}" in err and f"{wb}/.superlite" in err


def test_resolve_keeps_a_binding_inside_the_worktree(repo, at):
    _, wa, _ = trees(repo)
    bind_to(wa / ".superlite")
    (wa / "docs").mkdir(exist_ok=True)
    at(wa / "docs")
    assert state.resolve() == wa / ".superlite"


def test_state_dir_names_the_foreign_run(repo, at, monkeypatch):
    _, wa, wb = trees(repo)
    bind_to(wb / ".superlite")
    at(wa)
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(wb / ".superlite"))
    assert state.resolve() == wb / ".superlite"


def test_non_strict_and_main_checkout_follow_the_binding(repo, at):
    main, wa, wb = trees(repo)
    bind_to(wb / ".superlite")
    at(wa)
    assert state.resolve(strict=False) == wb / ".superlite"
    at(main)
    assert state.resolve() == wb / ".superlite"


def test_private_folder_passes(repo, at):
    _, wa, _ = trees(repo)
    p = state.private_dir(A)
    bind_to(p)
    at(wa)
    assert state.resolve() == p


def test_for_plan_uses_the_plan_folder_when_the_binding_is_foreign(repo, at):
    _, wa, wb = trees(repo)
    bind_to(wb / ".superlite")
    at(wa)
    plan = wa / "docs" / "superpowers" / "plans" / "p.md"
    assert state.for_plan(plan) == wa / ".superlite"


def run_py(script, cwd, *args, **env):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **env)
    e.pop("SUPERLITE_STATE_DIR", None) if "SUPERLITE_STATE_DIR" not in env else None
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, env=e, timeout=60)


def test_writer_cli_refuses_with_exit_2(repo):
    main, wa, wb = trees(repo)
    bind_to(wb / ".superlite", A)
    log = wb / ".superlite" / "incidents.jsonl"
    args = ("add", "--file", "a.py", "--line", "1", "--context", "x")
    r = run_py("incident.py", wa, *args, CLAUDE_CODE_SESSION_ID=A)
    assert r.returncode == 2, r.stdout + r.stderr
    assert len(r.stderr.strip().splitlines()) == 1 and str(wa) in r.stderr and f"{wb}/.superlite" in r.stderr
    assert not log.exists()
    r = run_py("incident.py", wa, *args, CLAUDE_CODE_SESSION_ID=A, SUPERLITE_STATE_DIR=str(wb / ".superlite"))
    assert r.returncode == 0, r.stderr
    assert log.exists()


def test_where_reports_a_foreign_binding(repo):
    main, wa, wb = trees(repo)
    bind_to(wb / ".superlite", A)
    r = run_py("state.py", wa, "where", CLAUDE_CODE_SESSION_ID=A)
    assert r.returncode == 0, r.stderr
    assert "session binding" in r.stdout and "foreign" in r.stdout


def test_orchestrator_uses_the_state_check(repo):
    import orchestrator
    assert orchestrator.foreign_worktree is state.foreign_worktree
    main, wa, wb = trees(repo)
    bind_to(wb / ".superlite", A)
    r = sl(wa, A, "bind")
    assert r.returncode == 0, r.stderr
    assert state.bound(A) == wa / ".superlite"
