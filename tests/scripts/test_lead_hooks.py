# tests/scripts/test_lead_hooks.py
import json
from test_fleet_hooks import run_hook

def env(sd, **kw):
    return {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(sd), **kw}

def start(sd, **kw):
    r = run_hook("session-start", json.dumps({"session_id": "s1", "source": "startup", "cwd": str(sd.parent)}), env(sd, **kw), sd.parent)
    return r.stdout, json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

def test_session_start_gives_a_lead_its_note_and_the_full_context(tmp_path):
    sd = tmp_path / "wt" / ".superlite"; sd.mkdir(parents=True)
    t = start(sd)[1]
    assert "You are superlite batch lead W2." in t and "using-superlite" in t and "fleet worker W2" not in t
    assert "Never end your turn while your fleet workers run" in t and "NEEDS_DECISION" in t
    assert "fleet worker W2" in start(sd, SUPERLITE_FLEET_ROLE="implementer")[1]
    raw, t = start(sd, SUPERLITE_FLEET_WORKER='W2" x')
    assert "batch lead W?." in t and 'W2" x' not in raw

def test_lead_test_runs_are_rewritten_like_the_coordinators(tmp_path):
    sd = tmp_path / "wt" / ".superlite"; sd.mkdir(parents=True); (sd / "pool.json").write_text("{}")
    call = json.dumps({"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "pytest"}, "cwd": str(sd.parent)})
    out = json.loads(run_hook("rewrite-test-runs", call, env(sd), sd.parent).stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "allow" and "run_tests --full" in out["updatedInput"]["command"]
    r = run_hook("rewrite-test-runs", call, env(sd, SUPERLITE_FLEET_ROLE="fixer"), sd.parent)
    assert r.returncode == 2 and "must not run the full test suite" in r.stderr
