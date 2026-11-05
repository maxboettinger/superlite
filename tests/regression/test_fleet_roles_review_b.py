# tests/regression/test_fleet_roles_review_b.py -- package review B of fleet roles T1-T5 (seams against the real producers)
import json, sys, os
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_fleet import REAL, fleet, world  # noqa: F401,E402  (world is a fixture)
import fleet_layer as fl  # noqa: E402
import fleet_io as fio  # noqa: E402
import fleet_report as fr  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="drives the in-process fake herdr")


class Shell:
    def __init__(self): self.calls = []
    def run_in_pane(self, pane, command): self.calls.append((pane, command)); return ""


def _layer_world(world, monkeypatch):
    (world.proj / "scripts").mkdir(); (world.proj / "scripts" / "test_layers.py").write_text("# l\n")
    sh = Shell(); monkeypatch.setattr(fl, "hc", sh)
    monkeypatch.setattr(fio.hc, "agent_states", lambda: {})
    return sh


def test_layer_runs_against_real_choose_account_and_open_pane(world, monkeypatch):
    """Seam T4 <- T3: the real (account, config_dir, shared) tuple and the real open_pane record/pane id."""
    fleet.main(["on"]); sh = _layer_world(world, monkeypatch)
    r = fl.run(world.sd, "headless", world.proj, env={"HOME": "/u"})
    assert r["id"] == "W1" and r["account"] == "claude3" and r["pane_id"] == "w6:p1"
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert (w["role"], w["state"], w["pane_id"], w["account"]) == ("layer", "busy", "w6:p1", "claude3")
    assert sh.calls[0][0] == "w6:p1"
    env = next(c for c in world.fh.calls if c[0] == "create_workspace")[2]
    assert env["CLAUDE_CONFIG_DIR"] == "/u/.claude-account3" and "SUPERLITE_FLEET_WORKER" not in env


def test_wait_finishes_layer_and_stop_writes_state_before_closing_workspace(world, monkeypatch, capsys):
    """Seam T5 <- T4 and #192: the last worker stopped by wait clears workspace_id in fleet.json before close_workspace."""
    fleet.main(["on"]); _layer_world(world, monkeypatch)
    fl.run(world.sd, "headless", world.proj, env={"HOME": "/u"})
    d = world.sd / "fleet" / "layers"
    (d / "W1-headless.log").write_text("headless: green\n"); (d / "W1-headless.exit").write_text("0\n")
    seen = {}
    orig = world.fh.close_workspace
    def close(ws):
        seen["ws"] = json.loads((world.sd / "fleet.json").read_text()).get("workspace_id"); orig(ws)
    world.fh.close_workspace = close
    capsys.readouterr()
    res = fio.wait(world.sd, None, 1000, poll_s=0)
    out = capsys.readouterr().out
    assert res[0]["status"] == "GREEN" and "W1 layer-headless GREEN exit=0" in out
    assert ("close_workspace", "w6") in world.fh.calls and seen["ws"] is None
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "stopped"


def test_reviewer_wait_line_and_stop_with_real_spawn(world, monkeypatch, capsys):
    """Seam T5 <- T2/T3: a spawned final-reviewer is one_turn; a json reply gives `Wn label STATUS findings=n json` and stops it."""
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, None, world.proj, role="final-reviewer")
    text = ('Checked: x\n```json\n{"status": "CHANGES_REQUESTED", "files": [], "tests": "", "findings": [{"file": "a.py", "line": 3, '
            '"problem": "p", "fix": "f", "tier": 2}], "summary": "s"}\n```\n')
    tr = world.sd / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}) + "\n")
    monkeypatch.setattr(fio.hc, "agent_states", lambda: {fleet.fs.agent_name(world.sd, "W1"): "idle"})
    fio._busy(world.sd, "W1", "final", 1)
    (world.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "agent_id": "W1", "t": 5, "transcript": str(tr)}) + "\n")
    capsys.readouterr(); fio.wait(world.sd, None, 1000, poll_s=0)
    out = capsys.readouterr().out.strip()
    assert out == f"W1 final CHANGES_REQUESTED findings=1 {world.sd / 'fleet' / 'reports' / 'final.json'}"
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "stopped"


def test_json_fence_inside_a_summary_string_does_not_cut_the_block():
    """A summary quoting a fence must not make a valid report fall back to UNKNOWN."""
    body = json.dumps({"status": "DONE", "files": [], "tests": "", "findings": [], "summary": "ran ```x``` ok"})
    r = fr.parse("Status: DONE\n```json\n" + body + "\n```\n")
    assert r["valid"] and r["summary"] == "ran ```x``` ok"
