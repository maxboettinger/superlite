"""run_tests --fast uses testcmd's one Swift mapping: a test target whose folder differs from its name runs filtered (#431)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import testcmd  # noqa: E402

PBX = ('// !$*UTF8*$!\n{ objects = {\n'
       'S1 = { isa = PBXFileSystemSynchronizedRootGroup; path = "Unit Tests"; sourceTree = "<group>"; };\n'
       'G0 = { isa = PBXGroup; children = ( S1 ); sourceTree = "<group>"; };\n'
       'A1 = { isa = PBXNativeTarget; name = AppTests; fileSystemSynchronizedGroups = ( S1 ); '
       'productType = "com.apple.product-type.bundle.unit-test"; };\n'
       'P0 = { isa = PBXProject; mainGroup = G0; };\n}; rootObject = P0; }\n')
OK = "echo 'Executed 1 test, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"
CFG = {"language": "swift", "test": f"echo FULL > .superlite/got.txt; {OK}",
       "test_file": f"printf '%s\\n' {{only_testing}} > .superlite/got.txt; {OK}"}


def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "App.xcodeproj" / "project.pbxproj").write_text(PBX, encoding="utf-8")
    (tmp_path / "Unit Tests").mkdir()
    (tmp_path / "Unit Tests" / "FooTests.swift").write_text(
        "import XCTest\nfinal class FooTests: XCTestCase {\n    func testA() {}\n}\n", encoding="utf-8")
    (tmp_path / "Unit Tests" / "Helpers.swift").write_text("func helper() -> Int { 1 }\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(CFG), encoding="utf-8")
    return tmp_path


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def got(root):
    return (root / ".superlite" / "got.txt").read_text(encoding="utf-8").splitlines()


def test_helpers_are_testcmds():
    assert run_tests.swift_test_targets is testcmd.swift_test_targets
    assert run_tests.owning_test_target is testcmd.owning_test_target
    assert run_tests.xcode_only_testing is testcmd.xcode_only_testing


def test_fast_folder_differs_from_target_runs_filtered(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--fast", "Unit Tests/FooTests.swift")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests/FooTests"]
    assert "not in a test target" not in r.stderr


def test_fast_helper_note_has_run_tests_prefix(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--fast", "Unit Tests/Helpers.swift")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests"]
    assert "run_tests: Unit Tests/Helpers.swift declares no test suite; using -only-testing:AppTests" in r.stderr
    assert "testcmd:" not in r.stderr


def test_fast_spec_quiet_prints_nothing(tmp_path, monkeypatch, capsys):
    root = repo(tmp_path)
    monkeypatch.chdir(root)
    spec = run_tests.fast_spec(["Unit Tests/Helpers.swift"], quiet=True)
    assert "-only-testing:AppTests" in spec["command"]
    assert capsys.readouterr().err == ""


def test_background_parent_prints_no_note(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--fast", "Unit Tests/Helpers.swift", "--background")
    assert r.returncode == 0, r.stderr
    assert "declares no test suite" not in r.stderr
    w = rt(root, "--timeout", "60", "--wait")
    assert w.returncode == 0, w.stdout + w.stderr
    assert got(root) == ["-only-testing:AppTests"]


def test_fast_spec_without_only_testing_calls_two_arg_resolve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sentinel = {"command": "fake", "python": True}
    monkeypatch.setattr(testcmd, "resolve", lambda root, paths=None: sentinel)
    assert run_tests.fast_spec(["src/b.py"]) == sentinel
