"""testcmd.parse_output: honest generic counts (#481): summary lines win, green without a count is not green."""
from __future__ import annotations

import json
import subprocess
import sys

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
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert cp.returncode == 1, cp.stdout + cp.stderr
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert s["error"].startswith("no tests ran:")
