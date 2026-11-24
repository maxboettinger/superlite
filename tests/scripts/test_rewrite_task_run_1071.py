"""hooks/rewrite-test-runs (#1071): on an isolate stack a worker's raw run of the test-cmd.json "test" command with
plain arguments is rewritten to `sl -C <root> run_tests --task Tn --background -- <args>` when its pool task is a plan
task without a **Tests:** cmd=; every other raw run stays denied, the message naming the form for that worker."""
import json
import os
import shlex
import subprocess

import pytest
from test_rewrite_isolate import BASH, HOOK, HOST, SL, run, setup

MAXAPP = {"language": "swift", "test": "maxapp test", "test_file": "maxapp test {only_testing}"}
OWN = "maxapp test --only AppTests/OwnTests"
PLAN = "### T3 x\n**Owns:** a.swift\n**Tests:** fast\n\n### T5 y\n**Owns:** b.swift\n**Tests:** fast cmd=" + OWN + "\n"


@pytest.fixture
def proj(tmp_path):
    setup(tmp_path, MAXAPP)
    (tmp_path / ".superlite" / "plan.md").write_text(PLAN)
    return tmp_path


def out(r):
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]


def rows(proj):
    return [json.loads(ln) for ln in (proj / ".superlite" / "incidents.jsonl").read_text().splitlines()]


def sl_words(cmd, proj):
    seg = next(s for s in cmd.replace("&&", ";").replace("|", ";").split(";") if "run_tests" in s)
    words = shlex.split(seg)
    assert words[0] == "bash" and words[1] == SL and words[2] == "-C"
    assert os.path.realpath(words[3]) == os.path.realpath(proj) and words[4] == "run_tests"
    return words[1:]


def parses(cmd, proj):
    """run_tests' argparse takes the rewritten arguments: --help before the pass-through exits 0."""
    words = sl_words(cmd, proj)
    i = words.index("--") if "--" in words else len(words)
    return subprocess.run([BASH, *words[:i], "--help"], capture_output=True, text=True).returncode == 0


def run_monitor(proj, command, agent_id):
    data = {"tool_name": "Monitor", "tool_input": {"command": command}, "agent_id": agent_id}
    env = {k: v for k, v in os.environ.items() if k not in HOST}
    env.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj / "_home")})
    return subprocess.run([BASH, str(HOOK)], input=json.dumps(data), capture_output=True, text=True, env=env)


FIELD = [
    ("maxapp test --only AreaTests/PlanTests --only ArchitectureTests 2>&1 | tail -15",
     "-- --only AreaTests/PlanTests --only ArchitectureTests", ["| tail -15"]),
    ("sleep 120; maxapp test --only AreaTests/PlanMoveTests 2>&1 | tail -12",
     "-- --only AreaTests/PlanMoveTests", ["sleep 120;", "| tail -12"]),
    ("maxapp test --ios-only --only ScreenSnapshotTests > .build/t.log 2>&1; echo exit $?; tail -5 .build/t.log",
     "-- --ios-only --only ScreenSnapshotTests", ["echo exit $?", "tail -5 .build/t.log"]),
    ("maxapp test '-only-testing:AppTests/RetryTests/aRetry()' >/tmp/repro.log 2>&1; echo ex $?",
     "-- '-only-testing:AppTests/RetryTests/aRetry()'", ["echo ex $?"]),
    ("git diff --stat | cat; cd . && maxapp test --ios --only HealthTests 2>&1 | tail -25",
     "-- --ios --only HealthTests", ["git diff --stat", "cd . &&", "| tail -25"]),
]


@pytest.mark.parametrize("raw,args,kept", FIELD)
def test_field_forms_rewritten(proj, raw, args, kept):
    h = out(run(proj, raw, agent_id="a1"))
    cmd = h["updatedInput"]["command"]
    assert h["permissionDecision"] == "allow"
    assert "run_tests --task T3 --background " + args in cmd
    assert "maxapp test" not in cmd and "--fast" not in cmd and "2>&1" not in cmd and "repro.log" not in cmd
    assert all(k in cmd for k in kept)
    assert parses(cmd, proj)
    assert "--task T3" in h["additionalContext"] and "sl run_tests --wait" in h["additionalContext"]
    last = rows(proj)[-1]
    assert (last["kind"], last["rule"], last["agent"]) == ("rule-rewrite", "task-test-run", "subagent")
    assert "maxapp test" in last["command"]
    assert last["rewritten"].count("sl -C ") == 1 and "-> sl -C " in last["target"]


def test_fleet_worker_rewritten(proj):
    (proj / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"id": "W4", "busy": True, "current": "T3"}]}))
    r = run(proj, "maxapp test --only AreaTests 2>&1 | tail -5", env={"SUPERLITE_FLEET_WORKER": "W4"})
    cmd = out(r)["updatedInput"]["command"]
    assert "run_tests --task T3 --background -- --only AreaTests" in cmd and parses(cmd, proj)


def test_help_passes(proj):
    r = run(proj, "maxapp test --help 2>&1 | head -30", agent_id="a1")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


