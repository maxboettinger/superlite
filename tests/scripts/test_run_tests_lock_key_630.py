"""#630: a test-cmd.json `"lock": false` full run takes no local full-suite lock."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import testcmd  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

RUN_TESTS = SCRIPTS / "run_tests.py"
TESTCMD = SCRIPTS / "testcmd.py"
PASS = "echo 'Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"
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


@pytest.fixture(autouse=True)
def _no_outer_lock(monkeypatch):
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)


def project(tmp_path, **extra):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": PASS, **extra}), encoding="utf-8")
    return tmp_path


def holding(tmp_path):
    spec = testcmd.resolve(tmp_path)
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(run_tests.full_lock_path(run_tests.lock_toolchain(spec)))],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def stop(proc):
    proc.kill()
    proc.wait(timeout=10)
    proc.stdout.close()


def go(tmp_path, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args)], cwd=tmp_path, capture_output=True, text=True, timeout=120)


def test_lock_enabled_values(capsys):
    assert testcmd.lock_enabled({"test": "x", "lock": False}) is False
    assert testcmd.lock_enabled({"test": "x"}) is True
    assert testcmd.lock_enabled(None) is True
    assert capsys.readouterr().err == ""
    assert testcmd.lock_enabled({"test": "x", "lock": "no"}) is True
    assert 'test-cmd.json "lock" must be true or false; ignored' in capsys.readouterr().err


def test_full_run_with_lock_false_skips_held_lock(tmp_path):
    project(tmp_path, lock=False)
    proc = holding(tmp_path)
    try:
        cp = go(tmp_path, "--full", "--lock-wait", "2")
    finally:
        stop(proc)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "no full-suite lock" in cp.stderr
    assert "waiting for" not in cp.stderr


def test_background_full_run_writes_no_lockwait(tmp_path):
    project(tmp_path, lock=False)
    proc = holding(tmp_path)
    try:
        cp = go(tmp_path, "--full", "--lock-wait", "2", "--background")
        assert cp.returncode == 0, cp.stdout + cp.stderr
        wait = [ln for ln in cp.stdout.splitlines() if ln.startswith("wait:")][-1][len("wait:"):].strip()
        w = subprocess.run(wait, shell=True, cwd=tmp_path, capture_output=True, text=True, timeout=120)
    finally:
        stop(proc)
    assert w.returncode == 0, w.stdout + w.stderr
    assert not list((tmp_path / ".superlite").glob("*.lockwait"))


def test_full_run_without_key_still_waits(tmp_path):
    project(tmp_path)
    proc = holding(tmp_path)
    try:
        cp = go(tmp_path, "--full", "--lock-wait", "1")
    finally:
        stop(proc)
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "full-suite lock: still held" in cp.stdout + cp.stderr


def test_fast_run_ignores_key(tmp_path):
    project(tmp_path, lock=False)
    cp = go(tmp_path, "--fast")
    assert "no full-suite lock" not in cp.stdout + cp.stderr


def test_user_entry_lock_false(tmp_path, monkeypatch):
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"swift": {"test": PASS, "lock": False}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(user))
    (tmp_path / "App.xcodeproj").mkdir()
    assert testcmd.resolve(tmp_path)["lock"] is False


def test_sl_testcmd_shows_lock(tmp_path):
    project(tmp_path, lock=False)
    cp = subprocess.run([sys.executable, str(TESTCMD), "--root", str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert json.loads(cp.stdout)["lock"] is False
