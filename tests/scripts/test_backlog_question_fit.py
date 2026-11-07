import copy
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402


def opts():
    return [{"label": "Keep (Recommended)", "description": "a"}, {"label": "Drop", "description": "b"}]


def test_fit_question_cuts_header_label_description():
    q = {"questions": [{"question": "Keep the v1 API?", "header": "Compatibility",
                        "options": [{"label": "k" * 70 + " (Recommended)", "description": "x"},
                                    {"label": "Drop", "description": "y" * 250}]}]}
    assert bc.fit_question(q) == ['"Keep the v1 API?" header: 13 -> 12 characters',
                                  '"Keep the v1 API?" option 1 label: 84 -> 60 characters',
                                  '"Keep the v1 API?" option 2 description: 250 -> 200 characters']
    assert q["questions"][0]["options"][0]["label"] == "k" * 46 + " (Recommended)"
    assert bc.check_question(q) == []


def test_fit_question_cuts_a_bare_question_in_place():
    q = {"question": "Q?", "header": "Dependencies!", "options": opts()}
    assert bc.fit_question(q) == ['"Q?" header: 13 -> 12 characters']
    assert q["header"] == "Dependencies"


def test_fit_question_never_cuts_the_question():
    q = {"questions": [{"question": "a" * 301, "header": "H", "options": opts()}]}
    assert bc.fit_question(q) == []
    assert q["questions"][0]["question"] == "a" * 301
    assert "q1 question: 1 to 300 characters" in " ".join(bc.check_question(q))


def test_fit_question_ignores_other_shapes():
    for v in (None, [], "x", {"questions": "x"}, {"questions": [None, {"header": 5, "options": "x"}]}):
        assert bc.fit_question(v) == []


def test_fit_proposal_is_fit_question_per_decision():
    def d(a, b):
        return {"header": "x", "questions": [{"question": a, "header": "Compatibility", "options": opts()},
                                             {"question": b, "header": "Compatibility", "options": opts()}]}
    d1, d2 = d("One?", "Two?"), d("Three?", "Four?")
    p = {"batches": [{"decisions": [copy.deepcopy(d1)]}, {"decisions": [copy.deepcopy(d2)]}]}
    expect = bc.fit_question(copy.deepcopy(d1)) + bc.fit_question(copy.deepcopy(d2))
    assert expect and bc.fit_proposal(p) == expect


def test_cut_lines_prefix_and_cap():
    assert bc.cut_lines(['"Q?" header: 13 -> 12 characters'], "B1 ") == ['B1 shortened: "Q?" header: 13 -> 12 characters']
    assert bc.cut_lines([f"n{i}" for i in range(7)]) == [f"shortened: n{i}" for i in range(5)] + ["shortened: 2 more"]
    assert bc.cut_lines([]) == []
    assert bc.cut_lines(list("abcde")) == [f"shortened: {c}" for c in "abcde"]
