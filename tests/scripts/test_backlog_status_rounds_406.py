"""backlog status: shipped batches of earlier plan rounds collapse to one count line; --all lists them (#406)."""
import sys

import pytest
from backlog_fixtures import APPROVED, batch as b
from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401  bk is the CLI fixture
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog as bl  # noqa: E402
import backlog_state as bs  # noqa: E402

COUNT = "earlier rounds: {} shipped (sl backlog status --all lists them)"
HEADER = "batch | issues | state | lead | PR | next"
HEAD = "backlog o/r: {} batches, {} running, {} shipped, ship approved (AskUserQuestion 2026-11-05T10:00:00Z)"


def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), "approved_ship": APPROVED, **kw}


def shipped(bid, **kw):
    n = bid[1:]
    return b(bid, [f"{bid}.py"], "shipped", pr=100 + int(n), version=f"1.5.{n}", lead=f"W{n}", **kw)


def test_round_record_keeps_its_batches_and_counts_the_rest():
    d = data(shipped("B1"), shipped("B2"), shipped("B3"), b("B4", ["d.py"], "running", lead="W9"), b("B5", ["e.py"]),
             round=["B3", "B4", "B5"])
    assert bs.status_lines(d) == [HEAD.format(5, 1, 3), COUNT.format(2), HEADER,
                                  "B3 | #3 | shipped | W3 | #103 | 1.5.3",
                                  "B4 | #4 | running | W9 | - | sl backlog wait",
                                  "B5 | #5 | planned | - | - | start"]


def test_all_lists_every_batch_without_the_count_line():
    d = data(shipped("B1"), shipped("B2"), b("B3", ["c.py"]), round=["B3"])
    assert bs.status_lines(d, all_=True) == [HEAD.format(3, 0, 2), HEADER, "B1 | #1 | shipped | W1 | #101 | 1.5.1",
                                             "B2 | #2 | shipped | W2 | #102 | 1.5.2", "B3 | #3 | planned | - | - | start"]
    assert bs.status_lines(d)[1:] == [COUNT.format(2), HEADER, "B3 | #3 | planned | - | - | start"]


def test_a_batch_not_shipped_is_listed_outside_the_round():
    d = data(shipped("B1"), b("B2", ["b.py"], "parked", reason="hold"), round=[])
    assert bs.status_lines(d)[1:] == [COUNT.format(1), HEADER, "B2 | #2 | parked | - | - | hold"]


def test_no_row_left_prints_no_table_and_keeps_left_out_lines():
    d = data(shipped("B1"), shipped("B2"), round=["B9"], outside=[{"number": 7, "title": "x", "reason": "not planned (cap)"}])
    assert bs.status_lines(d) == [HEAD.format(2, 0, 2), COUNT.format(2), "not planned (cap): #7"]


def test_without_a_round_record_titles_pick_the_current_round():
    d = data(shipped("B1"), shipped("B2"), shipped("B3"), b("B4", ["d.py"], "running", lead="W9"),
             titles={"3": "Three", "4": "Four", "8": "Eight"})
    assert bs.status_lines(d)[1:] == [COUNT.format(2), HEADER, "B3 | #3 | shipped | W3 | #103 | 1.5.3",
                                      "B4 | #4 | running | W9 | - | sl backlog wait"]


def test_without_a_round_record_or_titles_every_batch_is_listed():
    d = data(shipped("B1"), b("B2", ["b.py"]))
    assert bs.status_lines(d)[1:] == [HEADER, "B1 | #1 | shipped | W1 | #101 | 1.5.1", "B2 | #2 | planned | - | - | start"]


def test_in_round_reads_jira_keys_and_round_ids():
    d = data(titles={"PIX-1": "x"})
    assert bs.in_round(d, shipped("B1", issues=["PIX-1"])) and not bs.in_round(d, shipped("B2", issues=["PIX-2"]))
    r = {**d, "round": ["B2"]}
    assert bs.in_round(r, shipped("B2", issues=["PIX-2"])) and not bs.in_round(r, shipped("B1", issues=["PIX-1"]))
    assert bs.in_round(d, b("B3", ["c.py"], "needs_decision"))


def ship_b1(bk):
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "shipped", "pr": 201, "version": "1.5.8"}))


def test_plan_records_its_round_and_counts_earlier_shipped(bk, capsys):
    assert cli(capsys, "plan")[0] == 0 and load(bk)["round"] == ["B1"]
    ship_b1(bk)
    rc, out = cli(capsys, "plan")
    assert rc == 0 and load(bk)["round"] == ["B2"]
    assert out.splitlines()[1:4] == [COUNT.format(1), HEADER, "B2 | #1 #2 | planned | - | - | start"]
    assert cli(capsys, "status")[1].splitlines()[1:4] == [COUNT.format(1), HEADER, "B2 | #1 #2 | planned | - | - | start"]
    rc, out = cli(capsys, "status", "--all")
    assert rc == 0 and "earlier rounds" not in out
    assert out.splitlines()[1:4] == [HEADER, "B1 | #1 #2 | shipped | - | #201 | 1.5.8", "B2 | #1 #2 | planned | - | - | start"]


def test_reset_starts_a_new_round(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    ship_b1(bk)
    assert cli(capsys, "plan")[0] == 0
    rc, out = cli(capsys, "plan", "--reset")
    assert rc == 0 and load(bk)["round"] == ["B2"] and [x["id"] for x in load(bk)["batches"]] == ["B1", "B2"]
    assert out.splitlines()[1] == COUNT.format(1)


def test_a_finished_round_stays_listed_until_the_next_plan(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    ship_b1(bk)
    rc, out = cli(capsys, "status")
    assert rc == 0 and "earlier rounds" not in out and out.endswith("next: sl backlog plan\n")
    assert out.splitlines()[1:3] == [HEADER, "B1 | #1 #2 | shipped | - | #201 | 1.5.8"]


def test_status_help_names_all(capsys):
    with pytest.raises(SystemExit):
        bl.main(["status", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "--all" in out and "earlier plan rounds" in out
