import sys
import pytest
from backlog_fixtures import Q, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402
import backlog_state as bs  # noqa: E402

BAD = 'by: "user", "main" or a {question: "user"|"main"} map'
SHIP_MAIN = ("ship: main cannot rule the ship approval; ask the user, or record an approval the user's prompt gave "
             "with sl backlog decide --approve-ship --source prompt")
KQ = "B2: Keep the v1 API?"


def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), **kw}


def test_answer_by_examples():
    assert bc.answer_by({"answers": {"A?": "x"}}, {"A?": "x"}) == ({"A?": "user"}, "")
    assert bc.answer_by({"by": "main"}, {"A?": "x", "B?": "y"}) == ({"A?": "main", "B?": "main"}, "")
    assert bc.answer_by({"by": {"B?": "main"}}, {"A?": "x", "B?": "y"}) == ({"A?": "user", "B?": "main"}, "")
    assert bc.answer_by({"by": "bot"}, {"A?": "x"}) == ({}, BAD)
    assert bc.answer_by({"by": {"C?": "main"}}, {"A?": "x"}) == ({}, "by: no answer for C?")
    assert bc.answer_by({"by": ["main"]}, {"A?": "x"}) == ({}, BAD)
    assert bc.answer_by({"by": {"A?": "admin"}}, {"A?": "x"}) == ({}, BAD)


def test_ship_question_last_and_recommended():
    d = data(b("B2", ["a.py"], decisions=[Q]), outside=[{"number": 7, "title": "X", "author": "eve"}])
    qs = bs.open_questions(d)
    assert [q["question"] for q in qs][1:] == ["B2: Keep the v1 API?", bs.SHIP_Q]
    assert qs[0]["question"].startswith("Admit outside issue #7")
    ship = qs[-1]
    assert [o["label"] for o in ship["options"]] == ["Approve shipping (Recommended)", "Not yet"]
    assert ship["options"][0]["description"] == "one yes for every batch of this plan round; a new plan asks again"
    assert ship["options"][1]["description"] == "leads stop before ship"


def test_answer_records_who_answered():
    d = data(b("B2", ["a.py"], decisions=[Q]))
    assert bs.answer(d, {bs.SHIP_Q: "Approve shipping (Recommended)"}, {bs.SHIP_Q: "user"}, "T") == []
    assert d["approved_ship"] == {"by": "AskUserQuestion", "time": "T"}
    d = data(b("B2", ["a.py"], decisions=[Q]))
    assert bs.answer(d, {bs.SHIP_Q: "Approve shipping"}, {bs.SHIP_Q: "main"}, "T") == [SHIP_MAIN]
    assert d["approved_ship"] is None
    assert bs.answer(d, {KQ: "Drop"}, {KQ: "main"}, "T") == []
    assert d["batches"][0]["answers"] == {"Keep the v1 API?": "Drop"}
    assert d["batches"][0]["answered_by"] == {"Keep the v1 API?": "main"}
    d = data(b("B2", ["a.py"], decisions=[Q]))
    assert bs.answer(d, {bs.SHIP_Q: "Approve shipping", KQ: "Drop"}, "AskUserQuestion", "T") == []
    assert d["batches"][0]["answered_by"] == {"Keep the v1 API?": "user"}
    assert d["approved_ship"] == {"by": "AskUserQuestion", "time": "T"}


def test_approve_ship_prompt():
    d = data(b("B1", ["a.py"]))
    assert bs.approve_ship(d, "prompt", "T") == "ship approved (prompt T): every batch of this plan round may ship"
    assert d["approved_ship"] == {"by": "prompt", "time": "T"}
    d["approved_ship"] = {"by": "AskUserQuestion", "time": "T0"}
    assert bs.approve_ship(d, "prompt", "T") == "ship already approved (AskUserQuestion T0)"
    assert d["approved_ship"] == {"by": "AskUserQuestion", "time": "T0"}
    with pytest.raises(ValueError, match=r"--source: only prompt \(an AskUserQuestion answer goes through decide --file\)"):
        bs.approve_ship(data(b("B1", ["a.py"])), "user", "T")
    with pytest.raises(ValueError, match="no batch planned: run sl backlog plan first"):
        bs.approve_ship(data(), "prompt", "T")


def test_status_shipped_counts():
    d = data(b("B3", ["c.py"], "shipped", version="1.5.9", followups=["a", "b"], undone=["c"], open_issues=[6]))
    assert [x for x in bs.status_lines(d) if x.startswith("B3 ")][0].endswith("| 1.5.9 followups=2 undone=1 OPEN #6")
    d = data(b("B3", ["c.py"], "shipped", version="1.5.9"))
    assert [x for x in bs.status_lines(d) if x.startswith("B3 ")][0].endswith("| 1.5.9")
