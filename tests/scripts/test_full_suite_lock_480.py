"""#480: full-suite runs take a machine-wide lock under ~/.superlite/locks, so full suites on one machine run one at a time."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

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
os.write(fd, json.dumps({"pid": os.getpid(), "root": "/elsewhere", "task": "T9", "started": time.time()}).encode())
print("held", flush=True)
time.sleep(float(sys.argv[2]))
'''
PROBE = r'''
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(1)
'''


@pytest.fixture(autouse=True)
def _no_outer_lock(monkeypatch):
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)  # a suite started by run_tests --full exports it


def hold(seconds):
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(run_tests.full_lock_path("python")), str(seconds)],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


def stop(proc):
    proc.kill()
    proc.wait(timeout=10)
    proc.stdout.close()


def is_free():
    return subprocess.run([sys.executable, "-c", PROBE, str(run_tests.full_lock_path("python"))]).returncode == 0


def args(tmp_path, lock_wait=30.0, task=None, run_id=None):
    return SimpleNamespace(lock_wait=lock_wait, task=task, run_id=run_id,
                           summary=str(tmp_path / ".superlite" / "test-summary.json"))


def project(tmp_path, test="def test_ok():\n    assert True\n"):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / "test_ok.py").write_text(test, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers =\n    quick: q\n", encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_lock_path_follows_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "h"))
    assert run_tests.full_lock_path("python") == tmp_path / "h" / "locks" / "full-suite-python.lock"


def test_holder_text():
    started = time.mktime((2026, 11, 11, 14, 3, 7, 0, 0, -1))
    assert run_tests.holder_text({"pid": 4242, "root": "/x/proj", "task": "T3", "started": started}) == "pid 4242 in /x/proj (task T3) since 14:03:07"
    assert run_tests.holder_text({"pid": 4242, "root": "/x/proj", "task": None, "started": started}) == "pid 4242 in /x/proj since 14:03:07"
    assert run_tests.holder_text(None) == "another run"


def test_lock_holder_reads_only_a_record(tmp_path):
    p = tmp_path / "l.lock"
    assert run_tests.lock_holder(p) is None
    for text in ("", "{half", "[1]", json.dumps({"pid": "7"})):
        p.write_text(text, encoding="utf-8")
        assert run_tests.lock_holder(p) is None, text
    p.write_text(json.dumps({"pid": 7, "root": "/r", "task": None, "started": 1.0}), encoding="utf-8")
    assert run_tests.lock_holder(p) == {"pid": 7, "root": "/r", "task": None, "started": 1.0}


def test_fast_label_takes_no_lock(tmp_path):
    with run_tests.full_suite_lock(args(tmp_path), "fast"):
        assert not run_tests.full_lock_path("python").exists()
        assert run_tests.LOCK_ENV not in os.environ


def test_full_label_holds_the_lock_and_records_the_holder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = run_tests.full_lock_path("python")
    with run_tests.full_suite_lock(args(tmp_path, task="T4"), "full"):
        assert not is_free()
        h = run_tests.lock_holder(p)
        assert (h["pid"], h["root"], h["task"]) == (os.getpid(), str(Path.cwd()), "T4")
        assert os.environ[run_tests.LOCK_ENV] == str(os.getpid())
        assert p.stat().st_mode & 0o777 == 0o600
        assert p.parent.stat().st_mode & 0o777 == 0o700
    assert is_free()
    assert run_tests.lock_holder(p) is None
    assert run_tests.LOCK_ENV not in os.environ


def test_waits_for_another_holder_then_takes_it(tmp_path, capsys):
    proc = hold(2)
    try:
        t0 = time.monotonic()
        with run_tests.full_suite_lock(args(tmp_path), "full"):
            waited = time.monotonic() - t0
            assert run_tests.lock_holder(run_tests.full_lock_path("python"))["pid"] == os.getpid()
    finally:
        stop(proc)
    assert waited >= 1.0
    err = capsys.readouterr().err
    assert f"run_tests: waiting for the python full-suite lock (held by pid {proc.pid} in /elsewhere (task T9) since " in err
    assert "); python full runs on one machine run one at a time" in err
    assert "run_tests: full-suite lock taken after " in err


def test_wait_limit_raises_lock_busy_and_clears_the_note(tmp_path):
    (tmp_path / ".superlite").mkdir()
    a = args(tmp_path, lock_wait=1.0, run_id="r1")
    proc = hold(30)
    try:
        with pytest.raises(run_tests.LockBusy) as e:
            with run_tests.full_suite_lock(a, "full"):
                pytest.fail("entered while another run holds the lock")
    finally:
        stop(proc)
    assert e.value.seconds == 1.0
    assert e.value.holder["pid"] == proc.pid
    assert not Path(a.summary).with_suffix(".lockwait").exists()


def test_nested_run_under_the_holder_skips_the_lock(tmp_path):
    with run_tests.full_suite_lock(args(tmp_path), "full"):
        t0 = time.monotonic()
        with run_tests.full_suite_lock(args(tmp_path, lock_wait=1.0), "full"):
            assert time.monotonic() - t0 < 0.5
        assert os.environ[run_tests.LOCK_ENV] == str(os.getpid())
        assert not is_free()
    assert is_free()


def test_a_stale_marker_does_not_skip_the_lock(tmp_path, monkeypatch):
    monkeypatch.setenv(run_tests.LOCK_ENV, "999999")
    proc = hold(30)
    try:
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_suite_lock(args(tmp_path, lock_wait=1.0), "full"):
                pass
    finally:
        stop(proc)
    assert os.environ[run_tests.LOCK_ENV] == "999999"


def test_unusable_lock_path_runs_without_the_lock(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(run_tests, "full_lock_path", lambda tc: blocker / "locks" / "full-suite.lock")
    ran = []
    with run_tests.full_suite_lock(args(tmp_path), "full"):
        ran.append(True)
    assert ran == [True]
    err = capsys.readouterr().err
    assert "run_tests: full-suite lock not taken: " in err and "; running without it" in err


def test_full_run_waits_for_the_lock_then_runs(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold(2)
    try:
        assert run_tests.main(["--full", "--lock-wait", "30"]) == 0
    finally:
        stop(proc)
    assert summary(tmp_path)["passed"] == 1
    assert "run_tests: full-suite lock taken after " in capsys.readouterr().err


def test_the_test_processes_inherit_the_marker(tmp_path, monkeypatch):
    project(tmp_path, "import json, os\n\ndef test_ok():\n"
                      "    rec = json.load(open(os.path.join(os.environ['SUPERLITE_HOME'], 'locks', 'full-suite-python.lock')))\n"
                      "    assert os.environ['SUPERLITE_FULL_SUITE_LOCK'] == str(rec['pid'])\n")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) == 0
    assert summary(tmp_path)["passed"] == 1


def test_lock_wait_limit_is_a_red_summary_without_incident(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold(30)
    try:
        assert run_tests.main(["--full", "--lock-wait", "1"]) == 2
    finally:
        stop(proc)
    data = summary(tmp_path)
    assert data["error"].startswith(f"full-suite lock: still held by pid {proc.pid} in /elsewhere (task T9) since ")
    assert data["error"].endswith(" after 1 s (run_tests --lock-wait S; 0 = no limit)")
    assert data["passed"] == 0
    log = tmp_path / run_tests.ct.DEFAULT_LOG
    assert not log.exists() or "full-suite lock" not in log.read_text(encoding="utf-8")
    assert capsys.readouterr().out.splitlines()[-1] == "0 0 0 0.0"


def test_fast_and_marker_runs_take_no_lock(tmp_path, monkeypatch):
    project(tmp_path, "import pytest\n\n@pytest.mark.quick\ndef test_ok():\n    assert True\n")
    monkeypatch.chdir(tmp_path)
    proc = hold(30)
    try:
        assert run_tests.main(["--fast", "test_ok.py", "--lock-wait", "1"]) == 0
        assert run_tests.main(["-m", "quick", "--lock-wait", "1"]) == 0
    finally:
        stop(proc)


def test_wait_names_the_lock_a_background_run_waits_for(tmp_path):
    project(tmp_path)
    proc = hold(60)
    try:
        cp = run(RUN_TESTS, "--full", "--background", "--lock-wait", "60", cwd=tmp_path)
        assert cp.returncode == 0, cp.both
        mine = Path(cp.out.splitlines()[0].split("summary: ", 1)[1])
        deadline = time.monotonic() + 20
        while not mine.with_suffix(".lockwait").exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        w = run(RUN_TESTS, "--wait", str(mine), "--timeout", "1", cwd=tmp_path)
        assert w.returncode == 2, w.both
        lines = w.err.splitlines()
        assert lines[-2].startswith(f"run_tests: {mine} is waiting for the python full-suite lock (held by pid {proc.pid} in /elsewhere (task T9) since "), w.err
        assert lines[-1].startswith("tests: no result yet after 1 s"), w.err
    finally:
        stop(proc)
    done = run(RUN_TESTS, "--wait", str(mine), "--timeout", "60", cwd=tmp_path)
    assert done.returncode == 0, done.both
    assert not mine.with_suffix(".lockwait").exists()
