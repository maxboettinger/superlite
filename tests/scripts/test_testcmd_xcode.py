"""testcmd: Swift Testing and XCTest output, xcodebuild filter, isolate flag."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


def test_swift_testing_summary():
    r = testcmd.parse_output("✔ Test run with 12 tests in 3 suites passed after 0.5 seconds.", 0)
    assert (r["passed"], r["failed"]) == (12, 0)


def test_swift_testing_failure_names():
    t = ("✘ Test tagsSorted() failed after 0.1 seconds with 1 issue.\n"
         "✘ Test run with 5 tests in 1 suite failed after 0.2 seconds with 1 issue.")
    r = testcmd.parse_output(t, 1)
    assert (r["passed"], r["failed"], r["names"]) == (4, 1, ["tagsSorted()"])


def test_xctest_uses_last_executed_line():
    t = ("Test Case '-[KitTests.FooTests testBar]' failed (0.01 seconds).\n"
         "Executed 1 test, with 1 failure (0 unexpected) in 0.0 (0.0) seconds\n"
         "Executed 3 tests, with 1 failure (0 unexpected) in 0.1 (0.1) seconds")
    r = testcmd.parse_output(t, 65)
    assert (r["passed"], r["failed"], r["names"]) == (2, 1, ["FooTests.testBar"])


def test_xcodebuild_both_frameworks_summed():
    t = ("\x1b[32m✔ Test run with 4 tests in 1 suite passed after 0.1 seconds.\x1b[0m\n"
         "Executed 3 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds")
    r = testcmd.parse_output(t, 0)
    assert (r["passed"], r["failed"]) == (7, 0)


def test_only_testing_placeholder(tmp_path):
    p = "Packages/Kit/Tests/CoreTests/LibraryTests.swift"
    assert testcmd.only_testing([p]) == "-only-testing:CoreTests/LibraryTests"
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite/test-cmd.json").write_text(json.dumps(
        {"language": "swift", "test": "xcodebuild test -scheme X",
         "test_file": "xcodebuild test -scheme X {only_testing}"}))
    r = testcmd.resolve(tmp_path, [p])
    assert r["command"] == "xcodebuild test -scheme X -only-testing:CoreTests/LibraryTests"
    assert r["isolate"] is True


def test_isolate_defaults(tmp_path):
    (tmp_path / ".superlite").mkdir()
    cfg = tmp_path / ".superlite/test-cmd.json"
    for lang, want in [("swift", True), ("go", True), ("rust", True), ("csharp", True), ("python", False), ("javascript", False)]:
        cfg.write_text(json.dumps({"language": lang, "test": "x"}))
        assert testcmd.resolve(tmp_path)["isolate"] is want, lang
    cfg.write_text(json.dumps({"language": "swift", "test": "x", "isolate": False}))
    assert testcmd.resolve(tmp_path)["isolate"] is False


def test_missing_reason_xcode_hint(tmp_path):
    (tmp_path / "App.xcodeproj").mkdir()
    r = testcmd.missing_reason(tmp_path)
    assert "xcodebuild test -scheme" in r and "{only_testing}" in r
