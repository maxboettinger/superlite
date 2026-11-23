import sys
from pathlib import Path
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run  # noqa: F401

import orchestrator  # noqa: E402

SID = "aaaaaaaa-0000-4000-8000-000000000001"

def wt_of(bk, n):
    return bk.root / ".claude" / "worktrees" / f"superlite-b{n}-t"

def fake_alive(monkeypatch, alive):
    monkeypatch.setattr(orchestrator, "alive_owner", lambda sd: alive.get(Path(sd).parent.name), raising=False)

def test_start_refuses_a_batch_whose_lead_still_runs_1047(bk, capsys, monkeypatch):
    wt = wt_of(bk, 1)
    put(bk, b("B1", ["a.py"], "parked", reason="x", worktree=str(wt)))
    fake_alive(monkeypatch, {wt.name: (SID, 4242)})
    rc, out = run(capsys, "start", "B1")
    assert rc == 2
    assert out.splitlines()[-1] + "\n" == (f"BLOCKED: B1 not started: lead session {SID} is still running (pid 4242) in {wt}; no second lead: sl backlog wait; "
                   f"to restart it, stop that session first, then sl backlog start B1 (if pid 4242 is not that session, delete {wt}/.superlite/session first)\n")
    assert not [c for c in bk.calls if c[0] == "spawn"] and not (wt / ".superlite" / "briefs" / "lead.md").exists()
    assert get(bk, "B1")["state"] == "parked"

def test_start_spawns_when_the_old_lead_is_gone_1047(bk, capsys, monkeypatch):
    wt = wt_of(bk, 1)
    put(bk, b("B1", ["a.py"], "parked", reason="x", worktree=str(wt)))
    fake_alive(monkeypatch, {})
    assert run(capsys, "start", "B1")[0] == 0
    assert len([c for c in bk.calls if c[0] == "spawn"]) == 1 and get(bk, "B1")["state"] == "running"

def test_start_refusal_leaves_other_batches_starting_1047(bk, capsys, monkeypatch):
    wt = wt_of(bk, 1)
    put(bk, b("B1", ["a.py"], "parked", reason="x", worktree=str(wt)), b("B2", ["b.py"]))
    fake_alive(monkeypatch, {wt.name: (SID, 4242)})
    rc, out = run(capsys, "start", "B1", "B2")
    assert rc == 2 and "BLOCKED: B1 not started: lead session" in out
    assert get(bk, "B1")["state"] == "parked" and get(bk, "B2")["state"] == "running"
