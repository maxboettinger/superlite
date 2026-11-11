"""run_tests --task Tn runs the `cmd=` in the task's **Tests:** field instead of the project runner (#475)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)
PLAN = """# Plan

### T1 hook script
**Owns:** tests/hooks/test.sh
**Tests:** fast cmd=bash tests/hooks/test.sh

### T2 plain
**Owns:** tests/test_ok.py
**Tests:** fast
"""


def run(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def project(tmp_path, script="exit 0\n", marker=True):
    if marker:
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "tests" / "hooks").mkdir(parents=True)
    (tmp_path / "tests" / "hooks" / "test.sh").write_text(script, encoding="utf-8")
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    return tmp_path


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def go(tmp_path, *args, task="T1"):
    return run(tmp_path, "--task", task, "--plan", tmp_path / "plan.md", *args)


def test_cmd_runs_instead_of_pytest(tmp_path):
    project(tmp_path)
    cp = go(tmp_path)
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert s["passed"] == 1 and s["failed"] == 0 and s["mode"] == "fast" and s["task"] == "T1"
    last = (tmp_path / ".superlite" / "ledger.md").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert last.startswith("- tests fast passed=1 failed=0")


def test_cmd_red_exit_is_one_failure(tmp_path):
    project(tmp_path, "exit 3\n")
    cp = go(tmp_path)
    assert cp.returncode == 1, cp.both
    s = summary(tmp_path)
    assert s["failed"] == 1
    assert any("exit code 3 from `bash tests/hooks/test.sh`" in json.dumps(f) for f in s["failures"])


def test_cmd_count_wins(tmp_path):
    project(tmp_path, "echo '4 passed'\n")
    cp = go(tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 4


def test_full_flag_still_fast(tmp_path):
    project(tmp_path)
    cp = go(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["mode"] == "fast"
    assert "unit layer stamped" not in cp.stderr


def test_fast_paths_not_passed(tmp_path):
    project(tmp_path)
    cp = go(tmp_path, "--fast", "tests/hooks/test.sh")
    assert cp.returncode == 0, cp.both
    assert "not passed to T1" in cp.stderr


def test_task_without_cmd_unchanged(tmp_path):
    project(tmp_path)
    cp = go(tmp_path, "--fast", "tests/test_ok.py", task="T2")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_no_plan_unchanged(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--task", "T9", "--fast", "tests/test_ok.py")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_no_project_command_still_runs_cmd(tmp_path):
    project(tmp_path, marker=False)
    cp = go(tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_marker_with_shell_cmd_is_usage_error(tmp_path):
    project(tmp_path)
    cp = go(tmp_path, "-m", "x")
    assert cp.returncode == 2, cp.both
    assert "is not pytest" in cp.stderr
