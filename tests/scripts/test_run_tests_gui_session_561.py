"""#561 / B119: run_tests stops with ENV-ERROR outside the macOS GUI session or with an unreachable test runner; located pytest ids."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

RUN_TESTS = SCRIPTS / "run_tests.py"
MAC = "xcodebuild test -scheme App -destination 'platform=macOS'"
GREEN = ("echo \"Test Case '-[AppTests.T test_a]' passed (0.001 seconds).\"\n"
         "echo 'Executed 1 test, with 0 failures (0 unexpected) in 0.001 (0.002) seconds'\n")
TMD = ("Testing failed:\n\tFailed to establish communication with the test runner. (Underlying Error: The connection to "
       "service named com.apple.testmanagerd.control was invalidated: failed at lookup with error 3 - No such process.)\n"
       "\tTest session results, code coverage, and logs:\n\t\t/tmp/x.xcresult\n\n** TEST FAILED **\n")
PROBE = ("bringing up nodes...\n\n.F    [100%]\n=================================== FAILURES ===================================\n"
         "___________________________________ test_bad ___________________________________\n"
         "[gw1] linux -- Python 3.12.3 /usr/bin/python\n\n    def test_bad():\n>       assert 5.23 < 5\nE       assert 5.23 < 5\n\n"
         "tests/test_probe.py:5: AssertionError\n=========================== short test summary info ============================\n"
         "FAILED tests/test_probe.py::test_bad - assert 5.23 < 5\n1 failed, 1 passed in 0.31s\nmaxapp remote: command exited 1\n")


def script(path, body):
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def project(tmp_path, kind="Background", xcode=GREEN, xcode_exit=0, **cfg):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "bin").mkdir()
    script(tmp_path / "bin" / "launchctl", f"echo {kind}")
    (tmp_path / "tmd.txt").write_text(TMD, encoding="utf-8")
    script(tmp_path / "bin" / "xcodebuild", f"touch '{tmp_path}/ran.txt'\n{xcode}exit {xcode_exit}")
    cfg = {"language": "swift", "test": MAC, **cfg}
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def run(tmp_path, *args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_USER_TEST_CMD"}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_DISK_FLOOR_GB="0", SUPERLITE_DISK_WARN_GB="0",
               SUPERLITE_MACHINE_LIMIT="0", PYTHONIOENCODING="utf-8", PATH=str(tmp_path / "bin") + os.pathsep + os.environ["PATH"],
               **(env_extra or {}))
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--log", str(sl / "incidents.jsonl"), "--ledger", str(sl / "ledger.md"),
                         "--summary", str(sl / "test-summary.json"), *args], capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_preflight_stops_background(tmp_path):
    project(tmp_path, setup=f"touch '{tmp_path}/setup.txt'")
    cp = run(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    assert "run_tests: ENV-ERROR: no macOS GUI session (launchctl managername: Background" in cp.stderr
    assert summary(tmp_path)["error"].startswith("ENV-ERROR: ")
    assert not (tmp_path / "ran.txt").exists()
    assert not (tmp_path / "setup.txt").exists()


def test_preflight_aqua_runs(tmp_path):
    project(tmp_path, kind="Aqua")
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_ios_destination_not_checked(tmp_path):
    project(tmp_path, test="xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 16'")
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert (tmp_path / "ran.txt").exists()


def test_lock_false_not_checked(tmp_path):
    project(tmp_path, lock=False)
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert (tmp_path / "ran.txt").exists()


def test_gui_check_off(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--full", env_extra={"SUPERLITE_GUI_CHECK": "0"})
    assert cp.returncode == 0, cp.both
    assert (tmp_path / "ran.txt").exists()


def test_runner_unreachable_env_error(tmp_path):
    project(tmp_path, kind="Aqua", xcode="cat tmd.txt\n", xcode_exit=65)
    cp = run(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    s = summary(tmp_path)
    assert s["error"].startswith("ENV-ERROR: xcodebuild could not reach its test runner")
    assert not [f for f in s.get("failures", []) if " to" in f or f.startswith("to")]
    assert "no-result log" in cp.stderr


def remote_project(tmp_path, out):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "out.txt").write_text(out, encoding="utf-8")
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "python", "test": "cat out.txt; exit 1", "lock": False}), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "bin").mkdir()


def test_remote_pytest_id_located(tmp_path):
    remote_project(tmp_path, PROBE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_probe.py").write_text("def test_bad():\n    assert 5.23 < 5\n", encoding="utf-8")
    run(tmp_path, "--full")
    s = summary(tmp_path)
    assert s["failures"] == ["tests/test_probe.py::test_bad: assert 5.23 < 5"], s
    assert s["files"] == {"tests/test_probe.py": [0, 1]}


def test_missing_path_stays_dash(tmp_path):
    remote_project(tmp_path, PROBE)
    run(tmp_path, "--full")
    assert summary(tmp_path)["failures"] == ["-::tests/test_probe.py::test_bad: assert 5.23 < 5"]
