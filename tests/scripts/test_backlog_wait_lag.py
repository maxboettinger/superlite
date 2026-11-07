# tests/scripts/test_backlog_wait_lag.py
import sys
import pytest
from test_backlog_run import bk, put, get, run, running  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402

LAST = "Outcome: BLOCKED, tui red Status: BLOCKED"
REC = {"t": 2000, "last": LAST, "transcript": "/x/t.jsonl"}


def fake(monkeypatch, text, read_ms=10000):
    fio = sys.modules["fleet_io"]
    if callable(text):
        monkeypatch.setattr(fio, "report_text", text, raising=False)
    else:
        monkeypatch.setattr(fio, "report_text", lambda t: text, raising=False)
    monkeypatch.setattr(fio, "READ_MS", read_ms, raising=False)


def texts(bk):
    return [c for c in bk.calls if c[0] == "text"]


def waits_quietly(bk, capsys):
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    x = get(bk, "B1")
    assert x["state"] == "running" and not x.get("reprompted")
    assert not texts(bk) and not any(c[0] in ("stop", "release") for c in bk.calls)


def test_empty_transcript_waits_inside_the_window(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, "")
    waits_quietly(bk, capsys)


def test_behind_transcript_waits_inside_the_window(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, "Working on T2.")
    waits_quietly(bk, capsys)


def test_flushed_transcript_parks_on_the_next_round(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, "")
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    fake(monkeypatch, "Outcome: BLOCKED\n\nStatus: BLOCKED")
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: " + LAST + "\n")


def test_window_over_parks_transcript_unread(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, "")
    monkeypatch.setattr(br, "_now_ms", lambda: 12000)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: " + LAST + " (transcript unread)\n")
    assert get(bk, "B1")["reason"] == LAST + " (transcript unread)"
    assert not texts(bk) and ("release", "B1") in bk.calls and ("stop", ["W1"]) in bk.calls


def test_window_over_without_status_reprompts_as_today(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "PONG", "transcript": "/x/t.jsonl"}; fake(monkeypatch, "")
    monkeypatch.setattr(br, "_now_ms", lambda: 12000)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["reprompted"] is True and len(texts(bk)) == 1


def test_read_ms_comes_from_fleet_io(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, "", read_ms=2000)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: " + LAST + " (transcript unread)\n")


def test_needs_decision_text_is_no_lag(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION", "transcript": "/x/t.jsonl"}
    fake(monkeypatch, "Status: NEEDS_DECISION")
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: Status: NEEDS_DECISION\n")


def test_cut_needs_decision_lags(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION", "transcript": "/x/t.jsonl"}
    fake(monkeypatch, "Working.")
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["state"] == "running"


def test_report_text_error_reads_as_empty(bk, capsys, monkeypatch):
    def boom(t):
        raise OSError("gone")
    running(bk); bk.stops["W1"] = dict(REC); fake(monkeypatch, boom)
    waits_quietly(bk, capsys)


def test_no_transcript_is_unchanged(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "Status: BLOCKED"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: Status: BLOCKED\n")


@pytest.mark.parametrize("text,last,want", [
    ("", "x", True), ("Status: DONE", "", False), ("work", "Status: BLOCKED", True),
    ("work", "PONG", False), ("work", "Status: NEEDS_DECISION", True)])
def test_lags_table(text, last, want):
    assert br._lags(text, last) is want
