"""hooks/rewrite-test-runs: a worker's run of exactly its own task's `**Tests:** cmd=` is rewritten to a
background `sl run_tests --task Tn`; every other raw run on an isolate stack stays denied."""
import json

import pytest
from test_rewrite_isolate import POOL, RAW, SWIFT, run, setup  # noqa: F401

PLAN = "### T3 x\n**Owns:** a.swift\n**Tests:** fast cmd=" + RAW + "\n\n### T5 y\n**Tests:** fast\n"


@pytest.fixture
def proj(tmp_path):
    setup(tmp_path)
    (tmp_path / ".superlite" / "plan.md").write_text(PLAN)
    return tmp_path


def out(r):
    return json.loads(r.stdout)["hookSpecificOutput"]


def rows(proj):
    return [json.loads(ln) for ln in (proj / ".superlite" / "incidents.jsonl").read_text().splitlines()]


def test_own_cmd_rewritten(proj):
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 0
    h = out(r)
    cmd = h["updatedInput"]["command"]
    assert h["permissionDecision"] == "allow"
    assert "--fast" not in cmd
    assert "run_tests --task T3 --background" in cmd and "Scripts/test.sh" not in cmd
    assert "sl run_tests --wait" in h["additionalContext"]
    assert "run_in_background" not in h["updatedInput"]
    last = rows(proj)[-1]
    assert last["kind"] == "rule-rewrite" and last["rule"] == "own-tests-cmd"


def test_backticked_cmd_matches(proj):
    (proj / ".superlite" / "plan.md").write_text(PLAN.replace("cmd=" + RAW, "cmd=`" + RAW + "`"))
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 0 and "run_tests --task T3 --background" in out(r)["updatedInput"]["command"]


def test_chain_keeps_other_segments(proj):
    r = run(proj, f"cd {proj} && {RAW} 2>&1 | tail -15", agent_id="a1")
    assert r.returncode == 0
    cmd = out(r)["updatedInput"]["command"]
    assert "cd " in cmd and "run_tests --task T3 --background" in cmd and "| tail -15" in cmd
    assert "2>&1" not in cmd


def test_stable_plan_path(proj):
    (proj / "docs" / "plans").mkdir(parents=True)
    (proj / "docs" / "plans" / "p.md").write_text("### T5 y\n**Tests:** fast cmd=" + RAW + "\n")
    (proj / ".superlite" / "stable.json").write_text(json.dumps({"plan": "docs/plans/p.md"}))
    r = run(proj, RAW, env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert r.returncode == 0 and "run_tests --task T5 --background" in out(r)["updatedInput"]["command"]


def test_quotes_escaped(proj):
    cmd_in = 'Scripts/test.sh -only-testing:A "b"'
    (proj / ".superlite" / "plan.md").write_text("### T3 x\n**Tests:** fast cmd=`" + cmd_in + "`\n")
    r = run(proj, cmd_in, agent_id="a1")
    assert r.returncode == 0
    assert "run_tests --task T3 --background" in out(r)["updatedInput"]["command"]
    row = rows(proj)[-1]
    assert row["rule"] == "own-tests-cmd" and '"' in row["command"]


def test_other_command_still_denied(proj):
    r = run(proj, "Scripts/test.sh -only-testing:AppTests/BarTests", agent_id="a1")
    assert r.returncode == 2
    assert "--task T3" in r.stderr and "own **Tests:** cmd=" in r.stderr and "-- <args>" not in r.stderr


def test_task_without_cmd_denied(proj):
    r = run(proj, RAW, env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert r.returncode == 2 and "-- <args>" in r.stderr and "own **Tests:** cmd=" not in r.stderr


def test_monitor_never_rewritten(proj):
    import os
    import subprocess

    from test_rewrite_isolate import BASH, HOOK, HOST
    data = {"tool_name": "Monitor", "tool_input": {"command": RAW}, "agent_id": "a1"}
    env = {k: v for k, v in os.environ.items() if k not in HOST}
    env.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj / "_home")})
    r = subprocess.run([BASH, str(HOOK)], input=json.dumps(data), capture_output=True, text=True, env=env)
    assert r.returncode == 2 and r.stdout == ""


def test_no_plan_denied(proj):
    (proj / ".superlite" / "plan.md").unlink()
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 2


def test_non_isolate_own_cmd_untouched(tmp_path):
    cmd = "pytest tests/test_a.py"
    setup(tmp_path, {"language": "python", "test": "pytest {files}", "test_file": "pytest {file}"})
    (tmp_path / ".superlite" / "plan.md").write_text("### T3 x\n**Tests:** fast cmd=" + cmd + "\n")
    r = run(tmp_path, cmd, agent_id="a1")
    assert r.returncode == 0 and r.stdout == ""
