import pytest
from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401  bk is the CLI fixture
import backlog as bl
import backlog_state as bs

RESET = "; sl backlog plan --reset drops them and plans every open issue again (shipped batches stay)"
BUSY = "; --reset is refused too while a batch is running or needs_decision"
TWO = [{**BATCH, "issues": [1]}, {**BATCH, "id": "B2", "topic": "second", "issues": [2], "files": ["b.py"]}]


def _state(bk, bid, state):
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, bid).update({"state": state}))


def test_plan_names_reset_while_only_planned_or_parked_batches_are_open(bk, capsys):
    bk.batches = TWO
    assert cli(capsys, "plan")[0] == 0
    _state(bk, "B2", "parked")
    assert cli(capsys, "plan") == (2, "BLOCKED: backlog has open batches (B1 planned, B2 parked)" + RESET + "\n")
    assert cli(capsys, "plan", "--reset")[0] == 0
    assert [(b["id"], b["state"]) for b in load(bk)["batches"]] == [("B1", "planned"), ("B2", "planned")]


@pytest.mark.parametrize("state", ["running", "needs_decision"])
def test_plan_refusal_says_reset_is_refused_with_a_live_batch(bk, capsys, state):
    bk.batches = TWO
    cli(capsys, "plan")
    _state(bk, "B1", state)
    want = (2, f"BLOCKED: backlog has open batches (B1 {state}, B2 planned)" + BUSY + "\n")
    assert cli(capsys, "plan") == want
    assert cli(capsys, "plan", "--reset") == want
    assert [b["state"] for b in load(bk)["batches"]] == [state, "planned"]


def test_open_refusal_lists_every_open_batch():
    open_ = [{"id": "B4", "state": "planned"}, {"id": "B5", "state": "needs_decision"}]
    assert bl.open_refusal(open_, open_[1:]) == "BLOCKED: backlog has open batches (B4 planned, B5 needs_decision)" + BUSY
    assert bl.open_refusal(open_[:1], []) == "BLOCKED: backlog has open batches (B4 planned)" + RESET


def test_plan_help_describes_reset(capsys):
    with pytest.raises(SystemExit):
        bl.main(["plan", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert ("drop the planned and parked batches and plan every open issue again; shipped batches stay; "
            "refused while a batch is running or needs_decision") in out


def test_status_names_plan_when_nothing_is_open(bk, capsys):
    assert cli(capsys, "status") == (0, "backlog: 0 batches, 0 running, 0 shipped, ship not approved\nnext: sl backlog plan\n")
    cli(capsys, "plan")
    assert "next: sl backlog plan" not in cli(capsys, "status")[1]
    _state(bk, "B1", "shipped")
    assert cli(capsys, "status")[1].splitlines()[-1] == "next: sl backlog plan"
    _state(bk, "B1", "parked")
    assert "next: sl backlog plan" not in cli(capsys, "status")[1]
