"""A dependency is kept only where the batches share a file or the triage gives a why; every kept one carries its reason (#742)."""
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

DROP = "depends: {} no longer waits for {}: no shared file and no reason"


def bt(bid, files, depends=()):
    return {"id": bid, "topic": "t", "issues": [int(bid[1:])], "files": list(files), "depends": list(depends), "decisions": []}


def check(*bs, backlog=frozenset()):
    out, errs = bc.check_proposal({"batches": list(bs)}, {int(b["id"][1:]) for b in bs}, backlog)
    assert errs == []
    return out


def test_depends_takes_ids_and_why_objects():
    out = check(bt("B1", ["a.py"]), bt("B2", ["b.py"]), bt("B3", ["c.py"], ["B1", {"id": "B2", "why": "  issue #3\tsays after\n#2 "}, {"id": "B2", "why": "x"}]))
    assert out[2]["depends"] == ["B1", "B2"] and out[2]["depends_why"] == {"B2": "issue #3 says after #2"}
    assert "depends_why" not in out[0]


def test_a_long_why_is_cut_at_a_whole_word():
    out = check(bt("B1", ["a.py"]), bt("B2", ["b.py"], [{"id": "B1", "why": "word " * 30}]))
    assert out[1]["depends_why"]["B1"] == ("word " * 16).strip() and bc.DEPENDS_WHY_MAX == 80


@pytest.mark.parametrize("bad", [[7], [{"why": "x"}], [{"id": "B1", "why": 3}], "B1"])
def test_a_bad_depends_entry_rejects(bad):
    b = bt("B2", ["b.py"])
    b["depends"] = bad
    out, errs = bc.check_proposal({"batches": [bt("B1", ["a.py"]), b]}, {1, 2})
    assert out == [] and any(e.startswith("B2: depends must be a list of batch ids") for e in errs)


def test_an_unknown_id_in_a_why_object_is_still_rejected():
    out, errs = bc.check_proposal({"batches": [bt("B1", ["a.py"], [{"id": "B7", "why": "x"}])]}, {1})
    assert out == [] and "B1: depends on unknown batch B7" in errs


def test_prune_keeps_shared_and_reasoned_and_drops_the_rest():
    out, lines = bc.prune_depends(check(bt("B1", ["a.py", "b.py"]), bt("B2", ["c.py"]), bt("B3", ["d.py"]),
                                        bt("B4", ["b.py", "a.py"], ["B1", {"id": "B2", "why": "issue #4 needs #2 first"}, "B3"])))
    assert out[3]["depends"] == ["B1", "B2"] and out[3]["depends_why"] == {"B1": "shares a.py (+1 more)", "B2": "issue #4 needs #2 first"}
    assert lines == [DROP.format("B4", "B3")]


def test_a_triage_why_wins_over_the_generated_one():
    out, lines = bc.prune_depends(check(bt("B1", ["a.py"]), bt("B2", ["a.py"], [{"id": "B1", "why": "issue #2 says after #1"}])))
    assert out[1]["depends_why"] == {"B1": "issue #2 says after #1"} and lines == []


def test_append_only_in_both_is_no_shared_file():
    out, lines = bc.prune_depends(check({**bt("B1", ["n.md"]), "append_only": ["n.md"]}, {**bt("B2", ["n.md"], ["B1"]), "append_only": ["n.md"]}))
    assert out[1]["depends"] == [] and "depends_why" not in out[1] and lines == [DROP.format("B2", "B1")]


def test_the_issue_round_keeps_only_the_file_orders():
    out, lines = bc.prune_depends(check(bt("B10", ["x.py"]), bt("B11", ["k.py"], ["B10"]), bt("B12", ["x.py"], ["B11"]), bt("B13", ["y.py"], ["B11"]),
                                        bt("B14", ["m.py"], ["B12", "B13"]), bt("B15", ["y.py"], ["B14"])))
    assert {b["id"]: b["depends"] for b in out} == {"B10": [], "B11": [], "B12": ["B10"], "B13": [], "B14": [], "B15": ["B13"]}
    assert out[2]["depends_why"] == {"B10": "shares x.py"} and out[5]["depends_why"] == {"B13": "shares y.py"}
    assert lines == [DROP.format("B11", "B10"), DROP.format("B12", "B11"), DROP.format("B13", "B11"), DROP.format("B14", "B12"),
                     DROP.format("B14", "B13"), DROP.format("B15", "B14"),
                     "depends: B12 waits for B10: shares x.py (the order the dropped dependencies held)",
                     "depends: B15 waits for B13: shares y.py (the order the dropped dependencies held)"]
    assert [b["id"] for b in bc.separate(out)] == ["B10", "B11", "B12", "B13", "B14", "B15"]


def test_a_backlog_batch_dependency_is_checked_against_its_files():
    run = {"id": "B5", "state": "running", "files": ["a.py"], "depends": []}
    out, lines = bc.prune_depends(check(bt("B1", ["a.py"], ["B5"]), bt("B2", ["b.py"], ["B5"]), backlog=frozenset({"B5"})), [run])
    assert out[0]["depends_why"] == {"B5": "shares a.py"} and out[1]["depends"] == [] and lines == [DROP.format("B2", "B5")]


def test_a_local_id_wins_over_a_backlog_id():
    out, lines = bc.prune_depends(check(bt("B1", ["a.py"]), bt("B2", ["b.py"], ["B1"]), backlog=frozenset({"B1"})),
                                  [{"id": "B1", "state": "running", "files": ["b.py"], "depends": []}])
    assert out[1]["depends"] == [] and lines == [DROP.format("B2", "B1")]


def test_prune_leaves_its_input_alone():
    bs_ = check(bt("B1", ["a.py"]), bt("B2", ["b.py"], ["B1"]))
    bc.prune_depends(bs_)
    assert bs_[1]["depends"] == ["B1"]


def test_separate_carries_the_reasons_through_a_merge():
    out, _ = bc.prune_depends(check(bt("B1", ["z.py"]), bt("B2", ["a.py", "z.py"], ["B1"]), bt("B3", ["a.py"]),
                                    bt("B4", ["q.py"], [{"id": "B3", "why": "issue #4 says after #3"}])))
    assert [(b["id"], b["depends"], b.get("depends_why")) for b in bc.separate(out)] == [
        ("B1", [], None), ("B2", ["B1"], {"B1": "shares z.py"}), ("B4", ["B2"], {"B2": "issue #4 says after #3"})]


def test_a_merge_keeps_the_first_reason_for_a_renamed_dependency():
    out, _ = bc.prune_depends(check(bt("B1", ["a.py"]), bt("B2", ["a.py"]),
                                    bt("B3", ["q.py"], [{"id": "B1", "why": "issue #3 after #1"}, {"id": "B2", "why": "issue #3 after #2"}])))
    assert [(b["id"], b["depends"], b.get("depends_why")) for b in bc.separate(out)] == [("B1", [], None), ("B3", ["B1"], {"B1": "issue #3 after #1"})]
