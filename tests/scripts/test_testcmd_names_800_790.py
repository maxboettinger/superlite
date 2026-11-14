"""#800 #790: a `Failed to ...` line is no failing test name; skipped Swift tests are named."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

SWIFT_X = "◇ Test run started.\n➜ Test x() skipped.\n✔ Test ok() passed after 0.001 seconds.\n✔ Test run with 2 tests passed after 0.002 seconds.\n"
SWIFT_XY = "◇ Test run started.\n➜ Test x() skipped.\n➜ Test y() skipped.\n✔ Test ok() passed after 0.001 seconds.\n✔ Test run with 3 tests passed after 0.002 seconds.\n"


def test_failed_to_line_is_no_name():
    r = testcmd.parse_output("Building...\n  Failed to connect to host\n", 1)
    assert r["names"] == []
    assert r["failed"] == 1


def test_dotnet_failed_dotted_name():
    assert testcmd.parse_output("  Failed MyTests.CalcTests.Add [12 ms]\n", 1)["names"] == ["MyTests.CalcTests.Add"]


def test_failed_path_and_colons():
    assert testcmd.parse_output("Failed tests/foo_test.sh\n", 1)["names"] == ["tests/foo_test.sh"]
    assert testcmd.parse_output("Failed pkg::mod::test_x\n", 1)["names"] == ["pkg::mod::test_x"]


def test_failed_word_with_dots_is_no_name():
    assert testcmd.parse_output("Failed loading...\n", 1)["names"] == []
    assert testcmd.parse_output("Failed to load a.b\n", 1)["names"] == []


def test_swift_testing_skipped_names():
    text = ("◇ Test run started.\n➜ Test gatedNetworkTest() skipped: \"needs network\"\n➜ Test anotherGate() skipped.\n"
            "✔ Test ok() passed after 0.001 seconds.\n✔ Test run with 3 tests passed after 0.002 seconds.\n")
    r = testcmd.parse_output(text, 0)
    assert r["skipped"] == 2
    assert r["skipped_names"] == ["gatedNetworkTest()", "anotherGate()"]
    assert r["passed"] == 1


def test_xctest_skipped_name():
    text = ("Test Case '-[AppTests.FooTests testGated]' skipped (0.001 seconds).\n"
            "Test Case '-[AppTests.FooTests testOk]' passed (0.001 seconds).\n"
            "Executed 2 tests, with 1 test skipped and 0 failures (0 unexpected) in 0.002 (0.003) seconds\n")
    r = testcmd.parse_output(text, 0)
    assert r["skipped"] == 1
    assert r["skipped_names"] == ["FooTests.testGated"]
    assert r["passed"] == 1


def test_other_branches_empty_skipped_names():
    assert testcmd.parse_output("3 passed\n", 0)["skipped_names"] == []
    assert testcmd.parse_output("1 passed, 1 skipped in 0.1s\n", 0)["skipped_names"] == []
    assert testcmd.parse_output("Test case 'A.t()' passed on 'Mac'\n", 0)["skipped_names"] == []


def test_merge_parsed_joins_skipped_names():
    merged = testcmd.merge_parsed([("a", testcmd.parse_output(SWIFT_X, 0)), ("b", testcmd.parse_output(SWIFT_XY, 0))])
    assert merged["skipped_names"] == ["x()", "y()"]
