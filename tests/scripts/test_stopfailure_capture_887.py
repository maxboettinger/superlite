# tests/scripts/test_stopfailure_capture_887.py
# #887: a turn that ends on an API error fires StopFailure, not Stop; it is bound to capture-worker-stop so the
# worker's stop record still lands in metrics.jsonl (the record carries the API error text in `last`).
import json
from pathlib import Path
import pytest
from test_fleet_hooks import HOOKS, run_hook

STOP_FAILURE_INPUT = {"session_id": "s1", "transcript_path": "/tmp/t1.jsonl", "cwd": "/tmp", "hook_event_name": "StopFailure",
                      "error": "rate_limit", "error_details": "429 Too Many Requests"}

@pytest.fixture
def sd(tmp_path):
    d = tmp_path / "state"; d.mkdir(); return d

def worker_env(sd):
    return {"SUPERLITE_FLEET_WORKER": "W3", "SUPERLITE_FLEET_AGENT": "superlite:implementer", "SUPERLITE_FLEET_PARENT_DIR": str(sd)}

def test_stopfailure_bound_to_capture_worker_stop():
    cfg = json.loads((HOOKS / "hooks.json").read_text())["hooks"]
    assert cfg["StopFailure"] == [{"hooks": [{"type": "command", "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/capture-worker-stop"', "shell": "bash"}]}]
    assert [h["command"] for e in cfg["Stop"] for h in e["hooks"]] == [
        'bash "${CLAUDE_PLUGIN_ROOT}/hooks/final-review-check"', 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/capture-worker-stop"']

def test_stopfailure_payload_writes_stop_record(sd):
    stdin = json.dumps({**STOP_FAILURE_INPUT, "last_assistant_message": "API Error: Rate limit reached"})
    r = run_hook("capture-worker-stop", stdin, worker_env(sd), sd.parent)
    assert r.returncode == 0 and r.stdout == ""
    lines = (sd / "metrics.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert (rec["ev"], rec["agent_id"], rec["type"], rec["transcript"], rec["last"]) == (
        "stop", "W3", "fleet:superlite:implementer", "/tmp/t1.jsonl", "API Error: Rate limit reached")

def test_stopfailure_without_message_writes_empty_last(sd):
    r = run_hook("capture-worker-stop", json.dumps(STOP_FAILURE_INPUT), worker_env(sd), sd.parent)
    assert r.returncode == 0
    lines = (sd / "metrics.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["last"] == ""

def test_stopfailure_outside_worker_writes_nothing(sd):
    env = {k: v for k, v in worker_env(sd).items() if k != "SUPERLITE_FLEET_WORKER"}
    r = run_hook("capture-worker-stop", json.dumps(STOP_FAILURE_INPUT), env, sd.parent)
    assert r.returncode == 0 and not (sd / "metrics.jsonl").exists()
