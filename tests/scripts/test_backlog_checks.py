# tests/scripts/test_backlog_checks.py
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

OPT = [{"label": "Keep (Recommended)", "description": "no break"}, {"label": "Drop", "description": "smaller"}]
Q0 = {"question": "Keep the v1 API?", "header": "API", "options": OPT, "multiSelect": False}
DEFAULTS = {"state": "planned", "answers": {}, "lead": None, "agent": None, "worktree": None, "branch": None, "since": 0,
            "pr": None, "merged": False, "version": None, "reason": "", "ship_runs": 0, "questions": 0}

def bt(bid, issues, files, depends=(), decisions=()):
    return {"id": bid, "topic": "t" + bid[1:], "issues": list(issues), "files": list(files), "depends": list(depends), "decisions": list(decisions)}

def norm(*bs):
    return bc.check_proposal({"batches": list(bs)}, {1, 2, 3, 4})[0]

def test_questions():
    assert bc.check_question({"questions": [Q0, {**Q0, "question": "Other?", "multiSelect": True}]}) == []
    for q, err in [({"questions": []}, "questions: 1 to 4 entries"), ({"questions": [Q0] * 5}, "questions: 1 to 4 entries"),
                   ({"questions": [{**Q0, "header": "a much too long header"}]}, "q1 header: 1 to 12 characters"),
                   ({"questions": [{**Q0, "options": OPT[:1]}]}, "q1 options: 2 to 4 entries"),
                   ({"questions": [{**Q0, "question": "Keep?\x1b[2J"}]}, "q1 question: control character"),
                   ({"questions": [{**Q0, "options": [OPT[0], OPT[0]]}]}, "q1 options: duplicate label Keep (Recommended)"),
                   ({"questions": [{**Q0, "multiSelect": "yes"}]}, "q1 multiSelect: true or false"), ([], "not an object with questions")]:
        assert err in bc.check_question(q), err

def test_bare_question_is_accepted_and_stored_normalised():
    bare = {"question": "Keep the v1 API?", "header": "API", "options": OPT}
    assert bc.check_question(bare) == [] and bc.clean_question(bare) == {"questions": [bare]}
    assert "q1 header: 1 to 12 characters" in bc.check_question({**bare, "header": "a much too long header"})
    assert norm(bt("B1", [1], ["a.py"], decisions=[bare]))[0]["decisions"] == [{"questions": [bare]}]

def test_proposal_is_normalised():
    assert norm(bt("B1", [2, 1], ["./b.py", "a.py", "a.py"])) == [{**bt("B1", [1, 2], ["a.py", "b.py"]), **DEFAULTS}]

@pytest.mark.parametrize("bad,err", [
    ([bt("B1", [9], ["a.py"])], "B1: unknown issue #9"),
    ([bt("B1", [1], ["/etc/passwd"])], "B1: file '/etc/passwd' is not a plain relative path"),
    ([bt("B1", [1], ["src/../../x"])], "B1: file 'src/../../x' is not a plain relative path"),
    ([bt("B1", [1], ["a.py"], ["B7"])], "B1: depends on unknown batch B7"),
    ([bt("B1", [1], ["a.py"]), bt("B2", [1], ["b.py"])], "#1 is in B1 and B2"),
    ([bt("B1", [1], ["a.py"], ["B2"]), bt("B2", [2], ["b.py"], ["B1"])], "dependency cycle: B1 B2"),
    ([{**bt("B1", [1], ["a.py"]), "id": "X1"}], "batch 1: id must be B<n>"),
    ([{**bt("B1", [1], ["a.py"]), "topic": "Bad Topic!"}], "B1: topic must be lowercase words joined by -"),
    ([bt("B1", [1], ["a.py"], decisions=[{"questions": []}])], "B1 decision 1: questions: 1 to 4 entries"),
    ([], "batches: 1 to 20 entries")])
def test_one_error_rejects_the_whole_proposal(bad, err):
    batches, errors = bc.check_proposal({"batches": bad + ([bt("B9", [4], ["z.py"])] if bad else [])}, {1, 2, 3, 4})
    assert batches == [] and err in errors
    assert bc.check_proposal([], {1}) == ([], ["proposal: not an object with batches"])

def test_separate_merges_unordered_clashes_only():
    ids = lambda bs: [(b["id"], b["issues"], b["files"], b["depends"]) for b in bs]
    out = bc.separate(norm(bt("B1", [1], ["a.py"], decisions=[{"questions": [Q0]}]), bt("B2", [2], ["a.py", "b.py"]), bt("B3", [3], ["b.py"]),
                           bt("B4", [4], ["c.py"], ["B2"])))
    assert ids(out) == [("B1", [1, 2, 3], ["a.py", "b.py"], []), ("B4", [4], ["c.py"], ["B1"])] and out[0]["decisions"] == [{"questions": [Q0]}]
    chain = norm(bt("B1", [1], ["a.py"]), bt("B2", [2], ["b.py"], ["B1"]), bt("B3", [3], ["a.py"], ["B2"]))
    assert bc.separate(chain) == chain

def test_proposal_from_takes_the_last_block_with_batches():
    text = 'x\n```json\n{"batches": [1]}\n```\nStatus: DONE\n```json\n{"status": "DONE", "batches": []}\n```'
    assert bc.proposal_from(text) == {"status": "DONE", "batches": []}
    assert bc.proposal_from('```json\n{"status": "DONE"}\n```') is None and bc.proposal_from("```json\n" + "[" * 5000 + "\n```") is None

def test_decisions_are_rebuilt_from_validated_fields_only():
    deep = cur = {}
    for _ in range(5000):
        cur["x"] = {}
        cur = cur["x"]
    dirty = {"questions": [{**Q0, "extra": deep, "options": [{**o, "evil": deep} for o in OPT]}], "also": deep}
    out = norm(bt("B1", [1], ["a.py"], decisions=[dirty]))
    assert out[0]["decisions"] == [{"questions": [Q0]}]
    assert bc.clean_question(dirty) == {"questions": [Q0]}

@pytest.mark.parametrize("drop", [False, True])
def test_a_batch_without_files_is_rejected(drop):
    b = bt("B1", [1], [])
    if drop:
        del b["files"]
    assert bc.check_proposal({"batches": [b]}, {1}) == ([], ["B1: files must list at least one repo-relative file"])

def test_a_files_value_that_is_not_a_list_gets_one_error():
    assert bc.check_proposal({"batches": [{**bt("B1", [1], []), "files": "a.py"}]}, {1}) == ([], ["B1: files must be a list"])
