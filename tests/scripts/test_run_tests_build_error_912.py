"""A build error leads the test result: red, with the error as the first failure, never a no-result stop (#912)."""
import json
import subprocess
import sys

from _fixtures import DISK_FREE
from test_plan_tools import SCRIPTS
from test_testcmd_counts_481 import BUILD_OBJ, ZERO_OBJ, dump

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import testcmd  # noqa: E402

ERR = "/src/App/Foo.swift:10: cannot find 'bar' in scope"


def _obj(errors):
    return {"status": "failed", "errors": errors, "summary": {"linker_errors": 0, "failed_tests": 0, "errors": len(errors), "warnings": 0}}


def _run(tmp_path, body, test="cat out.json; exit 1", raw=False):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": test}), encoding="utf-8")
    (tmp_path / "out.json").write_text(body if raw else dump(body), encoding="utf-8")
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    return cp, json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_xcsift_error_is_not_empty():
    r = testcmd.xcsift_summary(dump(BUILD_OBJ).splitlines(), 1)
    assert r["empty"] == "" and r["error"] == ERR and r["errors"] == [ERR] and r["counted"] is False and r["failed"] == 1


def test_xcsift_error_count_without_array():
    obj = {"status": "failed", "summary": {"errors": 2, "linker_errors": 1, "failed_tests": 0, "passed_tests": 0}}
    r = testcmd.xcsift_summary(dump(obj).splitlines(), 1)
    assert r["empty"] == "" and r["error"] == "xcsift summary: 2 errors, 1 linker errors"


def test_xcsift_zero_without_errors_stays_empty():
    r = testcmd.xcsift_summary(dump(ZERO_OBJ).splitlines(), 0)
    assert r["empty"] == "xcsift summary: 0 passed, 0 failed tests"


def test_build_error_run_is_red_not_no_result(tmp_path):
    cp, s = _run(tmp_path, BUILD_OBJ)
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert s["failed"] == 1 and "error" not in s
    assert s["failures"][0] == f"-::build error: {ERR}"
    inc = tmp_path / ".superlite" / "incidents.jsonl"
    assert not inc.exists() or "no-result" not in inc.read_text(encoding="utf-8")


def test_build_error_path_is_relative(tmp_path):
    f = tmp_path / "Tests" / "AppTests" / "FooTests.swift"
    f.parent.mkdir(parents=True)
    f.write_text("x\n", encoding="utf-8")
    cp, s = _run(tmp_path, _obj([{"file": str(f), "message": "missing arguments", "line": 44}]))
    assert s["failures"][0].endswith("build error: Tests/AppTests/FooTests.swift:44: missing arguments"), s["failures"]


def test_build_error_path_outside_run_folder_as_given(tmp_path):
    cp, s = _run(tmp_path, BUILD_OBJ)
    assert f"build error: {ERR}" in s["failures"][0]


def test_five_errors_list_three_and_the_rest(tmp_path):
    cp, s = _run(tmp_path, _obj([{"file": f"/x/F{i}.swift", "message": f"m{i}", "line": i} for i in range(1, 6)]))
    assert all("build error: " in f for f in s["failures"][:3])
    assert s["failures"][3] == "-::build error: (+2 more)"


def test_plain_error_line_beats_no_tests_line(tmp_path):
    cp, s = _run(tmp_path, "a.swift:3: error: x\nNo test files found\n", test="cat out.json; exit 1", raw=True)
    assert cp.returncode == 1
    assert s["failures"][0].startswith("-::build error:") and "no tests ran" not in s.get("error", "")


def test_empty_filter_still_no_tests_ran(tmp_path):
    cp, s = _run(tmp_path, ZERO_OBJ)
    assert s["error"].startswith("no tests ran:")


def test_summary_line_shows_the_build_error():
    d = {"mode": "fast", "passed": 0, "failed": 1, "failures": ["-::build error: Tests/A.swift:44: missing arguments"]}
    assert run_tests.summary_line(d) == "tests (fast): 0 passed, 1 failed; failing: build error: Tests/A.swift:44: missing arguments"


def test_summary_line_shows_the_assertion():
    d = {"mode": "fast", "passed": 0, "failed": 1, "failures": ["tests/test_a.py::test_x: assert 1 == 2"]}
    assert run_tests.summary_line(d) == "tests (fast): 0 passed, 1 failed; failing: tests/test_a.py::test_x: assert 1 == 2"


def test_wait_stdout_drops_files(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"passed": 1, "failed": 0, "skipped": 0, "mode": "fast", "files": {"a.py": [1, 0]}}), encoding="utf-8")
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--wait", str(p), "--timeout", "5"], cwd=tmp_path, capture_output=True, text=True)
    out = json.loads(cp.stdout)
    assert "files" not in out and out["summary"] == str(p.resolve())
    assert "files" in json.loads(p.read_text(encoding="utf-8"))
