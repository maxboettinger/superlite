import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

REC = " (Recommended)"

def q(header="API", labels=("Keep (Recommended)", "Drop"), desc="d", question="Which store?"):
    return {"questions": [{"question": question, "header": header,
                           "options": [{"label": lb, "description": desc} for lb in labels]}]}

def prop(*decisions):
    return {"batches": [{"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "depends": [], "decisions": list(decisions)}]}

def first(p):
    return p["batches"][0]["decisions"][0]["questions"][0]

def test_long_header_and_label_are_cut_and_the_proposal_passes():
    p = prop(q(header="Dependencies!", labels=("x" * 72 + REC, "Drop")))
    assert bc.fit_proposal(p) == ['"Which store?" header: 13 -> 12 characters', '"Which store?" option 1 label: 86 -> 60 characters']
    assert first(p)["header"] == "Dependencies" and first(p)["options"][0]["label"] == "x" * 46 + REC
    batches, errs = bc.check_proposal(p, {1})
    assert errs == [] and batches[0]["decisions"][0]["questions"][0]["header"] == "Dependencies"

def test_cut_drops_trailing_spaces_and_a_plain_label_keeps_its_start():
    p = prop(q(header="Ship it now please", labels=("a" * 59 + " tail", "Drop")))
    assert len(bc.fit_proposal(p)) == 2
    assert first(p)["header"] == "Ship it now" and first(p)["options"][0]["label"] == "a" * 59

def test_the_note_reports_the_real_length_after_trailing_spaces_are_dropped():
    p = prop(q(header="Ship it now please", labels=("a" * 59 + " tail", "Drop")))
    assert bc.fit_proposal(p) == ['"Which store?" header: 18 -> 11 characters', '"Which store?" option 1 label: 64 -> 59 characters']

def test_long_descriptions_are_cut_to_200():
    p = prop(q(desc="y" * 250))
    assert bc.fit_proposal(p) == ['"Which store?" option 1 description: 250 -> 200 characters',
                                  '"Which store?" option 2 description: 250 -> 200 characters']
    assert [len(o["description"]) for o in first(p)["options"]] == [200, 200]

def test_texts_within_limits_are_untouched():
    args = dict(header="x" * 12, labels=("y" * 60, "Drop"), desc="z" * 200)
    p = prop(q(**args))
    assert bc.fit_proposal(p) == [] and p == prop(q(**args))

def test_a_bare_question_decision_is_fitted_in_place():
    bare = q(header="Dependencies!")["questions"][0]
    p = prop(bare)
    assert bc.fit_proposal(p) == ['"Which store?" header: 13 -> 12 characters'] and bare["header"] == "Dependencies"
    assert p["batches"][0]["decisions"][0] is bare

def test_every_other_error_is_left_for_check_proposal():
    bad = {"question": "", "header": "", "options": [{"label": "", "description": "d"}, {"label": "a\x1b", "description": "d"}]}
    p = prop({"questions": [bad]})
    assert bc.fit_proposal(p) == []
    assert {"B1 decision 1: q1 question: 1 to 300 characters", "B1 decision 1: q1 header: 1 to 12 characters",
            "B1 decision 1: q1 options label: label 1 to 60 characters",
            "B1 decision 1: q1 options label: control character"} <= set(bc.check_proposal(p, {1})[1])

def test_a_cut_that_makes_two_labels_equal_still_rejects():
    p = prop(q(labels=("z" * 70, "z" * 65)))
    assert len(bc.fit_proposal(p)) == 2
    assert "B1 decision 1: q1 options: duplicate label " + "z" * 60 in bc.check_proposal(p, {1})[1]

def test_a_cut_that_would_leave_nothing_is_not_made():
    p = prop(q(header=" " * 13))
    assert bc.fit_proposal(p) == [] and first(p)["header"] == " " * 13

def test_the_note_names_the_question_without_control_characters():
    p = prop(q(header="Dependencies!", question="Pick\x1b[2J\n one?" + "!" * 100))
    assert bc.fit_proposal(p) == ['"Pick [2J one?' + "!" * 47 + '" header: 13 -> 12 characters']

def test_a_question_that_is_not_text_is_named_by_a_question_mark():
    p = prop(q(header="Dependencies!", question=5))
    assert bc.fit_proposal(p) == ['"?" header: 13 -> 12 characters']

@pytest.mark.parametrize("obj", [None, [], {"batches": "x"},
                                 {"batches": [None, {"id": 3, "decisions": "x"},
                                              {"decisions": [None, 5, {"questions": "x"},
                                                             {"questions": [None, {"options": "x"},
                                                                            {"header": 5, "options": [None, {"label": 7, "description": None}]}]}]}]}])
def test_malformed_shapes_are_skipped(obj):
    assert bc.fit_proposal(obj) == []

def test_deeply_nested_unknown_keys_are_never_walked():
    deep = cur = {}
    for _ in range(5000):
        cur["x"] = {}
        cur = cur["x"]
    p = prop({**q(header="Dependencies!"), "extra": deep})
    p["batches"][0]["extra"] = deep
    first(p)["options"][0]["evil"] = deep
    assert bc.fit_proposal(p) == ['"Which store?" header: 13 -> 12 characters']
