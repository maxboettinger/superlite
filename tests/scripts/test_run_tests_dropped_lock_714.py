"""#714: a --fast run whose paths are dropped runs the whole command, so it takes the full-run gate."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402
from _fixtures import DISK_FREE  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

RUN_TESTS = Path(run_tests.__file__)
NOTE = "--fast paths not passed, .superlite/test-cmd.json has no {files}"
SEEN = 'printf "%s" "${SUPERLITE_FULL_SUITE_LOCK:-none}" > lock.txt\n'
HOLDER = r'''
import fcntl, json, os, sys, time
p = sys.argv[1]
os.makedirs(os.path.dirname(p), exist_ok=True)
fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
os.write(fd, json.dumps({"pid": os.getpid(), "root": "/elsewhere", "task": None, "started": time.time() - 60}).encode())
print("held", flush=True)
time.sleep(60)
'''


def run(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(DISK_FREE, SUPERLITE_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--log", str(sl / "incidents.jsonl"), "--ledger", str(sl / "ledger.md"),
                         "--summary", str(sl / "test-summary.json"), *map(str, args)],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def project(tmp_path, cfg):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "shell", **cfg}), encoding="utf-8")
    (tmp_path / "all.sh").write_text(SEEN + 'echo "3 passed"\n', encoding="utf-8")
    (tmp_path / "run.sh").write_text(SEEN + 'echo "$# passed"\n', encoding="utf-8")
    (tmp_path / "a.sh").write_text("exit 0\n", encoding="utf-8")


def hold(tmp_path):
    lock = tmp_path / "home" / "locks" / "full-suite-shell.lock"
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(lock)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def stop(proc):
    proc.kill()
    proc.wait(timeout=10)
    proc.stdout.close()


def held_run(tmp_path, *args):
    proc = hold(tmp_path)
    try:
        return run(tmp_path, *args)
    finally:
        stop(proc)


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def seen(tmp_path):
    return (tmp_path / "lock.txt").read_text(encoding="utf-8")


def test_dropped_fast_run_holds_the_full_suite_lock(tmp_path):
    project(tmp_path, {"test": "bash all.sh"})
    cp = run(tmp_path, "--fast", "a.sh")
    assert cp.returncode == 0, cp.both
    assert seen(tmp_path).isdigit(), cp.both
    data = summary(tmp_path)
    assert data["mode"] == "fast"
    assert data["passed"] == 3
    assert data["paths_dropped"] == NOTE


def test_dropped_fast_run_waits_for_a_held_lock(tmp_path):
    project(tmp_path, {"test": "bash all.sh"})
    cp = held_run(tmp_path, "--fast", "a.sh", "--lock-wait", "1")
    assert cp.returncode == 2, cp.both
    assert "waiting for the shell full-suite lock" in cp.stderr
    assert "full-suite lock: still held" in cp.stderr
    assert not (tmp_path / "lock.txt").exists()
    data = summary(tmp_path)
    assert data["mode"] == "fast"
    assert data["paths_dropped"] == NOTE
    assert data["error"].startswith("full-suite lock: still held")


def test_dropped_fast_run_with_lock_false_runs_beside_a_holder(tmp_path):
    project(tmp_path, {"test": "bash all.sh", "lock": False})
    cp = held_run(tmp_path, "--fast", "a.sh", "--lock-wait", "1")
    assert cp.returncode == 0, cp.both
    assert 'no full-suite lock: test-cmd.json sets "lock": false' in cp.stderr
    assert "waiting for" not in cp.stderr
    assert seen(tmp_path) == "none"
    assert summary(tmp_path)["passed"] == 3


def test_fast_run_that_passes_its_paths_takes_no_lock(tmp_path):
    project(tmp_path, {"test": "bash all.sh", "test_file": "bash run.sh {files}"})
    cp = held_run(tmp_path, "--fast", "a.sh", "--lock-wait", "1")
    assert cp.returncode == 0, cp.both
    assert "waiting for" not in cp.stderr
    assert seen(tmp_path) == "none"
    assert summary(tmp_path)["passed"] == 1


def test_dropped_run_narrowed_by_passthrough_takes_no_lock(tmp_path):
    project(tmp_path, {"test": "bash all.sh"})
    cp = held_run(tmp_path, "--fast", "a.sh", "--lock-wait", "1", "--", "extra")
    assert cp.returncode == 0, cp.both
    assert "waiting for" not in cp.stderr
    assert seen(tmp_path) == "none"
    assert summary(tmp_path)["paths_dropped"] == NOTE
