import sys
from backlog_fixtures import Q, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402


def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), **kw}


def nxt(d):
    return {l.split(" | ")[0]: l.split(" | ")[-1] for l in bs.status_lines(d) if l.startswith("B")}


def test_two_planned_share_a_file():
    d = data(b("B61", ["docs.md"]), b("B62", ["docs.md"]))
    assert nxt(d) == {"B61": "start", "B62": "start, or after B61"} and bs.holds(d) == {"B62": "B61"}


def test_running_holder_keeps_clash():
    d = data(b("B61", ["docs.md"], "running"), b("B62", ["docs.md"]))
    assert nxt(d)["B62"] == "clash B61" and bs.holds(d) == {"B62": "B61"}


def test_waiting_batch_holds_nothing():
    d = data(b("B61", ["docs.md"], depends=["B60"]), b("B62", ["docs.md"]), b("B60", ["z.md"], "running"))
    n = nxt(d)
    assert n["B61"] == "waits B60" and n["B62"] == "start" and bs.holds(d) == {}


def test_open_decision_holds_nothing():
    d = data(b("B61", ["docs.md"], decisions=[Q]), b("B62", ["docs.md"]))
    assert nxt(d)["B62"] == "start" and bs.holds(d) == {}


def test_append_only_no_hold():
    d = data(b("B61", ["docs.md"], append_only=["docs.md"]), b("B62", ["docs.md"], append_only=["docs.md"]))
    assert nxt(d) == {"B61": "start", "B62": "start"} and bs.holds(d) == {}


def test_disjoint_no_hold():
    assert bs.holds(data(b("B61", ["a.py"]), b("B62", ["b.py"]))) == {}


def test_status_matches_startable():
    d = data(b("B1", ["a"]), b("B2", ["a"]), b("B3", ["b"]))
    n = nxt(d)
    assert bs.startable(d, cap=9) == [k for k, v in n.items() if v == "start"] == ["B1", "B3"]


def test_first_holder_named():
    d = data(b("B1", ["a"]), b("B2", ["a"]), b("B3", ["a", "b"]))
    assert bs.holds(d) == {"B2": "B1", "B3": "B1"}
