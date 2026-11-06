"""testcmd: xcodebuild -only-testing from declared suites, real xcodebuild output counts."""
from __future__ import annotations

import json
import sys

from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

FIX = FIXTURES / "xcode"
MIXED = "final class AlphaTests: XCTestCase {\n  func testA() {}\n}\nclass BetaTests: XCTestCase {\n  func testB() {}\n}\n"
MODERN = "@Suite struct Parser {\n  @Test func a() {}\n}\nstruct Fixture { let x = 1 }\n@Test func free() {}\n"


def _write(root, rel, text):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    return rel


def test_swift_suites_examples():
    assert testcmd.swift_suites(MIXED) == ["AlphaTests", "BetaTests"]
    assert testcmd.swift_suites(MODERN) == ["Parser", "free()"]


def test_implicit_suite_and_extension():
    t = "struct Implicit {\n  @Test func b() {}\n}\nextension AlphaTests {\n  func testMore() {}\n}\n"
    assert testcmd.swift_suites(t) == ["Implicit", "AlphaTests"]


def test_attributes_and_modifiers():
    t = ("@MainActor\nfinal class UITests: XCTestCase {\n  func testX() {}\n}\n"
         "@Suite(\"Named\")\npublic struct S {\n  @Test func t() {}\n}\n")
    assert testcmd.swift_suites(t) == ["UITests", "S"]


def test_only_testing_two_xctest_suites_in_one_file(tmp_path):
    rel = _write(tmp_path, "Tests/KitTests/Mixed.swift", MIXED)
    assert testcmd.only_testing([rel], tmp_path) == "-only-testing:KitTests/AlphaTests -only-testing:KitTests/BetaTests"


def test_no_suite_falls_back_with_warning(tmp_path, capsys):
    rel = _write(tmp_path, "Tests/KitTests/Helpers.swift", "struct Fixture {}\n")
    assert testcmd.only_testing([rel], tmp_path) == "-only-testing:KitTests/Helpers"
    err = capsys.readouterr().err
    assert "Tests/KitTests/Helpers.swift" in err and "declares no test suite" in err


def test_missing_file_falls_back(tmp_path, capsys):
    out = testcmd.only_testing(["Tests/KitTests/Gone.swift"], tmp_path)
    assert out == "-only-testing:KitTests/Gone"
    assert "declares no test suite" in capsys.readouterr().err


def test_duplicates_across_files_once(tmp_path):
    a = _write(tmp_path, "Tests/KitTests/A.swift", "final class AlphaTests: XCTestCase {\n}\n")
    b = _write(tmp_path, "Tests/KitTests/B.swift", "extension AlphaTests {\n  func testMore() {}\n}\n")
    assert testcmd.only_testing([a, b], tmp_path) == "-only-testing:KitTests/AlphaTests"


def test_resolve_expands_suites(tmp_path):
    rel = _write(tmp_path, "Tests/KitTests/Mixed.swift", MIXED)
    _write(tmp_path, ".superlite/test-cmd.json", json.dumps(
        {"language": "swift", "test": "xcodebuild test -scheme X",
         "test_file": "xcodebuild test -scheme X {only_testing}"}))
    assert testcmd.resolve(tmp_path, [rel])["command"] == (
        "xcodebuild test -scheme X -only-testing:KitTests/AlphaTests -only-testing:KitTests/BetaTests")


def _real(name, rc):
    return testcmd.parse_output((FIX / name).read_text(), rc)


def test_parse_real_xctest_two_suites():
    r = _real("xctest_two_suites.txt", 65)
    assert (r["passed"], r["failed"]) == (4, 1)


def test_parse_real_swift_testing():
    r = _real("swift_testing.txt", 0)
    assert (r["passed"], r["failed"]) == (3, 0)


def test_parse_real_mixed_selection():
    r = _real("mixed_only_testing.txt", 65)
    assert (r["passed"], r["failed"]) == (7, 1)


def test_free_test_with_nested_paren_attribute_and_one_line_suite():
    t = "@Test(.tags(.fast)) func free() {}\nstruct One { @Test func a() {} }\nstruct Plain { let x = 1 }\n"
    assert testcmd.swift_suites(t) == ["free()", "One"]
