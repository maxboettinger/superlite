"""run_tests names why a run had no result (#778) and finds a task's cmd= through --plan DIR (#793)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402
from _fixtures import DISK_FREE  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)


def run(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(DISK_FREE, SUPERLITE_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def config(tmp_path, command, **extra):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    spec = {"language": "shell", "test": command, "test_file": command, **extra}
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(spec), encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def no_result(tmp_path):
    f = tmp_path / ".superlite" / "incidents.jsonl"
    rows = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("kind") == "no-result"]


def test_no_result_target_kinds():
    assert run_tests.no_result_target("bash t.sh", 127, "/l.log", kind="command not found") == "command not found; exit 127 from `bash t.sh`; log /l.log"
    assert run_tests.no_result_target("pytest", 5, "", cause="no tests found in x") == "nothing collected: no tests found in x; exit 5 from `pytest`; log not written"
    assert run_tests.no_result_target("c", 0, "L") == "exit 0 from `c`; log L"


def test_target_names_command_not_found(tmp_path):
    config(tmp_path, "b211_no_such_cmd_xyz")
    cp = run(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    (inc,) = no_result(tmp_path)
    assert inc["target"].startswith("command not found; exit 127 from `")


def test_target_names_no_test_count(tmp_path):
    config(tmp_path, "echo hello")
    run(tmp_path, "--full")
    (inc,) = no_result(tmp_path)
    assert inc["target"].startswith("no test count; exit 0 from `")


def test_target_names_no_test_count_runner(tmp_path):
    config(tmp_path, 'echo "No test files found"')
    run(tmp_path, "--full")
    (inc,) = no_result(tmp_path)
    assert inc["target"].startswith("no test count (runner: No test files found); exit 0 from `")


def test_command_junit_flags():
    cj = run_tests.command_junit
    assert cj("bunx vitest run a --reporter=junit --outputFile.junit=out/j.xml") == "out/j.xml"
    assert cj("vitest run --outputFile=o.json") is None
    assert cj("pytest --junitxml r.xml") == "r.xml"
    assert cj("pytest --junit-xml=r.xml") == "r.xml"
    assert cj("vitest --reporter=junit --outputFile=o.xml") == "o.xml"
    assert cj("vitest --reporter junit --outputFile o.xml") == "o.xml"
    assert cj("echo hi") is None


def test_exit0_with_command_junit_counts(tmp_path):
    (tmp_path / "write.sh").write_text(
        'cat > rep.xml <<X\n<testsuite tests="2"><testcase classname="a" name="t1"/><testcase classname="a" name="t2"/></testsuite>\nX\n',
        encoding="utf-8")
    config(tmp_path, "sh write.sh --junitxml=rep.xml")
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 2
    assert not (tmp_path / ".superlite" / "incidents.jsonl").exists() or not no_result(tmp_path)


def test_root_relative_dir_equal_prefix(tmp_path):
    (tmp_path / "packages" / "x").mkdir(parents=True)
    assert run_tests.root_relative("packages/x", tmp_path / "packages" / "x", tmp_path) == "packages/x"


PLAN = """# Plan

### T1 a
**Owns:** some_test.py
**Tests:** fast cmd=echo 3 passed
"""


def test_task_plan_dir_runs_cmd(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "plan.md").write_text(PLAN, encoding="utf-8")
    (tmp_path / "some_test.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    cp = run(tmp_path, "--fast", "some_test.py", "--task", "T1", "--plan", ".superlite")
    assert "T1 runs its **Tests:** cmd: echo 3 passed" in cp.stderr, cp.both
    assert summary(tmp_path)["passed"] == 3
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert run_tests.task_plan(argparse.Namespace(plan=".superlite")) == (str(Path(".superlite") / "plan.md"), ".superlite")
        assert run_tests.task_plan(argparse.Namespace(plan=".superlite/plan.md"))[0] == ".superlite/plan.md"
        (tmp_path / "d").mkdir()
        (tmp_path / "p.md").write_text(PLAN, encoding="utf-8")
        (tmp_path / "d" / "stable.json").write_text(json.dumps({"plan": "p.md"}), encoding="utf-8")
        found, _ = run_tests.task_plan(argparse.Namespace(plan="d"))
        assert found and Path(found).name == "p.md"
        (tmp_path / ".superlite" / "plan.md").unlink()
        plan, tried = run_tests.task_plan(argparse.Namespace(plan=None))
        assert plan is None and tried
    finally:
        os.chdir(old)


def test_task_missing_plan_note(tmp_path):
    config(tmp_path, "echo 1 passed")
    cp = run(tmp_path, "--task", "T9", "--full")
    assert "run_tests: --task T9: no plan found (tried " in cp.stderr, cp.both
    assert "ran the project's test command, not a **Tests:** cmd=" in cp.stderr
    assert "no plan found" in summary(tmp_path).get("warning", "")


def test_task_not_in_plan_note(tmp_path):
    config(tmp_path, "echo 1 passed")
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    cp = run(tmp_path, "--task", "T9", "--plan", "plan.md", "--full")
    assert "run_tests: --task T9: not in plan.md; ran the project's test command, not a **Tests:** cmd=" in cp.stderr, cp.both
