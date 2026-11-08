import copy
import json
import sys

from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401  bk is the CLI fixture
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

LONG = "Keep the old API " + "x" * 330 + "?"
NOTE = f'"{LONG[:60]}" question: 348 -> 300 characters'


def opts():
    return [{"label": "Keep (Recommended)", "description": "a"}, {"label": "Drop", "description": "b"}]


def prop(*texts):
    return {"batches": [{"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "depends": [],
                         "decisions": [{"questions": [{"question": t, "header": "H", "options": opts()} for t in texts]}]}]}


def qs(p):
    return p["batches"][0]["decisions"][0]["questions"]


def test_plan_cuts_a_question_over_300_and_names_the_cut():
    p = prop(LONG)
    assert len(LONG) == 348 and bc.fit_proposal(p) == [NOTE]
    assert qs(p)[0]["question"] == LONG[:300]
    batches, errs = bc.check_proposal(p, {1})
    assert errs == [] and batches[0]["decisions"][0]["questions"][0]["question"] == LONG[:300]


def test_a_question_of_300_is_untouched():
    p = prop("q" * 300)
    assert bc.fit_proposal(p) == [] and qs(p)[0]["question"] == "q" * 300


def test_question_cut_drops_trailing_blanks_and_never_leaves_nothing():
    p = prop("a" * 298 + "   tail", " " * 301)
    assert bc.fit_proposal(p) == ['"' + "a" * 60 + '" question: 305 -> 298 characters']
    assert qs(p)[0]["question"] == "a" * 298 and qs(p)[1]["question"] == " " * 301
    assert "B1 decision 1: q2 question: 1 to 300 characters" in bc.check_proposal(p, {1})[1]


def test_two_questions_equal_after_the_cut_still_reject():
    p = prop("q" * 310, "q" * 320)
    assert len(bc.fit_proposal(p)) == 2
    assert "B1 decision 1: q2 question: duplicate" in bc.check_proposal(p, {1})[1]


def test_the_question_note_comes_before_the_header_note():
    p = prop(LONG)
    qs(p)[0]["header"] = "Dependencies!"
    assert bc.fit_proposal(p) == [NOTE, f'"{LONG[:60]}" header: 13 -> 12 characters']


def test_a_lead_question_keeps_its_text_unless_asked():
    q = {"questions": [{"question": LONG, "header": "H", "options": opts()}]}
    assert bc.fit_question(q) == [] and q["questions"][0]["question"] == LONG
    c = copy.deepcopy(q)
    assert bc.fit_question(c, question=True) == [NOTE] and c["questions"][0]["question"] == LONG[:300]


def test_plan_stores_the_cut_question_and_decide_asks_it(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    bk.batches = [{**BATCH, "decisions": [{"questions": [{"question": LONG, "header": "API", "options": opts()}]}]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and out.endswith(f"shortened: {NOTE}\n")
    assert load(bk)["batches"][0]["decisions"][0]["questions"][0]["question"] == LONG[:300]
    asked = [q["question"] for q in json.loads(cli(capsys, "decide", "--print")[1])["questions"]]
    assert f"B1: {LONG[:300]}" in asked
