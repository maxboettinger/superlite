"""#550: the full-suite lock is per toolchain, so a long python suite does not stall a shell or Xcode project."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

RUN_TESTS = SCRIPTS / "run_tests.py"
HOLDER = r'''
import fcntl, json, os, sys, time
p = sys.argv[1]
os.makedirs(os.path.dirname(p), exist_ok=True)
fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
os.write(fd, json.dumps({"pid": os.getpid(), "root": sys.argv[3], "task": None, "started": time.time() - 120}).encode())
print("held", flush=True)
time.sleep(float(sys.argv[2]))
'''


@pytest.fixture(autouse=True)
def _no_outer_lock(monkeypatch):
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)


def hold(toolchain, seconds, root="/elsewhere"):
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(run_tests.full_lock_path(toolchain)), str(seconds), root],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def stop(proc):
    proc.kill()
    proc.wait(timeout=10)
    proc.stdout.close()


def test_lock_toolchain():
    assert run_tests.lock_toolchain({"python": True}) == "python"
    assert run_tests.lock_toolchain({"python": False, "language": "swift", "command": "cd P && xcodebuild test -scheme X"}) == "xcode"
    assert run_tests.lock_toolchain({"python": False, "language": "shell", "command": "bash scripts/ci.sh lint"}) == "shell"
    assert run_tests.lock_toolchain({"python": False, "language": "Node.js", "command": "npm test"}) == "node-js"
    assert run_tests.lock_toolchain({"python": False, "command": "x"}) == "shell"


def test_lock_path_per_toolchain(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "h"))
    assert run_tests.full_lock_path("xcode") == tmp_path / "h" / "locks" / "full-suite-xcode.lock"


def shell_project(tmp_path):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(
        {"language": "bash", "test": "echo 'Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"}), encoding="utf-8")


def python_project(tmp_path):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")


def test_two_toolchains_do_not_wait(tmp_path, monkeypatch, capsys):
    shell_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold("python", 60)
    try:
        assert run_tests.main(["--full", "--lock-wait", "5"]) == 0
    finally:
        stop(proc)
    assert "waiting for" not in capsys.readouterr().err


def test_same_toolchain_waits_and_names_age(tmp_path, monkeypatch, capsys):
    python_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold("python", 30)
    try:
        assert run_tests.main(["--full", "--lock-wait", "1"]) == 2
    finally:
        stop(proc)
    err = capsys.readouterr().err
    assert f"waiting for the python full-suite lock (held by pid {proc.pid} in /elsewhere" in err
    assert "2 min ago" in err
    assert "full-suite lock: still held by" in err


def note(tmp_path, content):
    mine = tmp_path / ".superlite" / "test-summary-r1.json"
    mine.parent.mkdir(exist_ok=True)
    mine.write_text("", encoding="utf-8")  # no summary yet: --wait times out and names the lock
    mine.with_suffix(".lockwait").write_text(json.dumps(content), encoding="utf-8")
    return mine


def wait_err(tmp_path, mine):
    return run(RUN_TESTS, "--wait", str(mine), "--timeout", "1", cwd=tmp_path)


def test_wait_names_live_holder(tmp_path):
    proc = hold("python", 60)
    try:
        mine = note(tmp_path, {"lock": str(run_tests.full_lock_path("python")), "holder": {"pid": 1}})
        w = wait_err(tmp_path, mine)
    finally:
        stop(proc)
    assert f"held by pid {proc.pid}" in w.err, w.err
    assert "python full-suite lock" in w.err


def test_old_note_still_read(tmp_path):
    mine = note(tmp_path, {"pid": 4242, "root": "/x", "task": None, "started": time.time()})
    w = wait_err(tmp_path, mine)
    assert "held by pid 4242" in w.err, w.err


def test_expect_from_last_full_run(tmp_path):
    root = tmp_path / "other"
    (root / ".superlite").mkdir(parents=True)
    (root / ".superlite" / "test-summary-full.json").write_text(json.dumps({"seconds": 600}), encoding="utf-8")
    assert "its last full run took 10 min" in run_tests.wait_detail({"pid": 5, "root": str(root), "task": None, "started": time.time()})
