import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from backlog_fixtures import APPROVED, Q, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), **kw}

def test_main_root_load_update_and_batch(tmp_path):
    m = tmp_path / "m"; m.mkdir()
    git = lambda *a: subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", *a], cwd=m, check=True, capture_output=True)
    git("init", "-q"); git("commit", "-q", "--allow-empty", "-m", "x"); git("worktree", "add", "-q", "-b", "l", str(tmp_path / "wt"))
    assert bs.main_root(tmp_path / "wt") == m.resolve() == bs.main_root(m)
    with pytest.raises(RuntimeError, match="not in a git repository"):
        bs.main_root(tmp_path)
    p = bs.path(m); assert p == m / ".superlite" / "backlog.json"
    assert bs.load(p) == bs.default() == {"version": 1, "repo": "", "approved_ship": None, "titles": {}, "outside": [], "admitted": [], "skipped": [], "batches": []}
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: bs.update(p, lambda d: d["admitted"].append(i)), range(40)))
    assert sorted(bs.load(p)["admitted"]) == list(range(40)) and bs.update(p, lambda d: "ok") == "ok"
    with pytest.raises(KeyError, match="unknown batch B9"):
        bs.batch(bs.load(p), "B9")
    p.write_text("{broken"); assert bs.load(p) == bs.default()

def test_startable_respects_cap_clash_depends_and_decisions():
    d = data(b("B1", ["a.py"], "running"), b("B2", ["a.py"]), b("B3", ["c.py"]), b("B4", ["d.py"], depends=["B1"]), b("B5", ["e.py"], decisions=[Q]), b("B6", ["f.py"]))
    assert bs.startable(d, 2) == ["B3"] and bs.startable(d, 3) == ["B3", "B6"]
    d["batches"][4]["answers"] = {"Keep the v1 API?": "Drop"}; d["batches"][0]["state"] = "shipped"
    assert bs.startable(d, 9) == ["B2", "B3", "B4", "B5", "B6"]

def test_questions_and_answers():
    d = data(b("B2", ["a.py"], decisions=[Q]), outside=[{"number": 7, "title": "Add\nX", "author": "eve"}, {"number": 8, "title": "Y", "author": "mal"}])
    a7, a8 = "Admit outside issue #7 (Add X, by eve) into the backlog?", "Admit outside issue #8 (Y, by mal) into the backlog?"
    qs = bs.open_questions(d)
    assert [q["question"] for q in qs] == [bs.SHIP_Q, a7, a8, "B2: Keep the v1 API?"] and bs.open_questions(data()) == []
    assert [o["label"] for o in qs[0]["options"]] == ["Approve shipping", "Not yet"] and (qs[1]["header"], qs[3]["header"]) == ("#7", "API")
    assert bs.answer(d, {bs.SHIP_Q: "sure"}, "AskUserQuestion", "T") == ["ship: answer must be Approve shipping or Not yet"]
    errs = bs.answer(d, {bs.SHIP_Q: "Approve shipping", a7: "Admit", a8: "Skip", "B2: Keep the v1 API?": "Drop, and log it", "B9: x?": "y"}, "AskUserQuestion", "T")
    assert errs == ["no open question: B9: x?"] and d["approved_ship"] == {"by": "AskUserQuestion", "time": "T"}
    assert (d["admitted"], d["skipped"], d["batches"][0]["answers"]) == ([7], [8], {"Keep the v1 API?": "Drop, and log it"}) and bs.open_questions(d) == []

def test_status_lines_one_screen():
    d = data(b("B1", ["a.py"], "shipped", pr=201, version="1.5.8", lead="W1"), b("B2", ["b.py"], "needs_decision", lead="W2"),
             b("B3", ["c.py"], depends=["B2"]), b("B4", ["d.py"], "parked", reason="tui layer red"), approved_ship=APPROVED)
    assert bs.status_lines(d) == ["backlog o/r: 4 batches, 1 running, 1 shipped, ship approved (AskUserQuestion 2026-11-05T10:00:00Z)",
        "batch | issues | state | lead | PR | next", "B1 | #1 | shipped | W1 | #201 | 1.5.8",
        "B2 | #2 | needs_decision | W2 | - | sl backlog decide --print --batch B2", "B3 | #3 | planned | - | - | waits B2",
        "B4 | #4 | parked | - | - | tui layer red"]
    assert bs.status_lines(bs.default()) == ["backlog: 0 batches, 0 running, 0 shipped, ship not approved"]
    assert bs.status_lines(data(b("B1", ["a.py"], decisions=[Q])))[-2:] == ["B1 | #1 | planned | - | - | decide", "questions: 2 open (sl backlog decide --print)"]
