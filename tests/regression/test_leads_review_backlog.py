import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import ship_lock as sl  # noqa: E402

OWN = {"batch": "B2", "lead": "W2", "agent": "a2", "repo": "o/r"}
HOUR = 3600 * 1000


def test_live_holder_is_never_taken_over_by_age_when_herdr_is_readable(tmp_path):
    p = tmp_path / "locks" / "ship-o-r.lock"
    assert sl.acquire(p, {**OWN, "batch": "B1", "agent": "a1"}, {"a1"}, 0)["acquired"]
    r = sl.acquire(p, OWN, {"a1", "a2"}, 5 * HOUR)
    assert not r["acquired"] and r["holder"]["batch"] == "B1"


def test_gone_holder_and_unreadable_herdr_still_go_stale(tmp_path):
    p = tmp_path / "locks" / "ship-o-r.lock"
    sl.acquire(p, {**OWN, "batch": "B1", "agent": "a1"}, {"a1"}, 0)
    assert sl.acquire(p, OWN, {"a2"}, 1000)["took_over"]
    q = tmp_path / "locks" / "ship-x.lock"
    sl.acquire(q, {**OWN, "batch": "B1", "agent": "a1"}, None, 0)
    assert not sl.acquire(q, OWN, None, HOUR)["acquired"]
    assert sl.acquire(q, OWN, None, 3 * HOUR)["took_over"]


def test_brief_without_approval_forbids_shipping():
    ctx = {"sl": "/p/sl", "backlog_md": "/p/b.md", "repo": "o/r", "approved": None, "titles": {}, "summaries": [], "resume": False}
    out = bb.lead_brief({"id": "B2", "topic": "t", "issues": [1], "files": [], "answers": {}, "reason": ""}, ctx)
    assert "Ship: NOT approved" in out and "backlog ship" not in out and "None" not in out
