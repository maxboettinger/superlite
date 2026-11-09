import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import backlog_checks as bc  # noqa: E402

REC = " (Recommended)"
FULL = "Refuse, name the lost env and the resume command first"


def one(label, desc="trade-off"):
    o = {"label": label} if desc is None else {"label": label, "description": desc}
    return {"questions": [{"question": "Q?", "header": "H", "options": [o, {"label": "Drop", "description": "b"}]}]}


def opt(q):
    return q["questions"][0]["options"][0]


def test_a_suffixed_label_is_cut_at_a_word_and_its_full_text_leads_the_description():
    q = one(FULL + REC)
    assert bc.fit_question(q) == ['"Q?" option 1 label: 68 -> 54 characters']
    assert opt(q) == {"label": "Refuse, name the lost env and the resume" + REC, "description": FULL + ". trade-off"}
    assert bc.check_question(q) == []


def test_the_issue_labels_end_at_a_whole_word():
    for full, cut in (("Allow writes under .superlite/ and plans; name the guard file", "Allow writes under .superlite/ and plans; name"),
                      ("Try the project-package prefix first, then the plain module name", "Try the project-package prefix first, then the")):
        q = one(full + REC)
        bc.fit_question(q)
        assert opt(q) == {"label": cut + REC, "description": full + ". trade-off"}


def test_trailing_punctuation_is_dropped_and_a_cut_on_a_blank_keeps_the_last_word():
    q = one("x" * 50 + " abcdef; ghijkl")
    assert bc.fit_question(q) == ['"Q?" option 1 label: 65 -> 57 characters'] and opt(q)["label"] == "x" * 50 + " abcdef"
    q = one("w" * 30 + " " + "x" * 29 + " tail")
    assert bc.fit_question(q) == ['"Q?" option 1 label: 65 -> 60 characters'] and opt(q)["label"] == "w" * 30 + " " + "x" * 29


def test_one_long_word_is_cut_inside_it_and_still_moved():
    q = one("k" * 70 + REC)
    assert bc.fit_question(q) == ['"Q?" option 1 label: 84 -> 60 characters']
    assert opt(q) == {"label": "k" * 46 + REC, "description": "k" * 70 + ". trade-off"}


def test_description_absent_blank_or_after_a_sentence():
    full = "Keep the old v1 flag for one more minor release, then remove it in 1.6"
    cut = "Keep the old v1 flag for one more minor release, then remove"
    q = one(full, desc=None)
    assert bc.fit_question(q) == ['"Q?" option 1 label: 70 -> 60 characters'] and opt(q) == {"label": cut, "description": full}
    q = one(full, desc="  ")
    bc.fit_question(q)
    assert opt(q)["description"] == full
    q = one(full + ".", desc="  no break")
    bc.fit_question(q)
    assert opt(q) == {"label": cut, "description": full + ". no break"}


def test_a_moved_label_that_overflows_the_description_is_cut_to_200_and_named():
    q = one("k" * 70 + REC, desc="d" * 190)
    assert bc.fit_question(q) == ['"Q?" option 1 label: 84 -> 60 characters', '"Q?" option 1 description: 262 -> 200 characters']
    assert opt(q)["description"] == ("k" * 70 + ". " + "d" * 190)[:200]


def test_a_label_at_the_limit_and_a_non_string_description_stay():
    q = one("y" * 60)
    assert bc.fit_question(q) == [] and opt(q) == {"label": "y" * 60, "description": "trade-off"}
    q = one("k" * 70, desc=5)
    assert bc.fit_question(q) == ['"Q?" option 1 label: 70 -> 60 characters'] and opt(q) == {"label": "k" * 60, "description": 5}
    assert bc.check_question(q) == ["q1 options description: description 0 to 200 characters"]


def test_plan_proposals_get_the_same_word_cut():
    p = {"batches": [{"decisions": [one(FULL + REC)]}]}
    assert bc.fit_proposal(p) == ['"Q?" option 1 label: 68 -> 54 characters']
    assert opt(p["batches"][0]["decisions"][0])["description"] == FULL + ". trade-off"


def test_triage_brief_names_the_suffix_and_the_word_cut():
    t = bb.triage_brief([{"number": 1, "title": "t"}], {"repo": "r", "max_batches": 2})
    assert "option label at most 60 characters including a ` (Recommended)` suffix" in t
    assert "(a label at its last whole word, its full text moved to the front of its description)" in t
