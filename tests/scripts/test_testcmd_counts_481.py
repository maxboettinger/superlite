"""testcmd.parse_output: honest generic counts (#481): summary lines win, green without a count is not green."""
from __future__ import annotations

import json
import subprocess
import sys

from _fixtures import DISK_FREE
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def test_vitest_summary_wins():
    t = (" ❯ packages/a/test/x.test.ts (18 tests | 3 failed) 25ms\n"
         " Test Files  1 failed (1)\n      Tests  3 failed | 15 passed (18)")
    r = testcmd.parse_output(t, 1)
    assert triple(r) == (15, 3, 0) and r["counted"] is True and r["empty"] == ""


def test_vitest_skipped():
    assert triple(testcmd.parse_output("      Tests  1 failed | 15 passed | 2 skipped (18)", 1)) == (15, 1, 2)


def test_jest_summary():
    t = "Test Suites: 1 failed, 1 total\nTests:       3 failed, 15 passed, 18 total"
    assert triple(testcmd.parse_output(t, 1)) == (15, 3, 0)


def test_mocha_counts():
    assert triple(testcmd.parse_output("  12 passing (30ms)\n  2 failing\n  1 pending", 2)) == (12, 2, 1)


def test_green_without_count_is_not_green():
    r = testcmd.parse_output("done", 0)
    assert triple(r) == (0, 0, 0) and r["counted"] is False


def test_red_without_count_is_one_uncounted_failure():
    r = testcmd.parse_output("done", 1)
    assert triple(r) == (0, 1, 0) and r["counted"] is False and r["empty"] == ""


def test_no_test_files_line():
    r = testcmd.parse_output("No test files found, exiting with code 0", 0)
    assert triple(r) == (0, 0, 0) and r["names"] == [] and r["counted"] is False
    assert r["empty"] == "No test files found, exiting with code 0"


def test_xcode_return_has_keys():
    r = testcmd.parse_output("✔ Test run with 2 tests in 1 suite passed after 0.1 seconds.", 0)
    assert r["empty"] == "" and r["counted"] is True


def test_run_tests_no_count_stops(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": "echo done"}), encoding="utf-8")
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert cp.returncode == 1, cp.stdout + cp.stderr
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert s["error"].startswith("no tests ran:")


GREEN_OBJ = {"summary": {"warnings": 0, "errors": 0, "linker_errors": 0, "test_time": "0.003s", "passed_tests": 2, "failed_tests": 0}, "status": "success"}
RED_OBJ = {"status": "failed", "summary": {"failed_tests": 1, "passed_tests": 1, "errors": 0, "warnings": 0, "linker_errors": 0, "test_time": "0.003s"}, "failed_tests": [{"message": "XCTAssertEqual failed: (\"1\") is not equal to (\"2\")", "file": "/src/Tests/ArchitectureTests/PipelineConfigTests.swift", "duration": 0.002, "line": 42, "test": "ArchitectureTests.PipelineConfigTests testB"}]}
ZERO_OBJ = {"summary": {"errors": 0, "failed_tests": 0, "linker_errors": 0, "warnings": 0}, "status": "success"}
BUILD_OBJ = {"status": "failed", "errors": [{"file": "/src/App/Foo.swift", "message": "cannot find 'bar' in scope", "line": 10}], "summary": {"linker_errors": 0, "failed_tests": 0, "errors": 1, "warnings": 0}}


def dump(obj):
    return json.dumps(obj, indent=2, separators=(",", " : "))


GREEN, RED, ZERO, BUILD = dump(GREEN_OBJ), dump(RED_OBJ), dump(ZERO_OBJ), dump(BUILD_OBJ)
RED_NAME = "ArchitectureTests.PipelineConfigTests testB"
RED_MSG = 'XCTAssertEqual failed: ("1") is not equal to ("2")'
RED_FILE = "/src/Tests/ArchitectureTests/PipelineConfigTests.swift"


def test_xcsift_green():
    r = testcmd.xcsift_summary(GREEN.splitlines(), 0)
    assert triple(r) == (2, 0, 0) and r["counted"] is True and r["empty"] == "" and r["format"] == "xcsift"
    assert r["names"] == [] and r["sites"] == [] and r["error"] == "" and r["marker"] == ""


def test_xcsift_red():
    r = testcmd.xcsift_summary(RED.splitlines(), 1)
    assert triple(r) == (1, 1, 0) and r["names"] == [RED_NAME]
    assert r["reasons"] == {RED_NAME: (RED_MSG, 42)}
    assert r["sites"] == [(RED_FILE, 42, f"{RED_NAME}: {RED_MSG}")]


def test_xcsift_zero_and_not_xcsift():
    r = testcmd.xcsift_summary(ZERO.splitlines(), 0)
    assert triple(r) == (0, 0, 0) and r["counted"] is False and r["empty"] == "xcsift summary: 0 passed, 0 failed tests"
    assert testcmd.xcsift_summary(["7 passed in 0.1s"], 0) is None


def test_xcsift_inside_wrapper_text():
    r = testcmd.xcsift_summary(["wrapper: building"] + RED.splitlines() + ["wrapper: done in 3 s"], 1)
    assert triple(r) == (1, 1, 0) and r["names"] == [RED_NAME]


def test_xcsift_last_object_wins():
    r = testcmd.xcsift_summary((GREEN + "\n" + RED).splitlines(), 1)
    assert triple(r) == (1, 1, 0)


def test_xcsift_non_int_counts_ignored():
    text = '{"summary": {"passed_tests": "5"}}'
    assert testcmd.xcsift_summary(text.splitlines(), 0) is None


def test_xcsift_nested_object_is_not_the_summary():
    r = testcmd.xcsift_summary(RED.splitlines(), 1)
    assert r["passed"] == 1


def test_xcsift_build_error():
    r = testcmd.xcsift_summary(BUILD.splitlines(), 1)
    assert r["failed"] == 1 and r["counted"] is False and r["error"] == "/src/App/Foo.swift:10: cannot find 'bar' in scope"


def test_xcsift_status_failed_green_exit():
    assert testcmd.xcsift_summary(BUILD.splitlines(), 0)["failed"] == 1


def test_xcsift_skipped_key():
    obj = {"summary": {"passed_tests": 1, "failed_tests": 0, "skipped_tests": 3}, "status": "success"}
    assert testcmd.xcsift_summary(dump(obj).splitlines(), 0)["skipped"] == 3


def test_raw_xcode_lines_win():
    t = "Executed 3 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds\n" + GREEN
    r = testcmd.parse_output(t, 0)
    assert triple(r) == (3, 0, 0) and "format" not in r


def _run_cmd_json(tmp_path, body):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": "cat out.json"}), encoding="utf-8")
    (tmp_path / "out.json").write_text(body, encoding="utf-8")
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    return cp, json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_run_tests_xcsift_green_passes(tmp_path):
    cp, s = _run_cmd_json(tmp_path, GREEN)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert s["passed"] == 2


def test_run_tests_xcsift_zero_stops(tmp_path):
    cp, s = _run_cmd_json(tmp_path, ZERO)
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert s["error"].startswith("no tests ran:") and "runner: xcsift summary: 0 passed, 0 failed tests" in s["error"]
