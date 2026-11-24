"""#1076: every xcsift summary block of a run counts (`maxapp test` prints one for macOS, then one for iOS)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from _fixtures import DISK_FREE
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

MAC = {"summary": {"linker_errors": 0, "failed_tests": 0, "passed_tests": 8284, "test_time": "84.1s", "errors": 0, "warnings": 50}, "status": "success"}
IOS = {"summary": {"failed_tests": 0, "errors": 0, "linker_errors": 0, "warnings": 0, "passed_tests": 33, "test_time": "35.1s"}, "status": "success"}
NOISY_MAC = {"summary": {"linker_errors": 0, "failed_tests": 0, "passed_tests": 8335, "errors": 1, "warnings": 50},
             "errors": [{"file": "2026-11-23 13:49:54.993021+0100 xctest[69467:414404970] [error] CoreData",
                         "message": "Unable to create token NSXPCConnection."}],
             "status": "failed"}
IOS_RED = {"status": "failed", "summary": {"failed_tests": 1, "passed_tests": 32, "errors": 0, "warnings": 0, "linker_errors": 0},
           "failed_tests": [{"test": "SnapshotTests testHome", "message": "snapshot differs", "file": "/src/Tests/SnapshotTests.swift", "line": 12}]}
IOS_BUILD = {"status": "failed", "summary": {"failed_tests": 0, "errors": 1, "warnings": 0, "linker_errors": 0},
             "errors": [{"file": "/src/App/Foo.swift", "message": "cannot find 'bar' in scope", "line": 10}]}
FEEL_CRASH = {"status": "failed", "summary": {"failed_tests": 0, "passed_tests": 3, "errors": 1, "warnings": 0, "linker_errors": 0},
              "errors": [{"file": "ArchitectureTests/AppearanceTests.swift", "line": 14, "message": "'try!' expression unexpectedly raised an error"}]}
CRASH_ERR = "ArchitectureTests/AppearanceTests.swift:14: 'try!' expression unexpectedly raised an error"
BUILD_ERR = "/src/App/Foo.swift:10: cannot find 'bar' in scope"


def dump(obj):
    return json.dumps(obj, indent=2, separators=(",", " : "))


def out(*objs):
    lines = ["command: maxapp test"]
    for o in objs:
        lines += dump(o).splitlines() + ["maxapp: next platform"]
    return lines


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def test_two_green_blocks_are_summed():
    r = testcmd.xcsift_summary(out(MAC, IOS), 0)
    assert triple(r) == (8317, 0, 0)
    assert r["counted"] is True and r["empty"] == "" and r["errors"] == [] and r["error"] == "" and r["names"] == []


def test_counted_block_with_status_failed_stays_green():
    r = testcmd.xcsift_summary(out(NOISY_MAC, IOS), 0)
    assert triple(r) == (8368, 0, 0)
    assert r["errors"] == [] and r["error"] == ""


def test_single_counted_block_with_status_failed_stays_green():
    r = testcmd.xcsift_summary(dump(NOISY_MAC).splitlines(), 0)
    assert triple(r) == (8335, 0, 0) and r["errors"] == []


def test_red_ios_block_after_noisy_mac_block():
    r = testcmd.xcsift_summary(out(NOISY_MAC, IOS_RED), 1)
    assert triple(r) == (8367, 1, 0)
    assert r["names"] == ["SnapshotTests testHome"]
    assert r["reasons"] == {"SnapshotTests testHome": ("snapshot differs", 12)}
    assert r["sites"] == [("/src/Tests/SnapshotTests.swift", 12, "SnapshotTests testHome: snapshot differs")]
    assert r["errors"] == []


def test_block_that_counted_nothing_keeps_its_build_error():
    r = testcmd.xcsift_summary(out(MAC, IOS_BUILD), 0)
    assert triple(r) == (8284, 1, 0)
    assert r["errors"] == [BUILD_ERR] and r["error"] == BUILD_ERR


def test_counted_block_keeps_an_error_with_a_line():
    r = testcmd.xcsift_summary(out(NOISY_MAC, FEEL_CRASH), 1)
    assert r["errors"] == [CRASH_ERR] and r["error"] == CRASH_ERR
    assert triple(r) == (8338, 1, 0)


def test_counted_block_with_a_kept_error_and_status_failed_is_red_on_exit_0():
    r = testcmd.xcsift_summary(dump(FEEL_CRASH).splitlines(), 0)
    assert triple(r) == (3, 1, 0) and r["errors"] == [CRASH_ERR]


def test_red_exit_without_failed_tests_is_one_failure():
    r = testcmd.xcsift_summary(out(MAC, IOS), 65)
    assert triple(r) == (8317, 1, 0)


def test_same_failure_on_both_platforms():
    r = testcmd.xcsift_summary(out(IOS_RED, IOS_RED), 1)
    assert triple(r) == (64, 2, 0)
    assert r["names"] == ["SnapshotTests testHome"] and len(r["sites"]) == 1


def test_failed_entries_are_not_blocks():
    r = testcmd.xcsift_summary(dump(IOS_RED).splitlines(), 1)
    assert triple(r) == (32, 1, 0)


def test_many_blocks_all_count():
    t0 = time.monotonic()
    r = testcmd.xcsift_summary(out(*[IOS] * 300), 0)
    assert r["passed"] == 9900
    assert time.monotonic() - t0 < 2.0


def test_parse_output_sums_blocks():
    r = testcmd.parse_output("\n".join(out(MAC, IOS)), 0)
    assert triple(r) == (8317, 0, 0) and r["format"] == "xcsift"


def test_run_tests_full_sums_blocks(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": "cat out.txt"}), encoding="utf-8")
    (tmp_path / "out.txt").write_text("\n".join(out(NOISY_MAC, IOS)) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env, timeout=120)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert (s["passed"], s["failed"], s["failures"]) == (8368, 0, [])

