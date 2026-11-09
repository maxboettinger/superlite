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
