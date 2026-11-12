"""One answer rule for decide and answer (#586)."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_answer as ba  # noqa: E402

L = ["Keep", "Drop"]


def test_labels_of():
    q = {"question": "Keep?", "options": [{"label": "Keep (Recommended)"}, {"label": "Drop"}, "x", {"label": 3}, {}]}
    assert ba.labels_of(q) == ["Keep", "Drop"]
    assert ba.labels_of({"question": "Q?"}) == []


def test_examples():
    assert ba.answer_text("Keep (Recommended)", L) == ("Keep", "")
    assert ba.answer_text("Drop, additive only", L) == ("Drop, additive only", "")
    assert ba.answer_text({"label": "Drop", "note": "old runs unchanged"}, L) == ("Drop; note: old runs unchanged", "")
    assert ba.answer_text({"label": "Drop", "note": ""}, L) == ("Drop", "")
    assert ba.answer_text({"label": "Drop"}, L) == ("Drop", "")
    assert ba.answer_text("Maybe", ["Approve shipping", "Not yet"], fixed=True) == (None, "answer must be one of: Approve shipping, Not yet")
    assert ba.answer_text({"label": "Admit", "note": "x"}, ["Admit", "Skip"], fixed=True) == (None, "this question takes only its label, no note")
    assert ba.answer_text({"label": "Later", "note": ""}, L) == (None, 'label "Later" is not one of: Keep, Drop')
    assert ba.answer_text("x\x1b[2J", ["Keep"]) == (None, ba.RULE)
    assert ba.answer_text(3, []) == (None, ba.RULE)


def test_control_characters_refused_newline_kept():
    assert ba.answer_text("a\nb\tc", L) == ("a\nb\tc", "")
    for bad in ("a\x07", "a\x7f"):
        assert ba.answer_text(bad, L) == (None, ba.RULE)
        assert ba.answer_text({"label": "Drop", "note": bad}, L) == (None, ba.RULE)


def test_length_bounds():
    assert ba.answer_text("a" * 2000, L)[0] == "a" * 2000
    assert ba.answer_text("a" * 2001, L) == (None, ba.RULE)
    assert ba.answer_text("", L) == (None, ba.RULE)
    assert ba.answer_text("   ", L) == (None, ba.RULE)


def test_object_keys():
    assert ba.answer_text({"label": "Drop", "extra": 1}, L) == (None, ba.RULE)
    assert ba.answer_text({"note": "x"}, L) == (None, ba.RULE)
    assert ba.answer_text({"label": 3}, L) == (None, ba.RULE)
    assert ba.answer_text({"label": "Drop", "note": 3}, L) == (None, ba.RULE)


def test_unknown_labels_accept_any_label():
    assert ba.answer_text({"label": "Whatever (Recommended)"}, []) == ("Whatever", "")


def test_fixed_takes_recommended_suffix():
    assert ba.answer_text("Approve shipping (Recommended)", ["Approve shipping", "Not yet"], fixed=True) == ("Approve shipping", "")


def test_object_answer_text_bounded():
    assert ba.answer_text({"label": "Drop", "note": "n" * 1980}, L)[1] == ""
    assert ba.answer_text({"label": "Drop", "note": "n" * 1995}, L) == (None, ba.RULE)
    out, why = ba.answer_text({"label": "Drop", "note": "n" * 1900}, L)
    assert why == "" and len(out) <= 2000
