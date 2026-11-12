# tests/scripts/test_backlog_checks_583.py
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402


def bt(bid, issues=(1,), files=("a.py",), depends=(), topic="t"):
    return {"id": bid, "topic": topic, "issues": list(issues), "files": list(files), "depends": list(depends), "decisions": []}


def test_topic_slug():
    assert bc.topic_slug("Backlog Plan --add: Rejects") == "backlog-plan-add-rejects"
    assert bc.topic_slug("!!!") == ""


def test_slug_cut_keeps_whole_words():
    t = "backlog plan --add rejects the triage worker's own proposal: batch id"
    assert bc.topic_slug(t) == "backlog-plan-add-rejects-the-triage"


def test_normalise_topics():
    obj = {"batches": [{"id": "B1", "topic": "Backlog Plan"}, {"topic": "ok-topic"}, {"topic": "Two Words"}]}
    assert bc.normalise_topics(obj) == ['topic: "B1" "Backlog Plan" -> backlog-plan', 'topic: "batch 3" "Two Words" -> two-words']
    assert [b["topic"] for b in obj["batches"]] == ["backlog-plan", "ok-topic", "two-words"]
    assert bc.normalise_topics("x") == [] and bc.normalise_topics({"batches": [3, {"topic": 5}, {"topic": "!!!"}]}) == []


def test_normalise_note_drops_control_characters():
    obj = {"batches": [{"id": "B1", "topic": "Bad\x1b[2J Topic"}]}
    notes = bc.normalise_topics(obj)
    assert len(notes) == 1 and "\x1b" not in notes[0] and obj["batches"][0]["topic"] == "bad-2j-topic"


def test_check_proposal_accepts_backlog_depends():
    b = bt("B174", depends=["B112"], topic="t")
    out, errs = bc.check_proposal({"batches": [b]}, {1}, frozenset({"B112"}))
    assert errs == [] and out[0]["id"] == "B174" and out[0]["depends"] == ["B112"]


@pytest.mark.parametrize("bid,ok", [("B999999", True), ("B1000000", False), ("B0", False), ("X1", False)])
def test_id_range_and_message(bid, ok):
    out, errs = bc.check_proposal({"batches": [bt(bid)]}, {1})
    if ok:
        assert errs == [] and out[0]["id"] == bid
    else:
        assert out == [] and f"batch 1: id must be B<n>, B1 to B999999 (got {bid!r})" in errs


def test_local_id_wins_over_backlog_id():
    out, errs = bc.check_proposal({"batches": [bt("B1", [1], ["a.py"]), bt("B2", [2], ["a.py"], ["B1"])]}, {1, 2}, frozenset({"B1"}))
    assert errs == [] and out[1]["depends"] == ["B1"]
    assert [b["id"] for b in bc.separate(out)] == ["B1", "B2"]


def test_unknown_depends_still_rejected():
    out, errs = bc.check_proposal({"batches": [bt("B1", depends=["B7"])]}, {1}, frozenset({"B1"}))
    assert out == [] and "B1: depends on unknown batch B7" in errs


def test_trailing_newline_id_and_topic_rejected():
    out, errs = bc.check_proposal({"batches": [bt("B1\n")]}, {1})
    assert out == [] and errs
    out, errs = bc.check_proposal({"batches": [bt("B1", topic="ok\n")]}, {1})
    assert any("topic must be" in e for e in errs)
    obj = {"batches": [{"id": "B1", "topic": "ok\n"}]}
    assert bc.normalise_topics(obj) == ['topic: "B1" "ok" -> ok'] and obj["batches"][0]["topic"] == "ok"


def test_normalise_note_drops_control_characters_in_id():
    obj = {"batches": [{"id": "B1\x1b[2J", "topic": "Two Words"}]}
    notes = bc.normalise_topics(obj)
    assert len(notes) == 1 and "\x1b" not in notes[0]
