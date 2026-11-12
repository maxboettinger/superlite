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
