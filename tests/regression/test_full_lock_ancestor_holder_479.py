"""#479 F-T1-4: a nested full run whose env lost SUPERLITE_FULL_SUITE_LOCK must not wait on a lock its own ancestor holds."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock and ps are POSIX only")

PARENT = r'''
import fcntl, json, os, subprocess, sys, time
p, script, proj = sys.argv[1:4]
os.makedirs(os.path.dirname(p), exist_ok=True)
fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
os.write(fd, json.dumps({"pid": os.getpid(), "root": "/outer", "task": None, "started": time.time()}).encode())
env = {k: v for k, v in os.environ.items() if k != "SUPERLITE_FULL_SUITE_LOCK"}
t0 = time.time()
r = subprocess.run([sys.executable, script, "--full", "--lock-wait", "20"], cwd=proj, env=env, capture_output=True, text=True)
print(json.dumps({"rc": r.returncode, "err": r.stderr, "secs": time.time() - t0}))
'''


def test_nested_full_run_skips_lock_held_by_ancestor(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(
        {"language": "bash", "test": "echo 'Executed 1 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'"}), encoding="utf-8")
    home = tmp_path / "home"
    env = {**os.environ, "SUPERLITE_HOME": str(home)}
    env.pop("SUPERLITE_FULL_SUITE_LOCK", None)
    out = subprocess.run([sys.executable, "-c", PARENT, str(home / "locks" / "full-suite-shell.lock"), str(SCRIPTS / "run_tests.py"), str(proj)],
                         env=env, capture_output=True, text=True, timeout=60)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["secs"] < 15, res
    assert res["rc"] == 0, res
    assert "full-suite lock" not in res["err"], res


def test_is_ancestor():
    assert run_tests.is_ancestor(os.getppid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert run_tests.is_ancestor(child.pid) is False
