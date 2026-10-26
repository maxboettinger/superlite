"""run_tests is language-agnostic: test-cmd.json, marker detection, JUnit and exit-code fallbacks, no command."""
from __future__ import annotations

import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, run

RUN_TESTS = SCRIPTS / "run_tests.py"
TESTCMD = SCRIPTS / "testcmd.py"

VITEST_JUNIT = """<?xml version="1.0" encoding="UTF-8" ?>
<testsuites name="vitest tests" tests="3" failures="1" errors="0" time="0.5">
  <testsuite name="tests/slug.test.ts" tests="2" failures="0" errors="0" skipped="0" time="0.1">
    <testcase classname="tests/slug.test.ts" name="slugify &gt; lowercases" time="0.01"></testcase>
    <testcase classname="tests/slug.test.ts" name="slugify &gt; strips marks" time="0.01"></testcase>
  </testsuite>
  <testsuite name="tests/feed.test.ts" tests="1" failures="1" errors="0" skipped="0" time="0.1">
    <testcase classname="tests/feed.test.ts" name="feed &gt; builds rss" time="0.02">
      <failure message="expected 1 to be 2" type="AssertionError">AssertionError: expected 1 to be 2</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

RUNNER = """import shutil, sys
sys.stdout.write("running\\n")
shutil.copy("sample-junit.xml", sys.argv[1])
sys.exit(1)
"""

GO_RUNNER = """import sys
print("=== RUN   TestSlug")
print("--- FAIL: TestSlug (0.00s)")
print("    slug_test.go:12: got a want b")
print("FAIL")
print("FAIL\\texample.com/m\\t0.003s")
sys.exit(1)
"""


def config(tmp_path, **kw):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / "test-cmd.json").write_text(json.dumps(kw), encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def resolved(tmp_path, *fast):
    cp = run(TESTCMD, "--root", tmp_path, *(["--fast", *fast] if fast else []))
    assert cp.returncode == 0, cp.both
    return json.loads(cp.out)


def rt(tmp_path, *args):
    return run(RUN_TESTS, *args, cwd=tmp_path)


def test_marker_detection_table(tmp_path):
    def case(name, files):
        d = tmp_path / name
        d.mkdir()
        for fn, body in files.items():
            (d / fn).write_text(body, encoding="utf-8")
        return resolved(d)

    vi = case("vitest", {"package.json": json.dumps({"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1", "typescript": "^5"}})})
    assert vi["language"] == "typescript" and "--reporter=junit" in vi["command"] and "{junit}" in vi["command"] and vi["junit"] == "{junit}"
    jest = case("jest", {"package.json": json.dumps({"scripts": {"test": "jest"}, "devDependencies": {"jest": "^29", "jest-junit": "^16"}})})
    assert "jest-junit" in jest["command"] and jest["env"]["JEST_JUNIT_OUTPUT_FILE"] == "{junit}"
    plain = case("plainnode", {"package.json": json.dumps({"scripts": {"test": "node --test"}})})
    assert plain["command"] == "npm test" and plain["junit"] == "" and plain["language"] == "javascript"
    assert case("gomod", {"go.mod": "module m\n"})["command"] == "go test ./..."
    assert case("cargo", {"Cargo.toml": "[package]\n"})["command"] == "cargo test"
    assert case("dotnet", {"App.csproj": "<Project/>"})["command"] == "dotnet test"
    py = case("py", {"pyproject.toml": "[project]\n"})
    assert py["python"] is True and py["command"] is None


def test_fast_uses_test_file_and_full_uses_test(tmp_path):
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    assert resolved(tmp_path)["command"] == "go test ./..."
    assert resolved(tmp_path, "./slug", "./feed")["command"] == "go test ./slug ./feed"
    config(tmp_path, language="rust", test="make check", test_file="make check ARGS={files}", junit="", setup="")
    assert resolved(tmp_path)["command"] == "make check"
    assert resolved(tmp_path, "a", "b")["command"] == "make check ARGS=a b"
    assert resolved(tmp_path)["source"] == "test-cmd.json"  # wins over marker files


def test_no_test_command_exits_2_with_a_clear_summary(tmp_path):
    cp = rt(tmp_path, "--full")
    assert cp.returncode == 2 and cp.out.strip() == "0 0 0 0.0" and "no test command found" in cp.err
    s = summary(tmp_path)
    assert set(s) == {"passed", "failed", "skipped", "seconds", "mode", "failures", "skipped_tests"}
    assert s["failed"] == 1 and "no test command found" in s["failures"][0]


def test_junit_from_a_node_runner_keeps_the_summary_shape(tmp_path):
    (tmp_path / "sample-junit.xml").write_text(VITEST_JUNIT, encoding="utf-8")
    (tmp_path / "runner.py").write_text(RUNNER, encoding="utf-8")
    config(tmp_path, language="typescript", test=f"{sys.executable} runner.py {{junit}}", test_file=f"{sys.executable} runner.py {{junit}}",
           junit="{junit}", setup="")
    cp = rt(tmp_path, "--full")
    assert cp.returncode == 1, cp.both
    assert cp.out.strip().split()[:3] == ["2", "1", "0"]
    s = summary(tmp_path)
    assert set(s) == {"passed", "failed", "skipped", "seconds", "mode", "failures", "skipped_tests"}
    assert (s["passed"], s["failed"], s["mode"]) == (2, 1, "full")
    assert s["failures"] == ["tests/feed.test.ts::feed > builds rss: expected 1 to be 2"]
    inc = (tmp_path / ".superlite" / "incidents.jsonl").read_text(encoding="utf-8")
    assert "feed.test.ts" in inc and "verified" in inc  # failing test incident, and the passing file verified


def test_exit_code_fallback_for_a_runner_without_junit(tmp_path):
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    (tmp_path / "runner.py").write_text(GO_RUNNER, encoding="utf-8")
    config(tmp_path, language="go", test=f"{sys.executable} runner.py", test_file=f"{sys.executable} runner.py {{files}}", junit="", setup="")
    cp = rt(tmp_path, "--fast", "./slug")
    assert cp.returncode == 1, cp.both
    s = summary(tmp_path)
    assert s["mode"] == "fast" and s["failed"] >= 1 and s["failures"] == ["-::TestSlug: failed"]
    log = (tmp_path / ".superlite" / "test-output.log").read_text(encoding="utf-8")
    assert "--- FAIL: TestSlug" in log


def test_exit_code_zero_without_junit_is_green(tmp_path):
    config(tmp_path, language="rust", test=f'{sys.executable} -c "print(1)"', test_file="", junit="", setup="")
    cp = rt(tmp_path)
    assert cp.returncode == 0 and summary(tmp_path)["failed"] == 0 and summary(tmp_path)["passed"] >= 1


def test_non_python_project_never_asks_for_pytest(tmp_path):
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    config(tmp_path, language="go", test=f'{sys.executable} -c "print(1)"', test_file="", junit="", setup="")
    code = ("import sys; sys.path.insert(0, %r); import _pyrun\n"
            "def boom(*a, **k): raise AssertionError('pytest was asked for')\n"
            "_pyrun.pytest_cmd = boom\n"
            "import run_tests; sys.exit(run_tests.main(['--full']))\n") % str(SCRIPTS)
    cp = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "pytest" not in cp.stdout + cp.stderr


def test_background_and_wait_work_for_a_non_python_runner(tmp_path):
    config(tmp_path, language="go", test=f'{sys.executable} -c "print(1)"', test_file="", junit="", setup="")
    cp = rt(tmp_path, "--background")
    assert cp.returncode == 0 and cp.out.startswith("summary:")
    w = rt(tmp_path, "--wait", "--timeout", "60")
    assert w.returncode == 0, w.both
    assert json.loads(w.out)["failed"] == 0


def test_setup_runs_once(tmp_path):
    config(tmp_path, language="go", test=f'{sys.executable} -c "print(1)"', test_file="",
           junit="", setup=f'{sys.executable} -c "open(\'setup.ran\', \'a\').write(\'x\')"')
    rt(tmp_path)
    rt(tmp_path)
    assert (tmp_path / "setup.ran").read_text(encoding="utf-8") == "x"


def test_python_project_still_uses_pytest(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "test_a.py").write_text("def test_a():\n    assert 1 == 1\n", encoding="utf-8")
    cp = rt(tmp_path, "--full")
    assert cp.returncode == 0 and cp.out.strip().startswith("1 0 0"), cp.both


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def _repo_with_worktree(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "go.mod").write_text("module m\n", encoding="utf-8")
    _git(main, "add", "go.mod")
    _git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "side")
    return main, wt


SWIFT_DICT = {"language": "swift", "test": "swift test --xunit-output {junit}",
              "test_file": "swift test --xunit-output {junit} --filter {names}", "junit": "{junit}", "setup": ""}


def test_swift_package_detected(tmp_path):
    (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9\n", encoding="utf-8")
    sys.path.insert(0, str(SCRIPTS))
    import testcmd
    assert testcmd.detect(tmp_path) == SWIFT_DICT
    r = resolved(tmp_path)
    assert r["language"] == "swift" and r["command"] == "swift test --xunit-output {junit}" and r["junit"] == "{junit}"


def test_names_placeholder_builds_filter(tmp_path):
    (tmp_path / "Package.swift").write_text("// x\n", encoding="utf-8")
    assert resolved(tmp_path, "Tests/A/FooTests.swift")["command"] == "swift test --xunit-output {junit} --filter FooTests"
    sys.path.insert(0, str(SCRIPTS))
    import testcmd
    assert testcmd.names_filter(["Tests/PixKitTests/NotificationModelTests.swift", "Tests/X/PushPayloadTests.swift"]) == "NotificationModelTests|PushPayloadTests"


def test_worktree_falls_back_to_main_checkout_config(tmp_path):
    main, wt = _repo_with_worktree(tmp_path)
    config(main, language="x", test="echo x")
    r = resolved(wt)
    assert r["source"] == "test-cmd.json" and r["command"] == "echo x"


def test_main_checkout_without_config_is_none(tmp_path):
    main, wt = _repo_with_worktree(tmp_path)
    sys.path.insert(0, str(SCRIPTS))
    import testcmd
    assert testcmd.main_checkout_config(main) is None
    assert testcmd.main_checkout_config(wt) is None
    assert testcmd.main_checkout_config(tmp_path / "nowhere") is None
    assert resolved(wt)["source"] == "markers" and resolved(wt)["command"] == "go test ./..."
