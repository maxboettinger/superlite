"""#1091: xcsift errors[] entries that are console log lines never fail a run that exited 0 with no failed test."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from _fixtures import DISK_FREE
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

ZW = "​"
STAMP = "2026-11-20 15:04:16.527985+0100 xctest[86859:29490527] [error] CoreData"
TOKEN = "Unable to create token NSXPCConnection.  NSXPCStoreServerEndpointFactory 0x756e894c20 -newEndpointWithError returned error"
LOG = {"message": TOKEN, "file": f"{ZW}{ZW}{STAMP}"}
PLAIN = {"message": "[error] CoreData: Unable to create token"}
BUILD = {"file": "/src/App/Foo.swift", "message": "cannot find 'bar' in scope", "line": 10}
BUILD_ERR = "/src/App/Foo.swift:10: cannot find 'bar' in scope"
FAILED_TEST = {"test": "ChatTests testSync", "message": "Expectation failed", "file": "/src/Tests/ChatTests.swift", "line": 3}


def block(passed=0, failed=0, errors=(), status=None, failed_tests=()):
    obj = {"summary": {"failed_tests": failed, "passed_tests": passed, "errors": len(errors), "warnings": 0, "linker_errors": 0}}
    if errors:
        obj["errors"] = list(errors)
    if failed_tests:
        obj["failed_tests"] = list(failed_tests)
    obj["status"] = status or ("failed" if failed or errors else "success")
    return obj


def out(*objs):
    lines = ["command: maxapp test", "exit: 0", ""]
    for o in objs:
        lines += json.dumps(o, indent=2, separators=(",", " : ")).splitlines()
    return lines


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def _run(tmp_path, objs, rc):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": f"cat out.json; exit {rc}"}), encoding="utf-8")
    (tmp_path / "out.json").write_text("\n".join(out(*objs)) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    return cp, json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_real_pix_block_is_green_and_reports_the_log_line():
    r = testcmd.xcsift_summary(out(block(7590, errors=[LOG])), 0)
    assert triple(r) == (7590, 0, 0) and r["errors"] == [] and r["error"] == ""
    assert r["log_lines"] == 1 and r["log_line"].startswith(f"{STAMP}: Unable to create token")


def test_timestamp_file_with_a_line_is_a_log_line():
    r = testcmd.xcsift_summary(out(block(7590, errors=[{**LOG, "line": 4}])), 0)
    assert r["failed"] == 0 and r["errors"] == [] and r["log_lines"] == 1


def test_timestamp_file_is_dropped_on_a_red_exit_too():
    r = testcmd.xcsift_summary(out(block(0, errors=[{**LOG, "line": 4}, BUILD], status="failed")), 1)
    assert r["failed"] == 1 and r["errors"] == [BUILD_ERR] and r["error"] == BUILD_ERR and r["log_lines"] == 1


def test_quiet_run_drops_lineless_error_of_uncounted_block():
    r = testcmd.xcsift_summary(out(block(7590), block(0, errors=[PLAIN], status="failed")), 0)
    assert triple(r) == (7590, 0, 0) and r["errors"] == [] and r["error"] == "" and r["empty"] == ""
    assert r["log_lines"] == 1 and r["log_line"] == PLAIN["message"]


def test_red_exit_keeps_lineless_error_of_uncounted_block():
    r = testcmd.xcsift_summary(out(block(0, errors=[PLAIN], status="failed")), 1)
    assert r["failed"] == 1 and r["errors"] == [PLAIN["message"]] and "log_lines" not in r


def test_failed_tests_end_the_quiet_rule():
    r = testcmd.xcsift_summary(out(block(10, 1, failed_tests=[FAILED_TEST]), block(0, errors=[PLAIN], status="failed")), 0)
    assert r["failed"] >= 1 and r["errors"] == [PLAIN["message"]] and r["names"] == ["ChatTests testSync"]


def test_quiet_only_log_lines_is_no_result():
    r = testcmd.xcsift_summary(out(block(0, errors=[LOG], status="failed")), 0)
    assert triple(r) == (0, 0, 0) and r["counted"] is False and r["errors"] == [] and r["error"] == ""
    assert r["empty"] == "xcsift summary: 0 passed, 0 failed tests" and r["log_lines"] == 1


def test_no_log_lines_key_when_nothing_dropped():
    r = testcmd.xcsift_summary(out(block(5)), 0)
    assert "log_lines" not in r and "log_line" not in r


def test_merge_parsed_sums_log_lines():
    a = {"passed": 1, "failed": 0, "skipped": 0, "names": [], "tail": [], "counted": True, "log_lines": 2, "log_line": "x"}
    b = {"passed": 1, "failed": 0, "skipped": 0, "names": [], "tail": [], "counted": True, "log_lines": 1, "log_line": "y"}
    m = testcmd.merge_parsed([("a", a), ("b", b)])
    assert m["log_lines"] == 3 and m["log_line"] == "x"
    plain = {k: v for k, v in a.items() if not k.startswith("log_")}
    assert "log_lines" not in testcmd.merge_parsed([("a", plain), ("b", dict(plain))])


def test_green_maxapp_run_is_green_with_warning(tmp_path):
    cp, s = _run(tmp_path, [block(7590, errors=[LOG, LOG])], 0)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert s["passed"] == 7590 and s["failed"] == 0 and not any("build error" in f for f in s["failures"])
    assert s["warning"].startswith("xcsift listed 2 console log line(s) under errors[], not counted as failures: ")
    assert "run_tests: WARNING: xcsift listed 2 console log line(s)" in cp.stderr


def test_red_run_lists_no_log_line_failure(tmp_path):
    cp, s = _run(tmp_path, [block(10, 1, errors=[LOG], failed_tests=[FAILED_TEST])], 1)
    assert cp.returncode == 1
    assert s["failed"] == 1 and not any("CoreData" in f or "build error" in f for f in s["failures"])
