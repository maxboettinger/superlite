"""#597: run_tests --fast names, non-test paths, 127 and no-match stops, failing names in the summary line."""
import json
import subprocess
import sys
from pathlib import Path

from test_run_tests_swift_only_testing import PBXPROJ

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

OK = "echo 'Executed 1 test, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"
XCODE_CFG = {"language": "swift", "test": f"echo FULL > .superlite/got.txt; {OK}",
             "test_file": f"printf '%s\\n' {{only_testing}} > .superlite/got.txt; {OK}"}
SWIFT = {
    "AppTests/ParserTests.swift": "import XCTest\nfinal class ParserTests: XCTestCase {\n    func testA() {}\n}\n",
    "AppTests/FooTests.swift": "import XCTest\nfinal class FooTests: XCTestCase {\n    func testA() {}\n}\n",
}
JS_CFG = {"language": "javascript", "test": "echo '1 passed'",
          "test_file": "printf '%s\\n' {files} > .superlite/got.txt; echo '1 passed'"}


def repo(tmp_path, cfg, files=None, xcode=False):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    if xcode:
        (tmp_path / "App.xcodeproj").mkdir()
        (tmp_path / "App.xcodeproj" / "project.pbxproj").write_text(PBXPROJ, encoding="utf-8")
    for rel, text in (files or {}).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def rt(cwd, *args, root=None):
    sl = Path(root or cwd) / ".superlite"
    return subprocess.run([sys.executable, str(RUN_TESTS), *args, "--log", str(sl / "incidents.jsonl"), "--ledger", str(sl / "ledger.md"),
                           "--summary", str(sl / "test-summary.json")], cwd=cwd, capture_output=True, text=True, timeout=120)


