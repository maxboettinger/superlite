"""FIFO waiter queue of the ship lock (#588)."""
import json
from test_plan_tools import SCRIPTS  # noqa: F401
import ship_lock as sl

B1 = {"batch": "B1", "lead": "W2", "agent": "a2", "repo": "o/r"}
B2 = {"batch": "B2", "lead": "W3", "agent": "a3", "repo": "o/r"}
B3 = {"batch": "B3", "lead": "W4", "agent": "a4", "repo": "o/r"}
LIVE = {"a2", "a3", "a4"}


def q(p):
    return json.loads((p.parent / (p.name + ".queue")).read_text())


def test_queue_served_in_request_order(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    assert sl.acquire(p, B1, LIVE, 1000)["acquired"]
    r2 = sl.acquire(p, B2, LIVE, 2000)
    r3 = sl.acquire(p, B3, LIVE, 3000)
    assert (r2["place"], r3["place"], r3["queued"]) == (1, 2, 2)
    assert r2["first"] == {"batch": "B2", "lead": "W3", "agent": "a3", "time": 2000, "seen": 2000}
    assert sl.release(p, "B1")
    r = sl.acquire(p, B3, LIVE, 4000)
    assert not r["acquired"] and r["place"] == 2 and r["holder"] is None
    r = sl.acquire(p, B2, LIVE, 5000)
    assert r["acquired"] and r["place"] == 0 and r["queued"] == 1
    assert sl.release(p, "B2")
    assert sl.acquire(p, B3, LIVE, 6000)["acquired"]
    assert q(p) == []


def test_dead_waiter_is_skipped(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    sl.acquire(p, B1, LIVE, 1000)
    sl.acquire(p, B2, LIVE, 2000)
    sl.acquire(p, B3, LIVE, 3000)
    sl.release(p, "B1")
    assert sl.acquire(p, B3, {"a4"}, 4000)["acquired"]


def test_unseen_waiter_expires(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    b2 = {**B2, "agent": None}
    sl.acquire(p, B1, None, 1000)
    sl.acquire(p, b2, None, 1000)
    sl.release(p, "B1")
    assert sl.acquire(p, B3, None, 1000 + 600001)["acquired"]


def test_broken_queue_file_reads_empty(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    p.parent.mkdir(parents=True)
    qf = p.parent / (p.name + ".queue")
    qf.write_text("{x")
    assert sl.acquire(p, B1, LIVE, 1000)["acquired"]
    r = sl.acquire(p, B2, LIVE, 2000)
    assert r["place"] == 1 and len(q(p)) == 1


def test_release_drops_the_waiter(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    sl.acquire(p, B1, LIVE, 1000)
    sl.acquire(p, B2, LIVE, 2000)
    assert not sl.release(p, "B2")
    assert q(p) == []
