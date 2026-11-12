"""B153 (#655): full_queue keeps the waiters of a full-suite lock in arrival order."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import full_queue  # noqa: E402

ALIVE = lambda pid: True  # noqa: E731


def entry(name, pid, seen=1.0):
    return {"id": name, "pid": pid, "root": "/r", "task": None, "time": seen, "seen": seen}


def test_join_orders_by_arrival(tmp_path):
    lock = tmp_path / "l.lock"
    places = [full_queue.join(lock, entry(n, 10 + i, float(i + 1)), alive=ALIVE, now=float(i + 1))["place"] for i, n in enumerate("abc")]
    assert places == [1, 2, 3]
    full_queue.leave(lock, "a")
    snap = full_queue.join(lock, entry("b", 11, 2.0), alive=ALIVE, now=4.0)
    assert (snap["place"], snap["queued"], snap["first"]["id"]) == (1, 2, "b")


def test_join_twice_keeps_place(tmp_path):
    lock = tmp_path / "l.lock"
    full_queue.join(lock, entry("a", 11), alive=ALIVE, now=1.0)
    full_queue.join(lock, entry("b", 12), alive=ALIVE, now=2.0)
    assert full_queue.join(lock, entry("a", 11, 5.0), alive=ALIVE, now=5.0)["place"] == 1


def test_dead_waiter_dropped(tmp_path):
    lock = tmp_path / "l.lock"
    full_queue.join(lock, entry("a", 11), alive=ALIVE, now=1.0)
    snap = full_queue.join(lock, entry("b", 12, 3.0), alive=lambda p: p != 11, now=3.0)
    assert snap["place"] == 1 and snap["first"]["id"] == "b"
    assert [e["id"] for e in json.loads(Path(str(lock) + ".queue").read_text())] == ["b"]


def test_unseen_waiter_dropped(tmp_path):
    lock = tmp_path / "l.lock"
    full_queue.join(lock, entry("a", 11, 1000.0), alive=ALIVE, now=1000.0)
    snap = full_queue.join(lock, entry("b", 12, 1601.0), alive=ALIVE, now=1601.0)
    assert snap["place"] == 1 and snap["queued"] == 1


def test_broken_queue_reads_empty(tmp_path):
    lock = tmp_path / "l.lock"
    Path(str(lock) + ".queue").write_text("not json", encoding="utf-8")
    assert full_queue.join(lock, entry("a", 11), alive=ALIVE, now=1.0)["place"] == 1


def test_leave_unknown_id_noop(tmp_path):
    lock = tmp_path / "l.lock"
    full_queue.leave(lock, "nope")
    full_queue.join(lock, entry("a", 11), alive=ALIVE, now=1.0)
    full_queue.leave(lock, "nope")
    assert full_queue.join(lock, entry("a", 11), alive=ALIVE, now=2.0)["queued"] == 1


def test_pid_alive():
    import os
    assert full_queue.pid_alive(os.getpid())
    assert not full_queue.pid_alive(2 ** 22 + 12345678)


def test_pid_alive_rejects_bad_pids():
    for bad in (None, "x", 0, -1, True, 1.5):
        assert not full_queue.pid_alive(bad)


def test_join_survives_broken_pid_entries(tmp_path):
    lock = tmp_path / "l.lock"
    bad = [{"id": "n", "pid": None, "seen": 1.0}, {"id": "s", "pid": "x", "seen": 1.0}, {"id": "z", "pid": 0, "seen": 1.0}]
    Path(str(lock) + ".queue").write_text(json.dumps(bad), encoding="utf-8")
    assert full_queue.join(lock, entry("a", 11), now=1.0)["place"] == 1


def test_symlinked_queue_reads_empty(tmp_path):
    lock = tmp_path / "l.lock"
    real = tmp_path / "real.json"
    real.write_text(json.dumps([entry("a", 11)]), encoding="utf-8")
    Path(str(lock) + ".queue").symlink_to(real)
    assert full_queue.read(lock) == []
