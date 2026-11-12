"""backlog_run answer takes the one answer rule; _shipped runs without lead or worktree (#586)."""
import json, sys
from backlog_fixtures import Q
from test_backlog_run import bk, run, running, get, put, b  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402

KEY = "Keep the v1 API?"


def waiting(bk, answers):
    wt = running(bk)
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    (wt / ".superlite" / "question.json").write_text(json.dumps(Q))
    f = bk.root / "a.json"
    f.write_text(json.dumps({"answers": answers}))
    return wt, f


def test_answer_label_plus_note_reaches_lead(bk, capsys):
    wt, f = waiting(bk, {KEY: {"label": "Keep", "note": "additive only, old runs unchanged"}})
    want = "Keep; note: additive only, old runs unchanged"
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert json.loads((wt / ".superlite" / "answer-1.json").read_text())["answers"] == {KEY: want}
    assert get(bk, "B1")["answers"] == {KEY: want}


def test_answer_long_free_text(bk, capsys):
    wt, f = waiting(bk, {KEY: "z" * 1200})
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert get(bk, "B1")["answers"] == {KEY: "z" * 1200}


def test_answer_bad_label_names_the_rule(bk, capsys):
    wt, f = waiting(bk, {KEY: {"label": "Later"}})
    assert run(capsys, "answer", "B1", "--file", str(f)) == (
        2, f'BLOCKED: bad answer for {KEY}: label "Later" is not one of: Keep, Drop\n')
    assert not (wt / ".superlite" / "answer-1.json").exists()
    assert get(bk, "B1")["state"] == "needs_decision"


def test_answer_control_characters(bk, capsys):
    wt, f = waiting(bk, {"K?": "x\x1b[2J"})
    rc, out = run(capsys, "answer", "B1", "--file", str(f))
    assert rc == 2 and out.startswith("BLOCKED: bad answer for K?: an answer is an option label")
    assert "\x1b" not in out


def test_wait_ships_without_worktree_field(bk, capsys):
    put(bk, b("B1", ["a.py"], "running", pr=7))
    out = br._shipped(bs.path(bk.root), bk.sd, bk.root, get(bk, "B1"), None)
    assert out[0].startswith("B1 shipped PR #7")
    assert not [c for c in bk.calls if c[0] == "stop"]
    assert not [c for c in bk.calls if c[0] == "run"]
