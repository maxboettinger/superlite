"""B153 (#655): run_tests.full_suite_lock serves waiters first come first served."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_full_suite_lock_480 import args, hold, stop
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import full_queue  # noqa: E402
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

WAITER = r'''
import sys, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import run_tests
name, base = sys.argv[2], Path(sys.argv[3])
a = SimpleNamespace(lock_wait=60.0, task=None, run_id=None, summary=str(base / f"{name}-summary.json"))
with run_tests.full_suite_lock(a, "full"):
    with open(base / "order.txt", "a") as f:
        f.write(name + "\n")
    time.sleep(0.3)
'''


@pytest.fixture(autouse=True)
def _no_outer_lock(monkeypatch):
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)


def queue_file():
    return Path(str(run_tests.full_lock_path("python")) + ".queue")


def queued_names():
    try:
        return [e["id"] for e in json.loads(queue_file().read_text())]
    except (OSError, ValueError):
        return []


def test_three_waiters_served_in_arrival_order(tmp_path):
    holder = hold(60)
    procs = []
    env = dict(os.environ)
    try:
        for i, n in enumerate(("w1", "w2", "w3")):
            procs.append(subprocess.Popen([sys.executable, "-c", WAITER, str(SCRIPTS), n, str(tmp_path)], env=env, cwd=tmp_path))
            end = time.time() + 20
            while len(queued_names()) < i + 1 and time.time() < end:
                time.sleep(0.05)
            assert len(queued_names()) == i + 1
        stop(holder)
        end = time.time() + 30
        order = tmp_path / "order.txt"
        while time.time() < end and (not order.exists() or len(order.read_text().split()) < 3):
            time.sleep(0.1)
        assert order.read_text() == "w1\nw2\nw3\n"
    finally:
        for p in procs:
            p.kill()
            p.wait(timeout=10)
        if holder.poll() is None:
            stop(holder)


def test_dead_waiter_does_not_hold_a_place(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    lock = run_tests.full_lock_path("python")
    full_queue.join(lock, {"id": "dead", "pid": child.pid, "root": "/x", "task": None, "time": time.time(), "seen": time.time()})
    t0 = time.time()
    with run_tests.full_suite_lock(args(tmp_path, lock_wait=2.0), "full"):
        pass
    assert time.time() - t0 < 2
    assert "waiting for" not in capsys.readouterr().err


def test_wait_line_names_queue_place(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    holder = hold(30)
    lock = run_tests.full_lock_path("python")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        full_queue.join(lock, {"id": "other", "pid": other.pid, "root": "/x", "task": None, "time": time.time(), "seen": time.time()})
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_suite_lock(args(tmp_path, lock_wait=1.0), "full"):
                pass
        err = capsys.readouterr().err
        assert err.count("python full runs on one machine run one at a time, in arrival order: queue place 2 of 2") == 1
        assert queued_names() == ["other"]
    finally:
        other.kill()
        other.wait(timeout=10)
        stop(holder)


def test_foreground_wait_writes_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".superlite").mkdir()
    holder = hold(30)
    a = args(tmp_path, lock_wait=30.0)
    note = Path(a.summary).with_suffix(".lockwait")
    seen = {}
    import threading

    def run():
        with run_tests.full_suite_lock(a, "full"):
            pass

    t = threading.Thread(target=run)
    try:
        t.start()
        end = time.time() + 10
        while not note.exists() and time.time() < end:
            time.sleep(0.05)
        seen = json.loads(note.read_text())
    finally:
        stop(holder)
        t.join(timeout=20)
    assert {"lock", "holder", "pid", "since", "place", "queued"} <= set(seen)
    assert seen["pid"] == os.getpid() and (seen["place"], seen["queued"]) == (1, 1)
    assert not note.exists()
