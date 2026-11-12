"""#597: test names and paths resolve to test ids; no widening, shell-safe {names}, non-test paths dropped."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

PKG = '''// swift-tools-version:5.9
import PackageDescription
let package = Package(name: "App", targets: [
    .target(name: "App"),
    .testTarget(name: "AppTests", dependencies: ["App"], path: "AppTests"),
])
'''
PARSER = "import XCTest\nstruct ParserTests {\n    @Test func testA() {}\n}\n"
LEXER = "import XCTest\nstruct LexerTests {\n    @Test func testB() {}\n}\n"


def swift_project(tmp_path, template="swift test --filter {names}", **extra):
    (tmp_path / "Package.swift").write_text(PKG, encoding="utf-8")
    (tmp_path / "AppTests").mkdir()
    (tmp_path / "AppTests" / "ParserTests.swift").write_text(PARSER, encoding="utf-8")
    (tmp_path / "AppTests" / "LexerTests.swift").write_text(LEXER, encoding="utf-8")
    (tmp_path / "AppTests" / "Helpers.swift").write_text("func helper() {}\n", encoding="utf-8")
    (tmp_path / "Sources" / "App").mkdir(parents=True)
    (tmp_path / "Sources" / "App" / "Model.swift").write_text("struct Model {}\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "swift", "test": "swift test", "test_file": template, **extra}), encoding="utf-8")
    return tmp_path


def test_is_non_test():
    assert testcmd.is_non_test(".github/workflows/ci.yml") is True
    assert testcmd.is_non_test("docs/x.md") is True
    assert testcmd.is_non_test("Docs/X.MD") is True
    assert testcmd.is_non_test("tests/test_a.py") is False
    assert testcmd.is_non_test("FooTests") is False


def test_verify_paths_drops_workflow_yml():
    assert testcmd.verify_paths([".github/workflows/ci.yml", "src/a.sh"]) == ["src/a.sh"]


def test_unknown_test_name_message():
    e = testcmd.UnknownTestName(["Nope", "Gone"])
    assert isinstance(e, ValueError)
    assert str(e) == "test name not found: Nope, Gone (no Swift test target declares that suite)"
    assert e.names == ["Nope", "Gone"]


def test_name_ids(tmp_path):
    swift_project(tmp_path)
    assert testcmd.name_ids(tmp_path, ["ParserTests"]) == ["AppTests/ParserTests"]
    assert testcmd.name_ids(tmp_path, ["ParserTests/testA", "AppTests/ParserTests"]) == ["AppTests/ParserTests/testA", "AppTests/ParserTests"]
    with pytest.raises(testcmd.UnknownTestName) as e:
        testcmd.name_ids(tmp_path, ["Nope"])
    assert e.value.names == ["Nope"]


def test_suite_in_comment_is_no_suite(tmp_path):
    swift_project(tmp_path)
    (tmp_path / "AppTests" / "Other.swift").write_text("// struct GhostTests { @Test func g() {} }\n/* class MoreGhostTests: XCTestCase {} */\n", encoding="utf-8")
    idx = testcmd.suite_index(tmp_path)
    assert idx["ParserTests"] == ["AppTests"]
    assert "GhostTests" not in idx and "MoreGhostTests" not in idx


def test_swift_names(tmp_path):
    swift_project(tmp_path)
    assert testcmd.swift_names(tmp_path, ["AppTests/ParserTests.swift"]) == ["ParserTests"]
    assert testcmd.swift_names(tmp_path, ["AppTests/Helpers.swift"]) == ["AppTests"]
    assert testcmd.swift_names(tmp_path, ["Sources/App/Model.swift"]) is None
    assert testcmd.swift_names(tmp_path, ["ParserTests", "AppTests/ParserTests"]) == ["ParserTests", "AppTests.ParserTests"]


def test_names_filter_is_shell_quoted(tmp_path):
    swift_project(tmp_path)
    r = testcmd.resolve(tmp_path, ["AppTests/ParserTests.swift", "AppTests/LexerTests.swift"])
    assert r["command"] == "swift test --filter 'ParserTests|LexerTests'"
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "go", "test": "go test ./...", "test_file": "go test -run '{names}'"}), encoding="utf-8")
    r = testcmd.resolve(tmp_path, ["a/FooTests.swift", "a/BarTests.swift"])
    assert r["command"] == "go test -run 'FooTests|BarTests'"


def test_unknown_name_is_not_widened(tmp_path):
    swift_project(tmp_path, template="xcodebuild test {only_testing}")
    with pytest.raises(testcmd.UnknownTestName):
        testcmd.resolve(tmp_path, ["Nope"])


def test_only_testing_name_maps_to_target_suite(tmp_path):
    swift_project(tmp_path, template="xcodebuild test {only_testing}")
    r = testcmd.resolve(tmp_path, ["ParserTests"])
    assert r["command"] == "xcodebuild test -only-testing:AppTests/ParserTests"


def test_names_outside_test_target_run_unfiltered(tmp_path):
    swift_project(tmp_path)
    notes: list = []
    r = testcmd.resolve(tmp_path, ["Sources/App/Model.swift"], notes)
    assert r["command"] == "swift test"
    assert "Sources/App/Model.swift is not in a test target; running the unfiltered test command" in notes


def test_testcmd_cli_unknown_name_exit_2(tmp_path):
    swift_project(tmp_path, template="xcodebuild test {only_testing}")
    cp = subprocess.run([sys.executable, str(SCRIPTS / "testcmd.py"), "--root", str(tmp_path), "--fast", "Nope"], capture_output=True, text=True)
    assert cp.returncode == 2
    assert "test name not found: Nope" in cp.stderr


def test_swift_test_no_match_line_is_empty():
    r = testcmd.parse_output("Test Suite 'Selected tests' started\nerror: No matching test cases were run\n", 1)
    assert r["empty"] == "error: No matching test cases were run"


def test_names_slot_inside_quoted_pattern_is_not_requoted(tmp_path):
    swift_project(tmp_path)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "go", "test": "go test ./...", "test_file": "go test -run '^({names})$'"}), encoding="utf-8")
    r = testcmd.resolve(tmp_path, ["a/FooTests.swift", "a/BarTests.swift"])
    assert r["command"] == "go test -run '^(FooTests|BarTests)$'"
