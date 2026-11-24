"""run_tests --fast maps Swift test files to -only-testing:<Target>/<Suite> and skips other paths, never widening them to the whole suite (#398, #1119)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

PBXPROJ = (
    "// !$*UTF8*$!\n{\n\tobjects = {\n\n/* Begin PBXNativeTarget section */\n"
    "\t\tA1 /* App */ = {\n\t\t\tisa = PBXNativeTarget;\n\t\t\tbuildPhases = (\n\t\t\t\tB1 /* Sources */,\n\t\t\t);\n"
    "\t\t\tname = App;\n\t\t\tproductName = App;\n\t\t\tproductType = \"com.apple.product-type.application\";\n\t\t};\n"
    "\t\tA2 /* AppTests */ = {\n\t\t\tisa = PBXNativeTarget;\n\t\t\tbuildPhases = (\n\t\t\t\tB2 /* Sources */,\n\t\t\t);\n"
    "\t\t\tname = AppTests;\n\t\t\tproductName = AppTests;\n\t\t\tproductType = \"com.apple.product-type.bundle.unit-test\";\n\t\t};\n"
    "\t\tA3 /* App UITests */ = {\n\t\t\tisa = PBXNativeTarget;\n\t\t\tname = \"App UITests\";\n"
    "\t\t\tproductName = \"App UITests\";\n\t\t\tproductType = \"com.apple.product-type.bundle.ui-testing\";\n\t\t};\n"
    "/* End PBXNativeTarget section */\n\t};\n}\n")
FILES = {
    "App/Views/ContentView.swift": "import SwiftUI\nstruct ContentView: View {\n    var body: some View { Text(\"hi\") }\n}\n",
    "AppTests/FooTests.swift": "import XCTest\n@testable import App\nfinal class FooTests: XCTestCase {\n    func testA() {}\n}\n",
    "AppTests/FreeTests.swift": "import Testing\n@Test func adds() {}\n",
    "AppTests/Support/Helpers.swift": "import Foundation\nfunc makeFoo() -> Int { 1 }\n",
    "App UITests/LaunchTests.swift": "import XCTest\nfinal class LaunchTests: XCTestCase {\n    func testLaunch() {}\n}\n",
}
OK = "echo 'Executed 1 test, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"
CFG = {"language": "swift", "test": f"echo FULL > .superlite/got.txt; {OK}",
       "test_file": f"printf '%s\\n' {{only_testing}} > .superlite/got.txt; {OK}"}


def xcode_repo(tmp_path, cfg=CFG):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "App.xcodeproj" / "project.pbxproj").write_text(PBXPROJ, encoding="utf-8")
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    if cfg is not None:
        (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def got(root):
    return (root / ".superlite" / "got.txt").read_text(encoding="utf-8").splitlines()


def test_targets_from_pbxproj(tmp_path):
    assert run_tests.swift_test_targets(xcode_repo(tmp_path)) == {"AppTests", "App UITests"}


def test_targets_from_package_swift(tmp_path):
    (tmp_path / "Package.swift").write_text(
        'let package = Package(name: "Core", targets: [\n    .target(name: "Core"),\n'
        '    .testTarget(\n        name: "CoreTests", dependencies: ["Core"]),\n])\n', encoding="utf-8")
    assert run_tests.swift_test_targets(tmp_path) == {"CoreTests"}


def test_targets_nested_project(tmp_path):
    (tmp_path / "ios" / "App.xcodeproj").mkdir(parents=True)
    (tmp_path / "ios" / "App.xcodeproj" / "project.pbxproj").write_text(PBXPROJ, encoding="utf-8")
    assert run_tests.swift_test_targets(tmp_path) == {"AppTests", "App UITests"}


def test_targets_none(tmp_path):
    assert run_tests.swift_test_targets(tmp_path) == set()


@pytest.mark.parametrize("path,targets,want", [
    ("AppTests/FooTests.swift", {"AppTests"}, "AppTests"),
    ("AppTests/Support/Helpers.swift", {"AppTests"}, "AppTests"),
    ("App/Views/ContentView.swift", {"AppTests"}, None),
    ("Tests/CoreTests/BarTests.swift", {"AppTests"}, None),
    ("Tests/CoreTests/BarTests.swift", set(), "CoreTests"),
    ("AppTests/FooTests.swift", set(), "AppTests"),
    ("Sources/Core/Bar.swift", set(), None),
    ("Tests/BarTests.swift", set(), None),
    ("FooTests.swift", set(), None),
])
def test_owning_test_target(path, targets, want):
    assert run_tests.owning_test_target(path, targets) == want


def test_xcode_only_testing_suites(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["AppTests/FooTests.swift"]) == ("-only-testing:AppTests/FooTests", None)


def test_xcode_only_testing_free_function_is_quoted(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["AppTests/FreeTests.swift"]) == ("'-only-testing:AppTests/adds()'", None)


def test_xcode_only_testing_helper_runs_its_target(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["AppTests/Support/Helpers.swift"]) == ("-only-testing:AppTests", None)


def test_xcode_only_testing_target_with_space(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["App UITests/LaunchTests.swift"]) == (
        "'-only-testing:App UITests/LaunchTests'", None)


def test_xcode_only_testing_source_path_unmapped(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["AppTests/FooTests.swift", "App/Views/ContentView.swift"]) == (
        None, "App/Views/ContentView.swift")


def test_xcode_only_testing_dedupes(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, ["AppTests/FooTests.swift", "AppTests/FooTests.swift"]) == (
        "-only-testing:AppTests/FooTests", None)


def test_xcode_only_testing_absolute_path(tmp_path):
    root = xcode_repo(tmp_path)
    assert run_tests.xcode_only_testing(root, [str(root / "AppTests" / "FooTests.swift")]) == (
        "-only-testing:AppTests/FooTests", None)


def test_fast_spec_other_template_unchanged(tmp_path, monkeypatch):
    root = xcode_repo(tmp_path, cfg={"language": "swift", "test": "swift test", "test_file": "swift test --filter {names}"})
    monkeypatch.chdir(root)
    assert run_tests.fast_spec(["AppTests/FooTests.swift"])["command"] == "swift test --filter FooTests"


def test_fast_test_file_runs_target_suite(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", "AppTests/FooTests.swift")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests/FooTests"]
    assert "declares no test suite" not in r.stderr and "not in a test target" not in r.stderr


def test_fast_free_function_survives_the_shell(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", "AppTests/FreeTests.swift", "App UITests/LaunchTests.swift")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests/adds()", "-only-testing:App UITests/LaunchTests"]


SRC = "App/Views/ContentView.swift"
NOTE = f"run_tests: --fast {SRC} is in no test target, so it maps to no test filter; skipped, never widened to the whole suite (#1119)"
REFUSAL = f"--fast paths map to no test filter (in no test target): {SRC}; nothing to run: name a test file in a test target, or use --affected or --full (#1119)"


def test_fast_source_file_refused(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", SRC)
    assert r.returncode == 2, r.stderr
    assert f"run_tests: {REFUSAL}" in r.stderr
    assert not (root / ".superlite" / "got.txt").exists()
    summary = json.loads((root / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert summary["error"] == REFUSAL
    log = root / ".superlite" / "incidents.jsonl"
    assert not log.exists() or not log.read_text(encoding="utf-8").strip()


def test_fast_mixed_paths_runs_test_file_only(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", "AppTests/FooTests.swift", SRC)
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests/FooTests"]
    assert r.stderr.count(NOTE) == 1
    summary = json.loads((root / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert f"skipped --fast paths in no test target: {SRC} (#1119)" in summary["warning"]


def test_background_parent_refuses_unmapped(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", SRC, "--background")
    assert r.returncode == 2, r.stderr
    assert f"run_tests: {REFUSAL}" in r.stderr
    assert not (root / ".superlite" / "got.txt").exists()


def test_background_mixed_runs_child(tmp_path):
    root = xcode_repo(tmp_path)
    r = rt(root, "--fast", "AppTests/FooTests.swift", SRC, "--background")
    assert r.returncode == 0, r.stderr
    assert "no test filter" not in r.stderr and "declares no test suite" not in r.stderr
    w = rt(root, "--timeout", "60", "--wait")
    assert w.returncode == 0, w.stdout + w.stderr
    assert got(root) == ["-only-testing:AppTests/FooTests"]
    logs = list((root / ".superlite").glob("*.output.log")) + list((root / ".superlite").glob("*.log"))
    assert any(NOTE in x.read_text(encoding="utf-8", errors="replace") for x in logs)


def test_names_template_source_refused(tmp_path):
    cfg = {"language": "swift", "test": f"echo FULL > .superlite/got.txt; {OK}",
           "test_file": f"echo {{names}} > .superlite/got.txt; {OK}"}
    root = xcode_repo(tmp_path, cfg=cfg)
    r = rt(root, "--fast", SRC)
    assert r.returncode == 2, r.stderr
    assert not (root / ".superlite" / "got.txt").exists()


def test_targets_empty_name_is_skipped(tmp_path):
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "App.xcodeproj" / "project.pbxproj").write_text(
        "{\n\t\tA2 = {\n\t\t\tisa = PBXNativeTarget;\n\t\t\tname = \"\";\n"
        "\t\t\tproductType = \"com.apple.product-type.bundle.unit-test\";\n\t\t};\n}\n", encoding="utf-8")
    assert run_tests.swift_test_targets(tmp_path) == set()
