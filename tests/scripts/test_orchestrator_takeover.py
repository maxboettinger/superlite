"""`orchestrator takeover`: bind this session to a run folder another session owns (#367)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

ORCH = SCRIPTS / "orchestrator.py"
A = "aaaaaaaa-0000-4000-8000-000000000001"
B = "bbbbbbbb-0000-4000-8000-000000000002"
ROOT = SCRIPTS.parents[2]


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / ".git").mkdir(parents=True)
    return r


def sl(cwd, sid, *args, env_extra=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_PROJECT_DIR=str(cwd))
    env.pop("SUPERLITE_SESSION_ID", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if sid:
        env["CLAUDE_CODE_SESSION_ID"] = sid
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(ORCH), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, env=env, timeout=60)


def test_takeover_then_end(repo):
    sd = repo / ".superlite"
    assert sl(repo, A, "set", "ai", "--plan", sd).returncode == 0
    (sd / "stable.json").write_text("{}\n")
    r = sl(repo, B, "end", "--plan", sd)
    assert r.returncode == 2
    assert r.stderr.strip() == (f"orchestrator: {sd} belongs to session {A}; not ended; "
                                f"take the run over first: sl orchestrator takeover --plan {sd}")
    r = sl(repo, B, "takeover", "--plan", sd)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"orchestrator: run {sd} taken over from session {A}; this session owns it now"
    assert (sd / "session").read_text().strip() == B
    r = sl(repo, B, "end", "--plan", sd)
    assert r.returncode == 0, r.stderr
    assert not (sd / "stable.json").exists()
    assert list((sd / "runs").glob("*/stable.json"))


def test_takeover_unowned(repo):
    sd = repo / ".superlite"
    sd.mkdir()
    r = sl(repo, B, "takeover", "--plan", sd)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"orchestrator: session bound to {sd}; no other session owned it"


def test_set_refusal_names_takeover(repo):
    sd = repo / ".superlite"
    assert sl(repo, A, "set", "ai", "--plan", sd).returncode == 0
    r = sl(repo, B, "set", "ai", "--plan", sd)
    assert r.returncode == 2
    assert "belongs to session" in r.stderr
    assert f"sl orchestrator takeover --plan {sd}" in r.stderr


def test_takeover_missing_plan(tmp_path):
    p = tmp_path / "gone" / "plan.md"
    r = sl(tmp_path, B, "takeover", "--plan", p)
    assert r.returncode == 2
    assert r.stderr.strip() == f"orchestrator: plan not found: {p}"


def test_takeover_no_session(repo):
    sd = repo / ".superlite"
    sd.mkdir()
    r = sl(repo, None, "takeover", "--plan", sd)
    assert r.returncode == 2
    sys.path.insert(0, str(SCRIPTS))
    import orchestrator
    assert r.stderr.strip() == orchestrator.NO_SESSION


def test_takeover_foreign_worktree_without_plan(tmp_path):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    w = main / ".claude" / "worktrees" / "wa"
    w.mkdir(parents=True)
    (w / ".git").write_text(f"gitdir: {main}/.git/worktrees/wa\n")
    msd = main / ".superlite"
    msd.mkdir()
    r = sl(w, B, "takeover", env_extra={"SUPERLITE_STATE_DIR": str(msd)})
    assert r.returncode == 2
    assert "not taken over; pass --plan" in r.stderr


def test_tools_doc_names_takeover():
    line = [ln for ln in (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| `orchestrator`")][0]
    assert "takeover" in line


# --- #1047: a live owner is never taken over silently ---

import orchestrator  # noqa: E402

LIVE_TAIL = "a second session never takes over a live run (a batch lead ends here with Status: BLOCKED second lead); "


@pytest.fixture
def child():
    procs = []

    def spawn():
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        procs.append(p)
        return p

    yield spawn
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait()


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _owned(repo, pid):
    sd = repo / ".superlite"
    r = sl(repo, A, "set", "ai", "--plan", sd, env_extra={"CLAUDE_PID": str(pid)} if pid else None)
    assert r.returncode == 0, r.stderr
    return sd


def test_alive_owner_live_dead_and_unknown_1047(repo, child, monkeypatch):
    p = child()
    sd = _owned(repo, p.pid)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", B)
    monkeypatch.delenv("SUPERLITE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    assert orchestrator.alive_owner(sd) == (A, p.pid)
    monkeypatch.setenv("CLAUDE_PID", str(p.pid))
    assert orchestrator.alive_owner(sd) is None
    monkeypatch.delenv("CLAUDE_PID")
    p.kill()
    p.wait()
    assert orchestrator.alive_owner(sd) is None
    # A bound with CLAUDE_PID unset: line 2 empty
    (state._binding(A)).write_text(sd.as_posix() + "\n\n" + repo.as_posix() + "\n", encoding="utf-8")
    assert orchestrator.alive_owner(sd) is None
    # a PermissionError counts as alive, other errors and windows as not
    q = child()
    (state._binding(A)).write_text(sd.as_posix() + f"\n{q.pid}\n" + repo.as_posix() + "\n", encoding="utf-8")
    assert orchestrator.alive_owner(sd) == (A, q.pid)

    def deny(pid, sig):
        raise PermissionError

    monkeypatch.setattr(orchestrator.os, "kill", deny)
    assert orchestrator.alive_owner(sd) == (A, q.pid)

    def odd(pid, sig):
        raise OSError

    monkeypatch.setattr(orchestrator.os, "kill", odd)
    assert orchestrator.alive_owner(sd) is None
    monkeypatch.undo()
    monkeypatch.setenv("SUPERLITE_HOME", str(state.home()))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", B)
    import types
    monkeypatch.setattr(orchestrator, "os", types.SimpleNamespace(name="nt", environ=os.environ, kill=os.kill))
    assert orchestrator.alive_owner(sd) is None


def test_takeover_refuses_a_live_owner_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    r = sl(repo, B, "takeover", "--plan", sd)
    assert r.returncode == 2
    assert r.stdout == ""
    assert r.stderr.strip() == (f"orchestrator: {sd} belongs to session {A}, still running (pid {p.pid}); not taken over: "
                                f"{LIVE_TAIL}once that session has ended rerun this, or take it over anyway: "
                                f"sl orchestrator takeover --force --plan {sd}")
    assert (sd / "session").read_text().strip() == A


def test_takeover_force_takes_a_live_run_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    r = sl(repo, B, "takeover", "--force", "--plan", sd)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == (f"orchestrator: run {sd} taken over from session {A}; this session owns it now; "
                                f"session {A} is still running (pid {p.pid})")
    assert (sd / "session").read_text().strip() == B


def test_takeover_after_the_owner_ended_1047(repo):
    sd = _owned(repo, _dead_pid())
    r = sl(repo, B, "takeover", "--plan", sd)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"orchestrator: run {sd} taken over from session {A}; this session owns it now"


def test_takeover_in_the_same_process_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    r = sl(repo, B, "takeover", "--plan", sd, env_extra={"CLAUDE_PID": str(p.pid)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"orchestrator: run {sd} taken over from session {A}; this session owns it now"


def test_set_refusal_names_a_live_owner_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    r = sl(repo, B, "set", "ai", "--plan", sd)
    assert r.returncode == 2
    assert r.stderr.strip() == (f"orchestrator: {sd} belongs to session {A}, still running (pid {p.pid}); not set: {LIVE_TAIL}"
                                f"pass --plan with your own worktree's plan, or once that session has ended: "
                                f"sl orchestrator takeover --plan {sd}")
    assert "not bound" in sl(repo, B, "bind", "--plan", sd).stderr


def test_end_refusal_names_a_live_owner_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    r = sl(repo, B, "end", "--plan", sd)
    assert r.returncode == 2
    assert r.stderr.strip() == (f"orchestrator: {sd} belongs to session {A}, still running (pid {p.pid}); not ended; "
                                f"end the run in that session, or once it has ended: sl orchestrator takeover --plan {sd}")


def test_pool_prune_names_a_live_owner_1047(repo, child):
    p = child()
    sd = _owned(repo, p.pid)
    (sd / "pool.json").write_text('{"agents": []}\n')
    line = (f"pool: not pruned: {sd} belongs to session {A}, still running (pid {p.pid}); "
            f"prune in that session, or once it has ended: sl orchestrator takeover --plan {sd}")
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=B, CLAUDE_PROJECT_DIR=str(repo), PYTHONIOENCODING="utf-8")
    env.pop("SUPERLITE_SESSION_ID", None)
    env.pop("CLAUDE_PID", None)
    r = subprocess.run([sys.executable, str(SCRIPTS / "pool.py"), "prune", "--pool", str(sd / "pool.json")],
                       capture_output=True, text=True, cwd=repo, env=env, timeout=60)
    assert r.stdout.strip() == line, r.stderr
    r = sl(repo, B, "resume", "--plan", sd)
    assert r.stdout.splitlines()[0] == line


def test_docs_name_takeover_force_1047():
    text = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    paras = text.split("\n\n")
    i = next(k for k, s in enumerate(paras) if s.startswith("Taking a run over:"))
    assert paras[i + 1].startswith("A run whose owner session still runs")
    assert "`takeover --force` takes a live run over anyway." in paras[i + 1]
