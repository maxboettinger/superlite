# tests/scripts/test_backlog_status_b86.py
import sys
from backlog_fixtures import batch
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

CAP = "not planned (cap)"


def test_left_out_skips_issues_in_batches():
    d = {"outside": [{"number": 5, "title": "t", "reason": CAP}], "batches": [batch("B5", ["a.py"], state="shipped")]}
    assert bs.left_out_lines(d) == []


def test_rounds_and_keys_and_cap_hint():
    d = {"max_batches": 4, "batches": [], "outside": [{"number": 2, "reason": CAP, "rounds": 3}, {"number": 3, "reason": CAP},
                                                   {"number": "PIX-4", "reason": "not planned (triage: needs design)"}]}
    assert bs.left_out_lines(d) == [f"{CAP}: #2 (3 rounds) #3", "not planned (triage: needs design): PIX-4",
                                    "cap: a plan round holds at most 4 batches (sl backlog plan --max-batches N raises it, up to 20); capped issues rank first in the next round"]


def test_cap_hint_defaults_to_7():
    for extra in ({}, {"max_batches": True}):
        d = {**extra, "batches": [], "outside": [{"number": 2, "reason": CAP}]}
        assert "at most 7 batches" in bs.left_out_lines(d)[-1]


def test_rounds_bool_or_one_not_shown():
    for r in (True, 1):
        assert bs.left_out_lines({"outside": [{"number": 2, "reason": CAP, "rounds": r}]})[0] == f"{CAP}: #2"


def test_triage_cap_hint():
    d = {"outside": [{"number": 2, "reason": "not triaged (200 cap)"}, {"number": 3, "reason": "not triaged (200 cap)"}]}
    assert bs.left_out_lines(d) == ["not triaged (200 cap): #2 #3",
                                    "cap: a plan round triages only the first 200 open issues; the rest rank first in the next round"]


def test_status_row_jira_keys():
    d = {"batches": [batch("B1", ["a.py"], state="shipped", issues=["PIX-1"], version="1.0", open_issues=["PIX-1"])], "outside": []}
    out = "\n".join(bs.status_lines(d))
    assert "| PIX-1 |" in out and "1.0 OPEN PIX-1" in out


def test_worker_reason_text_does_not_trigger_cap_hints():
    d = {"outside": [{"number": 2, "reason": "not planned (triage: see planned (cap) and not triaged (x cap))"}]}
    assert bs.left_out_lines(d) == ["not planned (triage: see planned (cap) and not triaged (x cap)): #2"]


def test_skip_issue_refusal_drops_hash_for_jira_key():
    import pytest
    d = {"batches": [batch("B1", ["a.py"], state="running", issues=["PIX-2"])], "outside": [], "skipped": []}
    with pytest.raises(ValueError) as e:
        bs.skip_issue(d, "PIX-2")
    assert str(e.value).startswith("PIX-2 is in B1") and "#" not in str(e.value)


def test_triage_cap_hint_uses_k_once_per_k():
    d = {"outside": [{"number": 2, "reason": "not triaged (2 cap)"}, {"number": 3, "reason": "not triaged (2 cap)"}]}
    assert [x for x in bs.left_out_lines(d) if x.startswith("cap:")] == [
        "cap: a plan round triages only the first 2 open issues; the rest rank first in the next round"]
