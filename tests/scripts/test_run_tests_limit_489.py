"""run_tests --limit kills a hung test command tree, SIGTERM cleans up, --task summaries carry the task (#489)."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests  # noqa: E402
from test_plan_tools import run  # noqa: E402

HANG = "sh -c 'sleep 60 & echo $! > child.pid; sleep 60'"


def project(tmp_path, cmd=None):
    (tmp_path / ".superlite").mkdir()
    if cmd is not None:
        (tmp_path / ".superlite" / "test-cmd.json").write_text(
            json.dumps({"language": "go", "isolate": False, "test": cmd, "test_file": cmd}), encoding="utf-8")
    return tmp_path


def pid_dead(p):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        try:
            os.kill(p, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_limit_kills_command_tree(tmp_path):
    project(tmp_path, HANG)
    t0 = time.monotonic()
    r = run(RUN_TESTS, "--full", "--limit", "2", cwd=tmp_path)
    assert time.monotonic() - t0 < 30
    assert r.returncode == 2
    assert summary(tmp_path)["error"].startswith("wall-clock limit: test run killed after 2 s")
    assert pid_dead(int((tmp_path / "child.pid").read_text().strip()))
    lines = (tmp_path / ".superlite" / "incidents.jsonl").read_text(encoding="utf-8")
    assert "no-result" in lines


def test_limit_pytest_path(tmp_path):
    project(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_slow.py").write_text("import time\n\ndef test_slow():\n    time.sleep(60)\n", encoding="utf-8")
    r = run(RUN_TESTS, "--fast", "tests/test_slow.py", "--limit", "3", cwd=tmp_path)
    assert r.returncode == 2
    assert summary(tmp_path)["error"].startswith("wall-clock limit")


def test_limit_zero_is_none(tmp_path):
    project(tmp_path, "sh -c 'sleep 1; echo \"1 passed\"'")
    r = run(RUN_TESTS, "--full", "--limit", "0", cwd=tmp_path)
    assert r.returncode == 0
    assert summary(tmp_path)["passed"] == 1


def test_default_limit():
    assert run_tests.DEFAULT_LIMIT == 3600.0
    r = run(RUN_TESTS, "--help")
    assert "--limit" in r.out


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
def test_sigterm_kills_test_processes(tmp_path):
    project(tmp_path, HANG)
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    p = subprocess.Popen([sys.executable, str(RUN_TESTS), "--full"], cwd=tmp_path, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        pidfile = tmp_path / "child.pid"
        end = time.monotonic() + 15
        while time.monotonic() < end and not (pidfile.exists() and pidfile.read_text().strip()):
            time.sleep(0.1)
        child = int(pidfile.read_text().strip())
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=15)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 2
    assert pid_dead(child)
    assert summary(tmp_path)["error"] == "run_tests stopped by SIGTERM; its test processes were killed"


def test_background_task_pointer_and_summary_task(tmp_path):
    project(tmp_path, 'echo "1 passed"')
    r = run(RUN_TESTS, "--full", "--task", "T1", "--background", cwd=tmp_path)
    assert r.returncode == 0, r.both
    wait = [ln for ln in r.out.splitlines() if ln.startswith("wait: ")][-1][len("wait: "):]
    w = subprocess.run(wait, shell=True, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert w.returncode == 0, w.stderr
    data = json.loads(w.stdout)
    assert data["task"] == "T1"
    ptr = tmp_path / ".superlite" / "test-summary-T1.latest"
    assert json.loads(ptr.read_text())["summary"] == data_path(r.out)
    assert run_tests.task_pointer_path(".superlite/test-summary.json", "T1") == Path(".superlite/test-summary-T1.latest")


def data_path(out):
    return [ln for ln in out.splitlines() if ln.startswith("summary: ")][0][len("summary: "):]
