# tests/scripts/test_ship_lock.py
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import ship_lock as sl  # noqa: E402

B1 = {"batch": "B1", "lead": "W2", "agent": "a2", "repo": "o/r"}
B2 = {"batch": "B2", "lead": "W3", "agent": "a3", "repo": "o/r"}
H2 = 2 * 3600 * 1000

def test_lock_path(tmp_path, monkeypatch):
    assert sl.lock_path("maxboettinger/superlite", tmp_path) == tmp_path / "locks" / "ship-maxboettinger-superlite.lock"
    assert sl.lock_path("../Evil Repo", tmp_path).name == "ship-evil-repo.lock"
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "h")); assert sl.lock_path("o/r") == tmp_path / "h" / "locks" / "ship-o-r.lock"
    with pytest.raises(ValueError):
        sl.lock_path("../", tmp_path)

def test_acquire_reentry_release(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    assert sl.acquire(p, B1, {"a2"}, 1000) == {"acquired": True, "holder": None, "took_over": False}
    assert sl.holder(p) == {**B1, "time": 1000} and oct(p.stat().st_mode & 0o777) == "0o600"
    assert sl.acquire(p, B1, {"a2"}, 5000)["acquired"] and sl.holder(p)["time"] == 1000
    assert sl.acquire(p, B2, {"a2", "a3"}, 6000) == {"acquired": False, "holder": {**B1, "time": 1000}, "took_over": False}
    assert not sl.release(p, "B2") and sl.release(p, "B1") and sl.holder(p) is None and not p.exists()

def test_stale_holders(tmp_path):
    p = sl.lock_path("o/r", tmp_path); sl.acquire(p, B1, None, 1000)
    assert sl.acquire(p, B2, {"a3"}, 2000) == {"acquired": True, "holder": {**B1, "time": 1000}, "took_over": True}
    assert not sl.acquire(p, B1, None, 2000 + H2)["acquired"] and sl.acquire(p, B1, None, 2001 + H2)["took_over"]

def test_unreadable_or_symlinked_lock_is_held_and_never_followed(tmp_path):
    p = sl.lock_path("o/r", tmp_path); p.parent.mkdir(parents=True); p.write_text("{broken"); os.utime(p, (1, 1))
    r = sl.acquire(p, B1, set(), 1000)
    assert not r["acquired"] and r["holder"]["batch"] == "?" and not sl.release(p, "?") and sl.acquire(p, B1, set(), 1001 + H2)["took_over"]
    p.unlink(); victim = tmp_path / "victim"; victim.write_text("keep"); p.symlink_to(victim)
    assert not sl.acquire(p, B1, {"a2"}, int(time.time() * 1000))["acquired"] and not sl.release(p, "B1") and victim.read_text() == "keep"

def test_parallel_acquire_has_one_winner(tmp_path):
    p = sl.lock_path("o/r", tmp_path)
    owners = [{**B1, "batch": f"B{i}", "agent": f"a{i}"} for i in range(1, 9)]
    live = {o["agent"] for o in owners}
    with ThreadPoolExecutor(8) as ex:
        won = list(ex.map(lambda o: sl.acquire(p, o, live, 1000)["acquired"], owners))
    assert won.count(True) == 1
