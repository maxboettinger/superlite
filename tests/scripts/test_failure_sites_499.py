"""failure_sites: xcodebuild failure lines -> (file, line, context) sites (#499)."""
from __future__ import annotations

import shutil
import sys

import pytest

from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import failure_sites  # noqa: E402

FIX = FIXTURES / "xcode"
S = "Tests/KitTests/SpokenTextTests.swift"
SERIAL = {
    (S, 7, "SpokenTextTests/hugeLineIsLinear(): Expectation failed: one() == 2"),
    (S, 10, 'SpokenTextTests/"display name here": Expectation failed: one() == 3'),
    (S, 11, "SpokenTextTests/param(x:): Expectation failed: x == 1"),
    (S, 14, "freeFails(): Expectation failed: one() == 5"),
    ("Tests/KitTests/Nested.swift", 6, "Outer/Inner/deep(): Expectation failed: one() == 9"),
    ("Tests/OtherTests/OtherTests.swift", 12, "OtherSwiftTests/bad(): Caught error: CancellationError()"),
    ("Tests/OtherTests/OtherTests.swift", 7, 'LegacyTests/testBad: XCTAssertEqual failed: ("1") is not equal to ("2")'),
}
NAMES = ["bad()", "hugeLineIsLinear()", "freeFails()", '"display name here"', "param(x:) with 2 test cases", "deep()", "LegacyTests.testBad"]


def _text(name):
    return (FIX / name).read_text(encoding="utf-8")


@pytest.fixture
def kit(tmp_path):
    root = tmp_path / "kit"
    shutil.copytree(FIX / "kit", root)
    return str(root)


def test_serial_sites(kit):
    assert set(failure_sites.failures(_text("swift_serial_failures.txt"), kit, [], [])) == SERIAL


def test_names_matched_not_doubled(kit):
    got = failure_sites.failures(_text("swift_serial_failures.txt"), kit, [], NAMES)
    assert len(got) == 7 and set(got) == SERIAL


def test_parallel_sites(kit):
    got = failure_sites.failures(_text("swift_parallel.txt"), kit, [], [])
    assert len(got) == 7
    assert {
        (S, 5, "SpokenTextTests/hugeLineIsLinear(): failed"),
        ("Tests/KitTests/Nested.swift", 6, "Outer/Inner/deep(): failed"),
        (S, 14, "freeFails(): failed"),
        ("Tests/OtherTests/OtherTests.swift", 7, "LegacyTests/testBad(): failed"),
    } <= set(got)


def test_crash_site_from_failing_block(kit):
    assert failure_sites.failures(_text("swift_crash.txt"), kit, [], ["b2() (crashed)"]) == [
        ("Tests/KitTests/CrashTests.swift", 6, "CrashTests/b2(): crashed")]


def test_known_issues_not_failures(kit):
    assert failure_sites.failures(_text("swift_known_issues.txt"), kit, [], []) == []


def test_fast_path_wins_basename(tmp_path):
    for d in "AB":
        f = tmp_path / d / "SpokenTextTests.swift"
        f.parent.mkdir()
        shutil.copy(FIX / "kit/Tests/KitTests/SpokenTextTests.swift", f)
    got = failure_sites.failures(_text("swift_serial_failures.txt"), str(tmp_path), ["B/SpokenTextTests.swift"], [])
    spoken = [g for g in got if "SpokenTextTests" in g[2] or g[2].startswith("freeFails")]
    assert spoken and all(g[0] == "B/SpokenTextTests.swift" for g in spoken)


def test_unplaced_site(tmp_path):
    got = failure_sites.failures(_text("swift_serial_failures.txt"), str(tmp_path), [], [])
    assert len(got) == 7 and all(g[0] == "-" and g[1] == 0 for g in got)
    assert ("-", 0, "hugeLineIsLinear(): Expectation failed: one() == 2") in got


def test_ansi_and_zero_width(tmp_path):
    t = "\x1b[31m​✘ Test lost() recorded an issue at Gone.swift:3:1: boom\x1b[0m"
    assert failure_sites.failures(t, str(tmp_path), [], []) == [("-", 0, "lost(): boom")]


def test_name_without_site():
    assert failure_sites.failures("✘ Test lost() failed after 0.1 seconds with 1 issue.", "/nonexistent", [], ["lost()"]) == [("-", 0, "lost(): failed")]


def test_no_xcode_lines():
    assert failure_sites.failures("no xcode lines here", "/r", [], []) == []


def _suite_file(root, d, suite):
    f = root / d / f"{suite}.swift"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"struct {suite} {{\n    @Test func test() {{}}\n}}\n", encoding="utf-8")


def test_no_failure_lines_do_not_walk(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("walked")
    monkeypatch.setattr(failure_sites.os, "walk", boom)
    for t in ("ok 3 passed", _text("swift_known_issues.txt")):
        assert failure_sites.failures(t, str(tmp_path), [], []) == []


def test_scan_skips_testcmd_no_scan(tmp_path):
    _suite_file(tmp_path, "Carthage/Checkouts", "Lone")
    t = "✘ Test test() recorded an issue at Lone.swift:2:1: boom"
    assert failure_sites.failures(t, str(tmp_path), [], []) == [("-", 0, "test(): boom")]


def test_same_name_in_two_suites_kept(tmp_path):
    _suite_file(tmp_path, "A", "SuiteA")
    _suite_file(tmp_path, "B", "SuiteB")
    t = "Test case 'SuiteA/test()' failed on 'x' (0.1 seconds)\nTest case 'SuiteB/test()' failed on 'x' (0.1 seconds)"
    got = failure_sites.failures(t, str(tmp_path), [], [])
    assert got == [("A/SuiteA.swift", 2, "SuiteA/test(): failed"), ("B/SuiteB.swift", 2, "SuiteB/test(): failed")]


def test_first_issue_per_test(tmp_path):
    _suite_file(tmp_path, "A", "SuiteA")
    t = ("✘ Test test() recorded an issue at SuiteA.swift:2:1: one\n"
         "✘ Test test() recorded an issue at SuiteA.swift:2:1: two")
    assert failure_sites.failures(t, str(tmp_path), [], []) == [("A/SuiteA.swift", 2, "SuiteA/test(): one")]


def test_vitest_name_kept():
    got = failure_sites.failures(" FAIL  a.test.ts > one\n Tests  1 failed", "/", [], ["a.test.ts > one"])
    assert got == [("-", 0, "a.test.ts > one: failed")]


def test_non_xcode_names_never_walk(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("walked")
    monkeypatch.setattr(failure_sites.os, "walk", boom)
    got = failure_sites.failures("--- FAIL: TestX (0.00s)", "/r", [], ["TestX", "pkg.TestY"])
    assert got == [("-", 0, "TestX: failed"), ("-", 0, "pkg.TestY: failed")]
