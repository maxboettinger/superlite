# tests/scripts/test_backlog_start_stall.py
import sys
from pathlib import Path
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run, Herdr  # noqa: F401

STALL = "agent_prompt_stalled: no working state"

def fail_for(bk, monkeypatch, *wids):
    def send(sd, wid, brief, label=""):
        if wid in wids:
            raise Herdr(STALL)
        bk.calls.append(("send", wid, Path(brief).name, label))
        return label
    monkeypatch.setattr(sys.modules["fleet_io"], "send_brief", send, raising=False)

def test_start_stops_a_lead_whose_brief_stalls_and_starts_the_rest(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]), b("B3", ["c.py"]))
    fail_for(bk, monkeypatch, "W1")
    w3 = bk.root / ".claude" / "worktrees" / "superlite-b3-t"
    assert run(capsys, "start") == (2, f"BLOCKED: B1 lead W1 got no brief ({STALL}); lead stopped, rerun sl backlog start B1\nB3 running lead=W2 worktree={w3}\n")
    assert ("stop", ["W1"]) in bk.calls
    x = get(bk, "B1")
    assert x["state"] == "planned" and x.get("lead") != "W1" and x.get("agent") != "sl-m-W1"
    y = get(bk, "B3")
    assert y["state"] == "running" and y["lead"] == "W2"

def test_start_keeps_a_parked_batch_parked_when_its_brief_fails(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"], "parked", reason="tui red", worktree=str(bk.root / ".claude" / "worktrees" / "superlite-b1-t")))
    fail_for(bk, monkeypatch, "W1")
    assert run(capsys, "start", "B1")[0] == 2
    x = get(bk, "B1")
    assert x["state"] == "parked" and x["reason"] == "tui red"
    assert ("stop", ["W1"]) in bk.calls
