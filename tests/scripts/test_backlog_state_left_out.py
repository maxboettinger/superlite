import copy
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

OUT = [{"number": 3, "title": "Three", "author": "eve"},
       {"number": 5, "title": "Five", "reason": "not planned (cap)"},
       {"number": 6, "title": "Six", "reason": "not planned (cap)"},
       {"number": 7, "title": "Seven", "reason": "not triaged (200 cap)"}]


def data(**kw):
    d = {"outside": copy.deepcopy(OUT), "batches": [], "approved_ship": None, "admitted": [], "skipped": []}
    d.update(kw)
    return d


def test_left_out_lines_group_by_reason():
    assert bs.left_out_lines(data()) == ["not planned (cap): #5 #6", "not triaged (200 cap): #7"]


def test_admit_entries_skip_left_out():
    assert bs.admit_entries(data()) == [OUT[0]]


def test_open_questions_ask_admit_only_for_authors():
    qs = bs.open_questions(data())
    assert len(qs) == 1
    assert qs[0]["question"].startswith("Admit outside issue #3")
    assert not any(f"#{n}" in q["question"] for q in qs for n in (5, 6, 7))


def test_answer_refuses_left_out_admit():
    d = data()
    q = "Admit outside issue #5 (Five, by ) into the backlog?"
    assert bs.answer(d, {q: "Admit"}, "AskUserQuestion", "t") == [f"no open question: {q}"]
    assert d["admitted"] == []
    assert any(o["number"] == 5 for o in d["outside"])


def test_status_no_batches_lists_left_out():
    assert bs.status_lines(data()) == ["backlog: 0 batches, 0 running, 0 shipped, ship not approved",
                                       "not planned (cap): #5 #6", "not triaged (200 cap): #7"]


def test_status_order_table_reasons_questions():
    b = {"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "depends": [], "decisions": [], "state": "planned"}
    lines = bs.status_lines(data(batches=[b]))
    assert lines[2] == "B1 | #1 | planned | - | - | start"
    assert lines[-3:] == ["not planned (cap): #5 #6", "not triaged (200 cap): #7",
                          "questions: 2 open (sl backlog " + "decide --print)"]


def test_reason_cleaned():
    d = data(outside=[{"number": 9, "title": "N", "reason": "a\nb" + "x" * 100}])
    assert bs.left_out_lines(d) == ["a b" + "x" * 77 + ": #9"]


def test_entries_without_reason_unchanged():
    outside = [{"number": 3, "title": "Three", "author": "eve"},
               {"number": 4, "title": "Four", "author": "bob", "reason": ""}]
    b = {"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "depends": [], "decisions": [], "state": "planned"}
    d = data(outside=outside, batches=[b], approved_ship={"by": "x", "time": "t"})
    assert bs.left_out_lines(d) == []
    assert bs.admit_entries(d) == outside
    assert sum(q["question"].startswith("Admit outside issue") for q in bs.open_questions(d)) == 2


def test_skip_drops_left_out_entry():
    d = data()
    assert bs.skip_issue(d, 5) == "skipped #5 (in no batch)"
    assert bs.left_out_lines(d) == ["not planned (cap): #6", "not triaged (200 cap): #7"]
    assert d["skipped"] == [5]