@pytest.mark.parametrize("raw,why", [
    ("maxapp test 2>&1 | tail -5", "no runner arguments"),
    ('maxapp test --only "Area Tests/PlanTests"', "quoted space"),
    ("maxapp test --only $(cat list.txt)", "$("),
    ("maxapp test --only A 2>&1 | tail -4; maxapp test --only B 2>&1 | tail -4", "more than one test run"),
    ("(maxapp test --only A; maxapp test --only B)", "more than one test run"),
])
def test_not_rewritten_denied(proj, raw, why):
    r = run(proj, raw, agent_id="a1")
    assert r.returncode == 2 and r.stdout == ""
    assert "--task T3 --background -- <args>" in r.stderr and "Not rewritten: " in r.stderr and why in r.stderr
    assert rows(proj)[-1]["rule"] == "isolated-test-run"


def test_monitor_never_rewritten(proj):
    r = run_monitor(proj, "maxapp test --only AreaTests 2>&1 | tail -5", "a1")
    assert r.returncode == 2 and r.stdout == "" and "Monitor call is never rewritten" in r.stderr


def test_own_cmd_rewritten_without_fast(proj):
    h = out(run(proj, OWN + " 2>&1 | tail -5", env={"SUPERLITE_FLEET_WORKER": "W2"}))
    cmd = h["updatedInput"]["command"]
    assert "run_tests --task T5 --background" in cmd and "--fast" not in cmd and " -- " not in cmd
    assert parses(cmd, proj) and rows(proj)[-1]["rule"] == "own-tests-cmd"


def test_cmd_task_other_run_denied(proj):
    r = run(proj, "maxapp test --only AppTests/OtherTests", env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert r.returncode == 2 and r.stdout == ""
    assert "exactly: " + OWN in r.stderr and "run_tests --task T5 --background" in r.stderr
    assert "-- <args>" not in r.stderr


def test_no_task_subagent_names_worker_tree(proj):
    r = run(proj, "maxapp test --only AreaTests", agent_id="b9")
    assert r.returncode == 2 and r.stdout == "" and "no plan task" in r.stderr
    assert "run_tests --fast <test files or Suite names> --worker b9 --background" in r.stderr
    assert "--task" not in r.stderr


def test_no_task_fleet_worker(proj):
    r = run(proj, "maxapp test --only AreaTests", env={"SUPERLITE_FLEET_WORKER": "W7"})
    assert r.returncode == 2 and "no plan task" in r.stderr
    assert "run_tests --fast <test files or Suite names> --background" in r.stderr
    assert "--worker" not in r.stderr and "--task" not in r.stderr


def test_pool_task_missing_from_plan_is_no_task(proj):
    (proj / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"id": "a1", "busy": True, "current": "FR1"}]}))
    r = run(proj, "maxapp test --only AreaTests", agent_id="a1")
    assert r.returncode == 2 and "no plan task" in r.stderr and "--task" not in r.stderr


def test_unreadable_plan_keeps_task_line(proj):
    (proj / ".superlite" / "plan.md").unlink()
    r = run(proj, "maxapp test --only AreaTests", agent_id="a1")
    assert r.returncode == 2 and r.stdout == ""
    assert "--task T3 --background -- <args>" in r.stderr and "no readable plan names T3" in r.stderr


def test_test_file_runner_not_test_command_denied(proj):
    cfg = {"language": "swift", "test": "xcodebuild test -scheme X {only_testing}",
           "test_file": "Scripts/test.sh -only-testing:{file}"}
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg))
    r = run(proj, "Scripts/test.sh -only-testing:AppTests/BarTests", agent_id="a1")
    assert r.returncode == 2 and r.stdout == "" and 'not the test-cmd.json "test" command' in r.stderr


def test_outside_plan_root_untouched(proj, tmp_path_factory):
    other = tmp_path_factory.mktemp("other")
    r = run(proj, f"cd {other} && maxapp test --only AreaTests", agent_id="a1")
    assert (r.returncode, r.stdout) == (0, "")


def test_odd_quote_after_raw_run_denied(proj):
    r = run(proj, 'maxapp test --only X; echo "a;b"', agent_id="a1")
    assert r.returncode == 2 and r.stdout == "" and "a quote spans a separator" in r.stderr
    assert rows(proj)[-1]["rule"] == "isolated-test-run"


def test_odd_quote_before_raw_run_passes(proj):
    r = run(proj, 'echo "a;b"; maxapp test --only X', agent_id="a1")
    assert (r.returncode, r.stdout) == (0, "")


def test_own_cmd_plus_second_raw_run_denied(proj):
    r = run(proj, OWN + "; maxapp test --only B", env={"SUPERLITE_FLEET_WORKER": "W2"})
    assert r.returncode == 2 and r.stdout == "" and "exactly: " + OWN in r.stderr


def test_monitor_own_cmd_says_never_rewritten(proj):
    (proj / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"id": "a1", "busy": True, "current": "T5"}]}))
    r = run_monitor(proj, OWN, "a1")
    assert r.returncode == 2 and "Monitor call is never rewritten" in r.stderr and "exactly: " + OWN in r.stderr
