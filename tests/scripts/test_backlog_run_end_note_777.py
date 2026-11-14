import os
import sys

import pytest

from backlog_fixtures import batch as b
from test_backlog_run_end_590 import HEAD, end, put, rk  # noqa: F401
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402

T = "2026-11-14T10:00:00Z"


def NOTE(f, n):
    return f"run end: standing note from {f} ({T}, {n}) still goes into every later lead brief; sl backlog start --note /dev/null clears it"


def store(rk, text, file="/x/note.md"):
    bs.update(bs.path(rk.root), lambda d: d.update(note={"text": text, "file": file, "time": T}))


def test_note_follows_fleet_off(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    store(rk, "a\nb")
    assert end(rk) == [HEAD + "fleet off (stopped workers cleared: 1)", NOTE("/x/note.md", "2 lines")]


def test_note_follows_live_workers(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W2": {"state": "busy"}}
    store(rk, "only")
    assert end(rk) == [HEAD + "live workers W2 still run: sl fleet off stops and clears them", NOTE("/x/note.md", "1 line")]


def test_note_follows_failed_off(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    rk.result = 3
    store(rk, "a\nb")
    assert end(rk) == [HEAD + "sl fleet off failed (3): run it again", NOTE("/x/note.md", "2 lines")]


def test_no_note_keeps_one_line(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    assert end(rk) == [HEAD + "fleet off (stopped workers cleared: 1)"]
    store(rk, "")
    assert end(rk) == [HEAD + "fleet off (stopped workers cleared: 1)"]


def test_note_missing_fields_still_one_line(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    bs.update(bs.path(rk.root), lambda d: d.update(note={"text": "x"}))
    out = end(rk)
    assert len(out) == 2 and out[1].startswith("run end: standing note from None (None, 1 line)")


def test_no_run_end_no_note_line(rk):
    rk.workers = {"W1": {"state": "stopped"}}
    put(rk, b("B1", ["a"], "shipped"), b("B2", ["b"], "planned"))
    store(rk, "a")
    assert end(rk) == []
    put(rk, b("B1", ["a"], "shipped"))
    store(rk, "a")
    rk.on = False
    assert end(rk) == []


def test_control_characters_become_spaces(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    store(rk, "a", file="/x/a\nb.md")
    assert "standing note from /x/a b.md (" in end(rk)[1]


@pytest.mark.skipif(os.name == "nt", reason="no /dev/null")
def test_dev_null_clears_the_note(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    store(rk, "a")
    assert bs.read_note("/dev/null") == ""
    bs.update(bs.path(rk.root), lambda d: bs.set_note(d, "", "/dev/null", T))
    assert end(rk) == [HEAD + "fleet off (stopped workers cleared: 1)"]


def test_wait_prints_the_note_line(rk, capsys, monkeypatch):
    rk.workers = {"W1": {"state": "stopped"}}
    put(rk, b("B1", ["a"], "shipped"))
    store(rk, "a\nb")
    assert br.main(["wait", "--timeout", "0"]) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [HEAD + "fleet off (stopped workers cleared: 1)", NOTE("/x/note.md", "2 lines")]
