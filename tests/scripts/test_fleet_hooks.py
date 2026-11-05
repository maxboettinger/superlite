# tests/scripts/test_fleet_hooks.py
import json, os, subprocess, sys
from pathlib import Path
import pytest
from test_plan_tools import ROOT
HOOKS = ROOT / "hooks"

def run_hook(name, stdin, env, cwd):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}; e.update(env); e["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    return subprocess.run(["bash", str(HOOKS / name)], input=stdin, capture_output=True, text=True, env=e, cwd=cwd)

@pytest.fixture
def sd(tmp_path):
    d = tmp_path / "proj" / ".superlite"; d.mkdir(parents=True); (d / "stable.json").write_text("{}"); return d

def worker_env(sd):
    return {"SUPERLITE_FLEET_WORKER": "W1", "SUPERLITE_FLEET_AGENT": "superlite:implementer", "SUPERLITE_STATE_DIR": str(sd)}

def test_worker_stop_writes_record(sd):
    stdin = json.dumps({"session_id": "s1", "transcript_path": "/t/w1.jsonl", "last_assistant_message": "Status: DONE\nFiles: a"})
    r = run_hook("capture-worker-stop", stdin, worker_env(sd), sd.parent); assert r.returncode == 0
    rec = json.loads((sd / "metrics.jsonl").read_text().splitlines()[-1])
    assert rec["ev"] == "stop" and rec["agent_id"] == "W1" and rec["type"] == "fleet:superlite:implementer"
    assert rec["transcript"] == "/t/w1.jsonl" and rec["last"] == "Status: DONE Files: a" and isinstance(rec["t"], int) and rec["t"] > 10**12

def test_worker_stop_silent_without_env(sd):
    r = run_hook("capture-worker-stop", json.dumps({"session_id": "s1", "transcript_path": "/t"}), {"SUPERLITE_STATE_DIR": str(sd)}, sd.parent)
    assert r.returncode == 0 and r.stdout == "" and not (sd / "metrics.jsonl").exists()

def test_worker_stop_silent_when_stop_hook_active(sd):
    stdin = json.dumps({"session_id": "s1", "transcript_path": "/t", "stop_hook_active": True, "last_assistant_message": "x"})
    r = run_hook("capture-worker-stop", stdin, worker_env(sd), sd.parent)
    assert r.returncode == 0 and not (sd / "metrics.jsonl").exists()

def test_guard_exempts_worker(sd):
    call = json.dumps({"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": str(sd.parent / "src" / "a.py"), "content": "x"}, "cwd": str(sd.parent)})
    r = run_hook("block-coordinator-edits", call, worker_env(sd), sd.parent)
    assert r.returncode == 0 and r.stdout.strip() == ""
    plain = run_hook("block-coordinator-edits", call, {"SUPERLITE_STATE_DIR": str(sd)}, sd.parent)
    assert plain.returncode != 0 or '"deny"' in plain.stdout or "Blocked" in plain.stderr

def test_session_start_worker_note(sd):
    stdin = json.dumps({"session_id": "s1", "source": "startup", "cwd": str(sd.parent)})
    r = run_hook("session-start", stdin, worker_env(sd), sd.parent); assert r.returncode == 0
    assert "superlite fleet worker W1" in r.stdout and "superlite:implementer" in r.stdout and "/superlite:start" not in r.stdout and json.loads(r.stdout)
    normal = run_hook("session-start", stdin, {}, sd.parent); assert "fleet worker" not in normal.stdout and "superlite" in normal.stdout

def test_hooks_json_registers_worker_stop():
    cfg = json.loads((HOOKS / "hooks.json").read_text())
    cmds = [h["command"] for entry in cfg["hooks"]["Stop"] for h in entry["hooks"]]
    assert any("final-review-check" in c for c in cmds) and any("capture-worker-stop" in c for c in cmds)
    assert [i for i, c in enumerate(cmds) if "final-review-check" in c][0] < [i for i, c in enumerate(cmds) if "capture-worker-stop" in c][0]
