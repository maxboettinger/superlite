"""hooks/rewrite-test-runs: a subagent's or fleet worker's raw run of the configured test command on an
isolate stack (swift, go, rust, csharp) is denied with the exact `sl run_tests --fast ... --task Tn` command."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "rewrite-test-runs"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
SL = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl").as_posix()
SWIFT = {"language": "swift", "test": "xcodebuild test -scheme X {only_testing}",
         "test_file": "Scripts/test.sh -only-testing:{file}"}
RAW = "Scripts/test.sh -only-testing:AppTests/FooTests"
POOL = {"agents": [{"id": "a1", "tier": "sonnet", "busy": True, "current": "T3"},
                   {"id": "W2", "tier": "sonnet", "busy": True, "current": "T5,T6"}]}
HOST = ("SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_AGENT", "SUPERLITE_STATE_DIR", "CLAUDE_PLUGIN_ROOT",
        "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID")


def setup(proj, cfg=SWIFT):
    sd = proj / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "pool.json").write_text(json.dumps(POOL))
    if cfg is not None:
        (sd / "test-cmd.json").write_text(json.dumps(cfg))
    return proj


@pytest.fixture
def proj(tmp_path):
    return setup(tmp_path)


def run(proj, command, agent_id=None, env=None):
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_id:
        data["agent_id"] = agent_id
    base = {k: v for k, v in os.environ.items() if k not in HOST}  # the host may itself be a fleet worker
    base.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj / "_home"), **(env or {})})
    return subprocess.run([BASH, str(HOOK)], input=json.dumps(data), capture_output=True, text=True, env=base)


def test_subagent_raw_swift_run_denied(proj):
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 2 and r.stdout == ""
    assert "run_tests --fast" in r.stderr and "--task T3" in r.stderr and "--background" in r.stderr
    assert "T5" not in r.stderr
    rows = [json.loads(ln) for ln in (proj / ".superlite" / "incidents.jsonl").read_text().splitlines()]
    assert rows[-1]["kind"] == "rule-block" and rows[-1]["agent"] == "subagent" and "Scripts/test.sh" in rows[-1]["target"]


def test_fleet_worker_matched_by_env(proj):
    r = run(proj, RAW, env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert r.returncode == 2 and r.stdout == ""
    assert "run_tests --fast" in r.stderr and "--task T5" in r.stderr and "T6" not in r.stderr


def test_configured_command_by_its_two_words_denied(proj):
    r = run(proj, "xcodebuild test -scheme X -only-testing:AppTests/FooTests", agent_id="a1")
    assert r.returncode == 2 and "--task T3" in r.stderr


def test_chained_segment_denied(proj):
    r = run(proj, "cd app && Scripts/test.sh -only-testing:AppTests/FooTests 2>&1 | tail -5", agent_id="a1")
    assert r.returncode == 2 and "--task T3" in r.stderr


@pytest.mark.parametrize("cmd", ["ls -la", "xcodebuild -version", "git status", "echo Scripts/test.sh"])
def test_other_subagent_commands_pass(proj, cmd):
    r = run(proj, cmd, agent_id="a1")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_python_stack_not_isolated(proj):
    setup(proj, {**SWIFT, "language": "python"})
    r = run(proj, RAW, agent_id="a1")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_explicit_isolate_false_not_denied(proj):
    setup(proj, {**SWIFT, "isolate": False})
    assert run(proj, RAW, agent_id="a1").returncode == 0


def test_sl_run_tests_passes(proj):
    r = run(proj, f'bash "{SL}" run_tests --fast x --task T3', agent_id="a1")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    r = run(proj, f'bash "{SL}" run_tests --fast x --task T5', env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_coordinator_run_untouched(proj):
    r = run(proj, RAW)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_unknown_agent_still_denied_without_task_id(proj):
    r = run(proj, RAW, agent_id="zz")
    assert r.returncode == 2 and "run_tests --fast" in r.stderr and "--task <Tn>" in r.stderr


def test_main_checkout_config_fallback(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    for args in (["init", "-q"], ["config", "user.name", "T"], ["config", "user.email", "t@example.com"],
                 ["commit", "-q", "--allow-empty", "-m", "base"]):
        subprocess.run(["git", *args], cwd=main, check=True, capture_output=True)
    (main / ".superlite").mkdir()
    (main / ".superlite" / "test-cmd.json").write_text(json.dumps(SWIFT))
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(wt), "-b", "wt"], cwd=main, check=True, capture_output=True)
    setup(wt, cfg=None)  # a run marker in the worktree, no test-cmd.json of its own
    assert not (wt / ".superlite" / "test-cmd.json").exists()
    r = run(wt, RAW, agent_id="a1")
    assert r.returncode == 2 and "--task T3" in r.stderr
    plain = tmp_path / "plain"  # not a worktree, no config anywhere: nothing is isolated
    plain.mkdir()
    setup(plain, cfg=None)
    assert run(plain, RAW, agent_id="a1").returncode == 0


def test_quoted_command_denied(proj):
    r = run(proj, 'Scripts/test.sh -only-testing:"AppTests/Foo Tests"', agent_id="a1")
    assert r.returncode == 2 and "--task T3" in r.stderr


def test_batch_current_names_first_task(proj):
    (proj / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"id": "a1", "current": "T2,T4"}]}))
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 2 and "--task T2" in r.stderr and "T4" not in r.stderr


def test_agent_without_current_and_no_pool(proj):
    (proj / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"id": "a1", "busy": False}]}))
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 2 and "--task <Tn>" in r.stderr
    (proj / ".superlite" / "pool.json").unlink()
    (proj / ".superlite" / "prime.md").write_text("run\n")  # still an active run, but no pool
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 2 and "--task <Tn>" in r.stderr


@pytest.mark.parametrize("body", ["{not json", "", '{"language": swift', '{"test": "Scripts/test.sh x", "isolate": }'])
def test_malformed_test_cmd_passes_without_crash(proj, body):
    (proj / ".superlite" / "test-cmd.json").write_text(body)
    r = run(proj, RAW, agent_id="a1")
    assert r.returncode == 0 and "Traceback" not in r.stderr and "syntax error" not in r.stderr
