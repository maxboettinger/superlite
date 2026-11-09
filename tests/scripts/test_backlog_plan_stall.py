# tests/scripts/test_backlog_plan_stall.py
import sys
import herdr_client
from test_backlog_cli import bk, cli, load  # noqa: F401

def test_plan_stops_a_triage_worker_whose_brief_stalls(bk, capsys, monkeypatch):
    def send(sd, wid, brief, label=""):
        raise herdr_client.HerdrError("agent_prompt_stalled", "no working state")
    monkeypatch.setattr(sys.modules["fleet_io"], "send_brief", send, raising=False)
    monkeypatch.setattr(sys.modules["fleet"], "stop", lambda sd, ids=None, all_=False: bk.calls.append(("stop", ids)), raising=False)
    assert cli(capsys, "plan") == (3, "BLOCKED: triage worker W1 got no brief (agent_prompt_stalled: no working state); worker stopped\n")
    assert ("stop", ["W1"]) in bk.calls
    assert load(bk)["batches"] == []
