import sys
from test_backlog_run import bk, running, run, get  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief  # noqa: E402
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402
import pytest  # noqa: E402

TAIL = " [cut: sl backlog ship B1 notes prints the full text]"


@pytest.fixture(autouse=True)
def real_brief(monkeypatch):
    monkeypatch.setitem(sys.modules, "backlog_brief", backlog_brief)


def test_status_reason_and_no_change_examples():
    assert br.status_reason("Outcome\nStatus: BLOCKED merge denied: main runs it\n```json\n{}\n```", "Outcome") == "Status: BLOCKED merge denied: main runs it"
    assert br.status_reason("", "Status: BLOCKED - tui red") == "Status: BLOCKED - tui red"
    assert br.status_reason("", "") == "lead stopped"
    assert br.no_change_reason("Status: **DONE** no-change: duplicate of #12") == "duplicate of #12"
    assert br.no_change_reason("Status: DONE") is None


def test_wait_ends_a_no_change_batch(bk, capsys):
    wt = running(bk, issues=[7]); (wt / ".superlite" / "notes.md").write_text("Ruling: dup\n")
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE no-change: duplicate of #3"}
    rc, out = run(capsys, "wait", "--timeout", "0")
    lines = out.splitlines()
    assert rc == 0 and lines[0] == f"B1 no-change: duplicate of #3 summary={bk.sd / 'backlog' / 'B1.md'}" and "B1 OPEN #7" in lines
    b = get(bk, "B1")
    assert (b["state"], b["no_change"], b["open_issues"]) == ("shipped", "duplicate of #3", [7])
    assert (bk.sd / "backlog" / "B1.md").read_text().startswith("B1 no-change: #7\n")
    assert (bk.sd / "backlog" / "B1.notes.md").read_text() == "Ruling: dup\n"


def test_wait_parks_with_the_full_status_line(bk, capsys):
    running(bk); reason = "Status: BLOCKED " + "word " * 180
    bk.stops["W1"] = {"t": 2000, "last": reason[:160]}
    br.sys.modules["fleet_io"].report_text = lambda tr: "Outcome: BLOCKED\n" + reason + "\n```json\n{}\n```"
    bk.stops["W1"]["transcript"] = "/t.jsonl"
    out = run(capsys, "wait", "--timeout", "0")[1]
    assert get(bk, "B1")["reason"] == reason.strip()
    assert out.startswith("B1 parked: Status: BLOCKED word") and out.rstrip("\n").endswith(TAIL) and len(out) < 270


def test_shipped_line_counts_unverified_and_design(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", unverified=["app check (#5)"], kind="design")
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    lines = run(capsys, "wait", "--timeout", "0")[1].splitlines()
    assert lines[0] == f"B1 shipped PR #201 1.5.8 summary={bk.sd / 'backlog' / 'B1.md'} unverified=1 design: awaits plan approval"
    assert "B1 UNVERIFIED: app check (#5)" in lines


def test_status_shows_a_long_reason_below_the_table(bk):
    reason = "Status: BLOCKED merge denied. " + "detail " * 80
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [{"id": "B1", "issues": [1], "files": [], "state": "parked", "reason": reason},
                                                               {"id": "B2", "issues": [2], "files": [], "state": "shipped", "version": "1.0", "no_change": "dup of #1"}]}))
    lines = bs.status_lines(bs.load(bs.path(bk.root)))
    row = next(x for x in lines if x.startswith("B1 |"))
    assert len(row.split(" | ")[-1]) <= 40
    assert any(x.startswith("reason B1: Status: BLOCKED merge denied.") and x.endswith(TAIL) for x in lines)
    assert next(x for x in lines if x.startswith("B2 |")).endswith("| no-change")


def test_status_reason_bare_status_falls_back_to_last():
    assert br.status_reason("Outcome: merge denied\nStatus: BLOCKED", "B1 stop last") == "B1 stop last"
    assert br.status_reason("Status: **BLOCKED** -", "the last") == "the last"
    assert br.status_reason("Status: BLOCKED - tui red", "the last") == "Status: BLOCKED - tui red"


def test_no_change_batch_with_an_unmerged_branch_owes_cleanup(bk, capsys, monkeypatch):
    wt = running(bk, issues=[7], branch="superlite/b1-t")
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE no-change: dup of #3"}
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (1, "not fully merged") if cmd[:3] == ["git", "branch", "-d"] else (0, ""))
    run(capsys, "wait", "--timeout", "0")
    b = get(bk, "B1")
    assert b["state"] == "shipped" and "kept (not merged)" in b["cleanup_owed"]
    assert any("cleanup owed" in x for x in bs.status_lines(bs.load(bs.path(bk.root))))


def test_lagging_transcript_does_not_park_a_no_change_lead(bk, capsys, monkeypatch):
    running(bk, issues=[7])
    monkeypatch.setattr(br, "_now_ms", lambda: 50000)
    br.sys.modules["fleet_io"].report_text = lambda tr: ""
    br.sys.modules["fleet_io"].READ_MS = 10000
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE no-change: dup of #3", "transcript": "/t.jsonl"}
    run(capsys, "wait", "--timeout", "0")
    b = get(bk, "B1")
    assert (b["state"], b["no_change"]) == ("shipped", "dup of #3")


def test_quoted_no_change_line_before_a_final_blocked_parks(bk, capsys):
    running(bk, issues=[7])
    bk.stops["W1"] = {"t": 2000, "last": "x", "transcript": "/t.jsonl"}
    br.sys.modules["fleet_io"].report_text = lambda tr: "I quoted: Status: DONE no-change: dup\nStatus: BLOCKED merge denied\n"
    run(capsys, "wait", "--timeout", "0")
    b = get(bk, "B1")
    assert b["state"] == "parked" and not b.get("no_change")


def test_status_lines_strip_control_characters_from_a_park_reason(bk):
    reason = "Status: BLOCKED \x1b[2Jevil\x07 " + "detail " * 20
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [{"id": "B1", "issues": [1], "files": [], "state": "parked", "reason": reason}]}))
    lines = bs.status_lines(bs.load(bs.path(bk.root)))
    assert not any(ch in x for x in lines for ch in "\x1b\x07")
    short = "\x1b[2Jab"
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"reason": short}))
    assert not any("\x1b" in x for x in bs.status_lines(bs.load(bs.path(bk.root))))
