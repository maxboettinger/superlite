"""run_tests --wait on an earlier run of a task takes the task's newest run (#507)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_plan_tools import run  # noqa: E402
from test_run_tests_limit_489 import RUN_TESTS, data_path, project  # noqa: E402

COUNT = "sh -c 'n=$(cat n 2>/dev/null || echo 0); n=$((n+1)); echo $n > n; echo \"$n passed\"'"


def bg(tmp_path, *extra):
    r = run(RUN_TESTS, "--full", "--background", *extra, cwd=tmp_path)
    assert r.returncode == 0, r.both
    path = data_path(r.out)
    w = run(RUN_TESTS, "--wait", path, "--timeout", "60", cwd=tmp_path)
    assert w.returncode == 0, w.both
    return path


def test_wait_earlier_run_takes_newest(tmp_path):
    project(tmp_path, COUNT)
    first = bg(tmp_path, "--task", "T1")
    time.sleep(1.1)
    bg(tmp_path, "--task", "T1")
    w = run(RUN_TESTS, "--wait", first, "--timeout", "60", cwd=tmp_path)
    assert json.loads(w.out)["passed"] == 2
    assert "is an earlier run of T1; waiting on its newest run" in w.err


def test_wait_other_task_unchanged(tmp_path):
    project(tmp_path, COUNT)
    a = bg(tmp_path, "--task", "T1")
    time.sleep(1.1)
    bg(tmp_path, "--task", "T2")
    w = run(RUN_TESTS, "--wait", a, "--timeout", "60", cwd=tmp_path)
    assert json.loads(w.out)["passed"] == 1
    assert "earlier run" not in w.err


def test_wait_without_task_unchanged(tmp_path):
    project(tmp_path, COUNT)
    a = bg(tmp_path)
    time.sleep(1.1)
    bg(tmp_path)
    w = run(RUN_TESTS, "--wait", a, "--timeout", "60", cwd=tmp_path)
    assert json.loads(w.out)["passed"] == 1
    assert "earlier run" not in w.err
