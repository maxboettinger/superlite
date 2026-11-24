"""A waiter that still polls keeps its queue place when one Herdr read misses its agent (#1115)."""
from test_plan_tools import SCRIPTS  # noqa: F401
import ship_lock as sl

B1 = {"batch": "B1", "lead": "W2", "agent": "a2", "repo": "o/r"}
B2 = {"batch": "B2", "lead": "W3", "agent": "a3", "repo": "o/r"}
B3 = {"batch": "B3", "lead": "W4", "agent": "a4", "repo": "o/r"}
LIVE = {"a2", "a3", "a4"}


def test_grace_values():
    assert (sl.LIVE_GRACE_MS, sl.QUEUE_STALE_MS) == (120000, 600000)


def test_polling_head_survives_a_missed_agent_read(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    assert sl.acquire(p, B1, LIVE, 1000)["acquired"]
    sl.acquire(p, B2, LIVE, 2000)
    sl.acquire(p, B3, LIVE, 3000)
    r = sl.acquire(p, B3, {"a2", "a4"}, 4000)
    assert (r["place"], r["queued"], r["first"]["batch"]) == (2, 2, "B2")
    assert sl.release(p, "B1")
    r = sl.acquire(p, B3, {"a4"}, 5000)
    assert not r["acquired"] and r["place"] == 2 and r["first"]["batch"] == "B2"
    assert sl.acquire(p, B2, LIVE, 6000)["acquired"]


def test_gone_waiter_dropped_after_grace(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    sl.acquire(p, B1, LIVE, 1000)
    sl.acquire(p, B2, LIVE, 2000)
    sl.acquire(p, B3, LIVE, 3000)
    sl.release(p, "B1")
    assert not sl.acquire(p, B3, {"a4"}, 2000 + sl.LIVE_GRACE_MS)["acquired"]
    assert sl.acquire(p, B3, {"a4"}, 2001 + sl.LIVE_GRACE_MS)["acquired"]


def test_unreadable_herdr_keeps_waiters(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    sl.acquire(p, B1, LIVE, 1000)
    sl.acquire(p, B2, LIVE, 2000)
    sl.release(p, "B1")
    assert not sl.acquire(p, B3, None, 2000 + sl.LIVE_GRACE_MS + 1)["acquired"]
