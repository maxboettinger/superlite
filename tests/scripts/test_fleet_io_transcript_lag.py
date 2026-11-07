# tests/scripts/test_fleet_io_transcript_lag.py
import json, sys
import pytest
from test_fleet_io import world, transcript, FakeHerdr, rec, user, assistant  # noqa: F401
import fleet_io as io

CHANGES = "Verdict: CHANGES_REQUESTED\n```json\n" + json.dumps({"status": "CHANGES_REQUESTED", "findings": [{"file": "a.py", "line": 3, "problem": "p", "fix": "f", "tier": 1}]}) + "\n```\n"

def stop(world, sent, tr, last):
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": sent + 10, "agent_id": "W1", "type": "x", "transcript": str(tr) if tr else "", "last": last}) + "\n")

def setup(world, reviewer=False):
    if reviewer:
        f = world.sd / "fleet.json"; d = json.loads(f.read_text()); d["workers"]["W1"].update({"role": "final-reviewer", "one_turn": True}); f.write_text(json.dumps(d))
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); return world.clock.t[0]

def test_transcript_appearing_after_first_poll_is_the_report(world, tmp_path, monkeypatch, capsys):
    stops = []; monkeypatch.setattr(io, "_stop_worker", lambda sd, wid: stops.append(wid))
    sent = setup(world, True); tr = tmp_path / "w1.jsonl"; stop(world, sent, tr, "Verdict: CHANGES_REQUESTED")
    world.fh.states = [{"sl-proj-w1": "done"}]
    real = io.sleep; n = []
    def sl(s):
        if not n: transcript(tr, CHANGES)
        n.append(1); real(s)
    monkeypatch.setattr(io, "sleep", sl)
    out = io.wait(world.sd, ["W1"], 60000)
    assert out[0]["status"] == "CHANGES_REQUESTED" and out[0]["findings"] == 1
    assert (world.sd / "fleet" / "reports" / "T3.md").read_text() == CHANGES
    assert "(transcript unread)" not in capsys.readouterr().out and stops == ["W1"]

def test_stale_transcript_without_status_is_reread(world, tmp_path, monkeypatch):
    sent = setup(world); tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("Reading the packet."))
    stop(world, sent, tr, "Verdict: APPROVED"); world.fh.states = [{"sl-proj-w1": "done"}]
    real = io.sleep; n = []
    def sl(s):
        if not n: rec(tr, user("task"), assistant("Reading the packet."), assistant("Verdict: APPROVED\nChecked: x"))
        n.append(1); real(s)
    monkeypatch.setattr(io, "sleep", sl)
    assert io.wait(world.sd, ["W1"], 60000)[0]["status"] == "APPROVED"
    assert (world.sd / "fleet" / "reports" / "T3.md").read_text() == "Verdict: APPROVED\nChecked: x"

def test_transcript_never_flushed_is_unknown_not_the_cut_line(world, tmp_path, monkeypatch, capsys):
    stops = []; monkeypatch.setattr(io, "_stop_worker", lambda sd, wid: stops.append(wid))
    sent = setup(world, True); cut = "Verdict: CHANGES_REQUESTED - 3 findings ..."
    stop(world, sent, tmp_path / "missing.jsonl", cut); world.fh.states = [{"sl-proj-w1": "done"}]
    out = io.wait(world.sd, ["W1"], 60000)
    assert out[0]["status"] == "UNKNOWN" and out[0]["findings"] == 0
    md = (world.sd / "fleet" / "reports" / "T3.md").read_text()
    assert md.startswith("UNKNOWN (transcript empty or behind its stop record after 10 s:")
    assert "Stop record line (cut at 160 chars, not the report):\n" + cut in md
    assert json.loads((world.sd / "fleet" / "reports" / "T3.json").read_text())["status"] == "UNKNOWN"
    assert "Last pane lines:\n" in md and world.fh.screen in md
    assert capsys.readouterr().out.splitlines()[-1].endswith("(transcript unread)") and stops == []

def test_lag_window_is_read_ms(world, tmp_path, capsys):
    sent = setup(world); stop(world, sent, tmp_path / "missing.jsonl", "Status: DONE"); world.fh.states = [{"sl-proj-w1": "done"}]
    t0 = world.clock.t[0]
    assert io.wait(world.sd, ["W1"], 60000)[0]["status"] == "UNKNOWN"
    assert io.READ_MS <= world.clock.t[0] - t0 <= io.READ_MS + 2000
    sent = setup(world); stop(world, sent, tmp_path / "missing.jsonl", "Status: DONE")
    capsys.readouterr()
    assert io.wait(world.sd, ["W1"], io.READ_MS - 2001) == [] and "TIMEOUT W1" in capsys.readouterr().out

def test_stop_without_transcript_uses_last(world):
    sent = setup(world); stop(world, sent, None, "Status: DONE"); world.fh.states = [{"sl-proj-w1": "done"}]
    assert io.wait(world.sd, ["W1"], 60000)[0]["status"] == "DONE"

def test_flushed_transcript_read_once(world, tmp_path, monkeypatch):
    sent = setup(world); tr = tmp_path / "w1.jsonl"; transcript(tr, "Status: DONE\nFiles: a.py"); stop(world, sent, tr, "Status: DONE")
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl")
    calls = []; real = io.report_text; monkeypatch.setattr(io, "report_text", lambda t: (calls.append(t), real(t))[1])
    world.fh.states = [{"sl-proj-w1": "done", "sl-proj-w2": "working"}]
    out = io.wait(world.sd, ["W1", "W2"], 5000)
    assert [r["id"] for r in out] == ["W1"] and len(calls) == 1

def test_lags_rules():
    assert io._lags("", "x", "T3") is True
    assert io._lags("Reading.", "Status: DONE", "T3") is True
    assert io._lags("Reading.", "still busy", "T3") is False
    assert io._lags("Status: DONE", "", "T3") is False
