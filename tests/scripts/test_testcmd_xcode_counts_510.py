"""testcmd.parse_output on real xcodebuild captures: crashes, skips, parallel testing, known issues, zero-width spaces (#510)."""
from __future__ import annotations

import sys
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

FIX = FIXTURES / "xcode"


def parse(name, rc):
    return testcmd.parse_output((FIX / name).read_text(encoding="utf-8"), rc)


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def test_crash_relaunch_counts():
    r = parse("swift_crash.txt", 65)
    assert (r["passed"], r["failed"], r["skipped"]) == (6, 1, 1)
    assert r["names"] == ["b2() (crashed)"] and r["counted"] is True


def test_skip_counts():
    assert triple(parse("swift_skip.txt", 0)) == (4, 0, 1)


def test_parallel_counts():
    r = parse("swift_parallel.txt", 65)
    assert triple(r) == (5, 7, 0)
    assert r["names"] == ["LegacyTests.testBad()", "freeFails()", "SpokenTextTests/named()", "Outer/Inner/deep()",
                          "SpokenTextTests/hugeLineIsLinear()", "SpokenTextTests/param(x:)", "OtherSwiftTests/bad()"]


def test_serial_failures_counts():
    r = parse("swift_serial_failures.txt", 65)
    assert triple(r) == (5, 7, 0)
    assert "param(x:)" in r["names"] and "param(x:) with 2 test cases" not in r["names"]


def test_known_issues_counts():
    assert triple(parse("swift_known_issues.txt", 0)) == (433, 0, 0)


def test_zero_width_failed_line():
    t = "​✘ Test a() failed after 0.1 seconds with 1 issue.\n✘ Test run with 2 tests in 1 suite failed after 0.1 seconds with 1 issue."
    r = testcmd.parse_output(t, 1)
    assert triple(r) == (1, 1, 0) and r["names"] == ["a()"]


def test_no_run_total_counts_the_passed_lines():
    t = "✔ Test a() passed after 0.1 seconds.\n✔ Test b() passed after 0.1 seconds.\n✘ Test c() failed after 0.1 seconds with 1 issue."
    assert triple(testcmd.parse_output(t, 1)) == (2, 1, 0)
    assert triple(testcmd.parse_output(t.split("\n✘")[0], 0)) == (2, 0, 0)


def test_xctest_failure_is_no_build_error():
    assert parse("swift_serial_failures.txt", 65)["error"] == ""
    err = "Foo.swift:3:5: error: cannot find 'Date' in scope"
    assert testcmd.parse_output(err + "\n** TEST FAILED **", 65)["error"] == err
