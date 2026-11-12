# tests/scripts/test_backlog_append_only_602.py
import sys
from backlog_fixtures import batch
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402
import backlog_run  # noqa: E402
import backlog_state  # noqa: E402


def _bt(**kw):
    return {"batches": [{"id": "B1", "topic": "t", "issues": [1], "files": ["x.py"], "depends": [], "decisions": [], **kw}]}


def _sb(bid, files, depends=(), **kw):
    return {"id": bid, "issues": [int(bid[1:])], "files": files, "depends": list(depends), "decisions": [], **kw}


def test_serial_files_drops_files_both_append():
    a = {"files": ["a.md", "x.py"], "append_only": ["a.md"]}
    assert bc.serial_files(a, {"files": ["a.md"], "append_only": ["a.md"]}) == []
    assert bc.serial_files(a, {"files": ["a.md", "x.py"]}) == ["a.md", "x.py"]


def test_serial_files_without_append_only_is_the_plain_intersection():
    assert bc.serial_files({"files": ["b.py", "a.py"]}, {"files": ["a.py", "b.py", "c.py"]}) == ["a.py", "b.py"]


def test_appended_files_needs_both_sides():
    a = {"files": ["a.md", "x.py"], "append_only": ["a.md"]}
    assert bc.appended_files(a, {"files": ["a.md", "x.py"], "append_only": ["a.md"]}) == ["a.md"]
    assert bc.appended_files({"files": ["a.md"], "append_only": ["a.md"]}, {"files": ["a.md"]}) == []


def test_check_proposal_keeps_append_only():
    out, errs = bc.check_proposal(_bt(append_only=["a.md"]), {1})
    assert errs == [] and out[0]["files"] == ["a.md", "x.py"] and out[0]["append_only"] == ["a.md"]


def test_check_proposal_omits_an_empty_append_only():
    for extra in ({}, {"append_only": []}):
        out, errs = bc.check_proposal(_bt(**extra), {1})
        assert errs == [] and "append_only" not in out[0]


def test_check_proposal_rejects_bad_append_only():
    assert "B1: append_only must be a list" in bc.check_proposal(_bt(append_only="a.md"), {1})[1]
    assert "B1: append_only file '/etc/x' is not a plain relative path" in bc.check_proposal(_bt(append_only=["/etc/x"]), {1})[1]


def test_separate_keeps_batches_that_share_only_append_only_files():
    out = bc.separate([_sb("B1", ["a.md", "x.py"], append_only=["a.md"]), _sb("B2", ["a.md", "y.py"], append_only=["a.md"])])
    assert [x["id"] for x in out] == ["B1", "B2"] and out[1]["depends"] == []


def test_separate_merge_drops_a_rewritten_file_from_append_only():
    out = bc.separate([_sb("B1", ["a.md", "s.md"], append_only=["a.md", "s.md"]), _sb("B2", ["s.md", "x.py"])])
    assert len(out) == 1 and out[0]["id"] == "B1"
    assert out[0]["files"] == ["a.md", "s.md", "x.py"] and out[0]["append_only"] == ["a.md"]


def test_separate_merge_without_append_only_files_has_no_key():
    out = bc.separate([_sb("B1", ["s.md"], append_only=["s.md"]), _sb("B2", ["s.md"])])
    assert len(out) == 1 and "append_only" not in out[0]


def _data():
    return {"batches": [batch("B1", ["a.md"], "running", append_only=["a.md"]),
                        batch("B2", ["a.md", "y.py"], append_only=["a.md"]), batch("B3", ["a.md"])]}


def test_startable_skips_only_a_rewriting_batch():
    assert backlog_state.startable(_data(), cap=3) == ["B2"]


def test_pick_refuses_only_the_rewriting_batch():
    assert backlog_run._pick(_data(), ["B2", "B3"], 3, {}) == (["B2"], ["B3 shares files with running B1"])
