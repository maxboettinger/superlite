# tests/scripts/test_backlog_checks_b86.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402


def prop(topic, bid="B3", **kw):
    return {"batches": [{"id": bid, "topic": topic, "issues": [1], "files": ["a.py"], "depends": [], "decisions": [], **kw}]}


def test_topic_cut_at_last_dash():
    p = prop("backlog-plan-intake-and-status-output-fixes")
    assert bc.fit_proposal(p) == ['"B3" topic: 43 -> 37 characters']
    assert p["batches"][0]["topic"] == "backlog-plan-intake-and-status-output"
    assert bc.check_proposal(p, {1})[1] == []


def test_topic_without_dash_plain_cut():
    p = prop("a" * 45, bid="B1")
    assert bc.fit_proposal(p) == ['"B1" topic: 45 -> 40 characters']
    assert p["batches"][0]["topic"] == "a" * 40


def test_topic_40_untouched():
    p = prop("a" * 40)
    assert bc.fit_proposal(p) == [] and p["batches"][0]["topic"] == "a" * 40


def test_topic_note_names_batch_k():
    p = prop("a" * 45)
    del p["batches"][0]["id"]
    assert bc.fit_proposal(p) == ['"batch 1" topic: 45 -> 40 characters']


def test_topic_note_before_question_notes():
    q = {"question": "Keep?", "header": "a much too long header", "options": [{"label": "A"}, {"label": "B"}]}
    notes = bc.fit_proposal(prop("a" * 45, decisions=[q]))
    assert notes[0].startswith('"B3" topic:') and len(notes) == 2


def test_left_out_reasons_examples():
    assert bc.left_out_reasons({"batches": [], "left_out": [{"issues": [2, "#3", 9], "reason": "needs design"}, {"issues": [2], "reason": "dup"}]}, {1, 2, 3}) == {2: "needs design", 3: "needs design"}
    assert bc.left_out_reasons({"left_out": [{"issues": ["pix-2"], "reason": " blocked\nby PIX-1 "}]}, {"PIX-1", "PIX-2"}) == {"PIX-2": "blocked by PIX-1"}
    assert bc.left_out_reasons({"left_out": "x"}, {1}) == {}


def test_reason_cut_and_cleaned():
    r = bc.left_out_reasons({"left_out": [{"issues": [1], "reason": "x\x00y " + "word " * 14}]}, {1})[1]
    assert not any(ord(c) < 32 for c in r) and len(r) <= 60 and r == r.rstrip() and r.endswith("word")


def test_bad_entries_ignored():
    bad = ["s", {"issues": 2, "reason": "r"}, {"issues": [1], "reason": 5}, {"issues": [True], "reason": "r"}, {"issues": [1], "reason": "   "}]
    assert bc.left_out_reasons({"left_out": bad}, {1, 2}) == {}