def summary(root):
    return json.loads((Path(root) / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def got(root):
    return (Path(root) / ".superlite" / "got.txt").read_text(encoding="utf-8").splitlines()


def test_unknown_suite_name_refused(tmp_path):
    root = repo(tmp_path, XCODE_CFG, SWIFT, xcode=True)
    r = rt(root, "--fast", "Nope")
    assert r.returncode == 2, r.stderr
    assert "test name not found: Nope" in r.stderr
    assert not (root / ".superlite" / "got.txt").exists()
    log = root / ".superlite" / "incidents.jsonl"
    assert not log.exists() or not log.read_text(encoding="utf-8").strip()


def test_known_suite_name_runs_target_suite(tmp_path):
    root = repo(tmp_path, XCODE_CFG, SWIFT, xcode=True)
    r = rt(root, "--fast", "ParserTests")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["-only-testing:AppTests/ParserTests"]


def test_exit_127_is_could_not_run(tmp_path):
    root = repo(tmp_path, {"language": "unknown", "test": "nosuchtool-xyz"})
    r = rt(root, "--full")
    assert r.returncode == 2, r.stderr
    assert "test command could not run (exit 127" in r.stderr
    assert "test command could not run (exit 127" in summary(root)["error"]


def test_red_no_match_is_no_tests_ran(tmp_path):
    root = repo(tmp_path, {"language": "unknown", "test": "echo 'No matching test cases were run'; exit 1"})
    r = rt(root, "--full")
    assert r.returncode == 1, r.stderr
    assert summary(root)["error"].startswith("no tests ran")


def test_yml_path_skipped_with_note(tmp_path):
    root = repo(tmp_path, JS_CFG, {"tests/a.test.ts": "x\n", ".github/workflows/ci.yml": "on: push\n"})
    r = rt(root, "--fast", "tests/a.test.ts", ".github/workflows/ci.yml")
    assert r.returncode == 0, r.stderr
    assert "run_tests: --fast skips non-test paths: .github/workflows/ci.yml" in r.stderr
    assert got(root) == ["tests/a.test.ts"]


def test_only_non_test_paths_refused(tmp_path):
    root = repo(tmp_path, JS_CFG, {"a.yml": "x: 1\n", "b.md": "# b\n"})
    r = rt(root, "--fast", "a.yml", "b.md")
    assert r.returncode == 2
    assert "no test paths left: --fast named only non-test files (a.yml, b.md)" in r.stderr
    assert not (root / ".superlite" / "got.txt").exists()


def test_background_parent_refuses_non_test_only(tmp_path):
    root = repo(tmp_path, JS_CFG, {"a.yml": "x: 1\n"})
    r = rt(root, "--fast", "a.yml", "--background")
    assert r.returncode == 2
    assert "summary:" not in r.stdout
    assert "no test paths left" in r.stderr
    assert not list((root / ".superlite").glob("*.latest"))


def test_background_parent_refuses_unknown_name(tmp_path):
    root = repo(tmp_path, XCODE_CFG, SWIFT, xcode=True)
    r = rt(root, "--fast", "Nope", "--background")
    assert r.returncode == 2
    assert "summary:" not in r.stdout
    assert "run_tests: test name not found: Nope" in r.stderr


def test_fast_from_package_dir_resolves_once(tmp_path):
    root = repo(tmp_path, JS_CFG, {"packages/app/test/a.test.ts": "x\n"})
    for arg in ("packages/app/test/a.test.ts", "test/a.test.ts"):
        (root / ".superlite" / "got.txt").unlink(missing_ok=True)
        r = rt(root / "packages" / "app", "--fast", arg, root=root)
        assert r.returncode == 0, r.stderr
        assert got(root) == ["packages/app/test/a.test.ts"]


def test_summary_line_names_failing_tests():
    data = {"mode": "fast", "passed": 3, "failed": 2, "failures": ["tests/a.py::test_x: assert 1 == 2", "-::ParserTests/parses(): failed"]}
    assert run_tests.summary_line(data) == "tests (fast): 3 passed, 2 failed; failing: tests/a.py::test_x, ParserTests/parses()"


def test_summary_line_caps_at_three_names():
    data = {"mode": "fast", "passed": 0, "failed": 5, "failures": [f"{c}: boom" for c in "abcde"]}
    assert run_tests.summary_line(data) == "tests (fast): 0 passed, 5 failed; failing: a, b, c (+2 more)"


def test_summary_line_unchanged_without_failures():
    assert run_tests.summary_line({"passed": 3, "failed": 1, "skipped": 2, "mode": "fast"}) == "tests (fast): 3 passed, 1 failed, 2 skipped"
    assert run_tests.summary_line({"passed": 3, "failed": 1, "mode": "fast", "error": "x", "failures": ["a: b"]}) == "tests (fast): 3 passed, 1 failed; error: x"


def test_summary_line_cuts_long_names():
    line = run_tests.summary_line({"mode": "fast", "passed": 0, "failed": 1, "failures": ["n" * 100 + ": boom"]})
    assert line == "tests (fast): 0 passed, 1 failed; failing: " + "n" * 60


BASH_CFG = {"language": "bash", "test": "echo '1 passed'",
            "test_file": "printf '%s\\n' {files} > .superlite/got.txt; echo '2 passed'"}
RED_XC = {"status": "failed", "summary": {"failed_tests": 1, "passed_tests": 1, "errors": 0, "warnings": 0, "linker_errors": 0, "test_time": "0.003s"},
          "failed_tests": [{"message": "XCTAssertEqual failed: (\"1\") is not equal to (\"2\")", "file": "/src/Tests/ArchitectureTests/PipelineConfigTests.swift",
                            "duration": 0.002, "line": 42, "test": "ArchitectureTests.PipelineConfigTests testB"}]}
GREEN_XC = {"summary": {"warnings": 0, "errors": 0, "linker_errors": 0, "test_time": "0.003s", "passed_tests": 2, "failed_tests": 0}, "status": "success"}


def xc_dump(obj):
    return json.dumps(obj, indent=2, separators=(",", " : "))


def test_split_fast_examples(tmp_path):
    assert run_tests.split_fast("tests/a.py tests/b.py,tests/c.py") == ["tests/a.py", "tests/b.py", "tests/c.py"]
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "my a.py").write_text("", encoding="utf-8")
    assert run_tests.split_fast("tests/my a.py", str(tmp_path)) == ["tests/my a.py"]


def test_is_pytest_command_examples():
    assert run_tests.is_pytest_command("python -m pytest tests/a.py -q") is True
    assert run_tests.is_pytest_command("bash run.sh x.py") is False


def test_uncollectable_paths_examples(tmp_path, monkeypatch):
    for rel in ("tests/test_a.py", "tools/tests/a_test.sh"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    monkeypatch.chdir(tmp_path)
    assert run_tests.uncollectable_paths(["tests", "tests/test_a.py::test_x", "tools/tests/a_test.sh", "pkg/..."]) == ["tools/tests/a_test.sh"]


def test_space_list_from_subfolder(tmp_path):
    root = repo(tmp_path, BASH_CFG, {"tests/a.py": "", "tests/b.py": ""})
    r = rt(root / "tests", "--fast", "a.py b.py", root=root)
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/a.py", "tests/b.py"]


def test_quoted_list_never_one_argument(tmp_path):
    root = repo(tmp_path, BASH_CFG, {"tests/a.py": "", "tests/b.py": ""})
    r = rt(root, "--fast", "tests/a.py tests/b.py")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/a.py", "tests/b.py"]


def test_missing_py_with_pytest_test_file_is_usage_error(tmp_path):
    root = repo(tmp_path, {**BASH_CFG, "test_file": "python -m pytest {files} -q"})
    r = rt(root, "--fast", "tests/gone.py")
    assert r.returncode == 2
    assert "test path not found: tests/gone.py" in r.stderr


def test_missing_py_with_other_command_still_runs(tmp_path):
    root = repo(tmp_path, {**BASH_CFG, "test_file": "echo '1 passed' {files}"})
    r = rt(root, "--fast", "tests/gone.py")
    assert r.returncode == 0, r.stderr


SH_FILES = {"conftest.py": "", "tools/tests/a_test.sh": "echo hi\n"}


def test_builtin_runner_refuses_sh_test(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel, text in SH_FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    r = rt(tmp_path, "--fast", "tools/tests/a_test.sh")
    assert r.returncode == 2
    assert "tools/tests/a_test.sh" in r.stderr and "**Tests:** cmd=" in r.stderr


def test_builtin_refusal_has_no_incident(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel, text in SH_FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    r = rt(tmp_path, "--fast", "tools/tests/a_test.sh")
    assert r.returncode == 2
    inc = tmp_path / ".superlite" / "incidents.jsonl"
    assert "no-result" not in (inc.read_text(encoding="utf-8") if inc.exists() else "")
    assert not list((tmp_path / ".superlite").glob("no-result-*.log"))


def test_background_parent_refuses_sh_test(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel, text in SH_FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    r = rt(tmp_path, "--fast", "tools/tests/a_test.sh", "--background")
    assert r.returncode == 2
    assert "summary:" not in r.stdout
    assert not list((tmp_path / ".superlite").glob("*.latest"))


def test_xcsift_swift_red_run_places_failure(tmp_path):
    site = tmp_path / "Tests" / "ArchitectureTests" / "PipelineConfigTests.swift"
    site.parent.mkdir(parents=True)
    site.write_text("import XCTest\n", encoding="utf-8")
    red = {**RED_XC, "failed_tests": [{**RED_XC["failed_tests"][0], "file": str(site)}]}
    root = repo(tmp_path, {"language": "swift", "test": "cat .superlite/red.json; exit 1"})
    (root / ".superlite" / "red.json").write_text(xc_dump(red), encoding="utf-8")
    r = rt(root, "--full")
    assert r.returncode == 1, r.stdout + r.stderr
    sm = summary(root)
    rel = "Tests/ArchitectureTests/PipelineConfigTests.swift"
    assert any(f.startswith(rel + "::") and "XCTAssertEqual failed" in f for f in sm["failures"]), sm["failures"]
    assert rel in sm["files"]


def test_xcsift_swift_green_run_passes(tmp_path):
    root = repo(tmp_path, {"language": "swift", "test": "cat .superlite/green.json"})
    (root / ".superlite" / "green.json").write_text(xc_dump(GREEN_XC), encoding="utf-8")
    r = rt(root, "--full")
    assert r.returncode == 0, r.stdout + r.stderr
    assert summary(root)["passed"] == 2


def test_xcsift_build_error_red_run_lists_it_once(tmp_path):
    obj = {"status": "failed", "errors": [{"file": "/src/App/Foo.swift", "message": "cannot find 'bar' in scope", "line": 10}],
           "summary": {"linker_errors": 0, "failed_tests": 0, "passed_tests": 1, "errors": 1, "warnings": 0}}
    root = repo(tmp_path, {"language": "swift", "test": "cat .superlite/red.json; exit 1"})
    (root / ".superlite" / "red.json").write_text(xc_dump(obj), encoding="utf-8")
    rt(root, "--full")
    sm = summary(root)
    assert len([f for f in sm["failures"] if "build error:" in f]) == 1, sm["failures"]


def test_xcsift_site_resolves_through_symlinked_tree(tmp_path):
    real = tmp_path / "real"
    (real / "Tests").mkdir(parents=True)
    site = real / "Tests" / "ATests.swift"
    site.write_text("import XCTest\n", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(real)
    red = {**RED_XC, "failed_tests": [{**RED_XC["failed_tests"][0], "file": str(site)}]}
    proj = tmp_path / "proj"
    proj.mkdir()
    root = repo(proj, {"language": "swift", "test": "cat red.json; exit 1"})
    (real / "red.json").write_text(xc_dump(red), encoding="utf-8")
    import os
    import types
    sl = root / ".superlite"
    class Args(types.SimpleNamespace):
        def __getattr__(self, name):
            return None

    a = Args(summary=str(sl / "test-summary.json"), log=str(sl / "incidents.jsonl"), ledger=str(sl / "ledger.md"), passthrough=None, limit=None, cli_env=None)
    old = Path.cwd()
    os.chdir(root)
    try:
        run_tests.run_other(a, {"command": "cat red.json; exit 1", "junit": None, "setup": None, "language": "swift"}, [], "full", cwd=str(link))
    finally:
        os.chdir(old)
    sm = json.loads((sl / "test-summary.json").read_text(encoding="utf-8"))
    assert "Tests/ATests.swift" in sm["files"], sm
