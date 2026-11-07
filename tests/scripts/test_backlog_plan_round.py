import sys
from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog as bl  # noqa: E402
import backlog_state as bs  # noqa: E402

APPROVAL = {"by": "AskUserQuestion", "time": "t"}


def approve(bk):
    bs.update(bs.path(bk.root), lambda d: d.__setitem__("approved_ship", dict(APPROVAL)))


def questions(capsys):
    import json
    return json.loads(cli(capsys, "decide", "--print")[1])["questions"]


def test_reset_plan_clears_ship_approval(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    approve(bk)
    rc, out = cli(capsys, "plan", "--reset")
    assert rc == 0 and load(bk)["approved_ship"] is None
    assert out.splitlines()[0].endswith("ship not approved")
    assert questions(capsys)[0]["question"] == bs.SHIP_Q


def test_next_round_plan_clears_ship_approval(bk, capsys):
    cli(capsys, "plan")
    approve(bk)
    bs.update(bs.path(bk.root), lambda d: d["batches"][0].__setitem__("state", "shipped"))
    bk.batches = [{**BATCH, "issues": [2]}]
    assert cli(capsys, "plan")[0] == 0
    assert load(bk)["approved_ship"] is None


def test_rejected_plan_keeps_ship_approval(bk, capsys):
    cli(capsys, "plan")
    approve(bk)
    bk.batches = [{**BATCH, "issues": [99]}]
    assert cli(capsys, "plan", "--reset")[0] == 3
    assert load(bk)["approved_ship"] == APPROVAL


def test_left_out_issue_in_outside_with_triage_reason(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert load(bk)["outside"] == [{"number": 3, "title": "Three", "author": "eve"},
                                   {"number": 2, "title": "Two", "reason": "not planned (triage)"}]
    assert "not planned (triage): #2" in out.splitlines()


def test_left_out_at_cap_reason(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "MAX_BATCHES", 1)
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan")[0] == 0
    assert {"number": 2, "title": "Two", "reason": "not planned (cap)"} in load(bk)["outside"]


def test_issues_past_limit_listed(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "ISSUE_LIMIT", 2)
    bk.batches = [{**BATCH, "issues": [1, 2]}]
    assert cli(capsys, "plan")[0] == 0
    assert "#3" not in (bk.sd / "briefs" / "triage.md").read_text()
    assert load(bk)["outside"] == [{"number": 3, "title": "Three", "reason": "not triaged (2 cap)"}]
    assert not any("#3" in q["question"] for q in questions(capsys))


def test_skipped_issue_past_limit_not_listed(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "ISSUE_LIMIT", 2)
    cli(capsys, "skip", "3")
    bk.batches = [{**BATCH, "issues": [1, 2]}]
    assert cli(capsys, "plan")[0] == 0
    assert load(bk)["outside"] == []


def test_status_lists_left_out(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    cli(capsys, "plan")
    assert "not planned (triage): #2" in cli(capsys, "status")[1].splitlines()
    assert not any("#2" in q["question"] for q in questions(capsys))


def test_next_plan_replaces_left_out(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    cli(capsys, "plan")
    bk.batches = [BATCH]
    assert cli(capsys, "plan", "--reset")[0] == 0
    assert not any("reason" in o for o in load(bk)["outside"])


def test_cap_reason_uses_proposal_batch_count_after_separate(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "MAX_BATCHES", 2)
    bk.vis = "PRIVATE"
    bk.batches = [{**BATCH, "issues": [1]}, {**BATCH, "id": "B2", "issues": [2]}]
    rc, _ = cli(capsys, "plan")
    d = load(bk)
    assert rc == 0 and len(d["batches"]) == 1
    assert {"number": 3, "title": "Three", "reason": "not planned (cap)"} in d["outside"]
