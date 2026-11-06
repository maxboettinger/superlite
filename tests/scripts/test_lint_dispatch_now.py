"""lint --stable: DISPATCH NOW names startable tasks only; the freeze keys on dispatch, not on being listed."""
from __future__ import annotations

import json

from test_plan_tools import make_plan, pt

PROD = "f(x: int) -> int"


def two(tmp_path, produces=PROD, edges=(("T1", "T2"),), extra=()):
    return make_plan(tmp_path, [{"id": "T1", "time": 2, "produces": produces}, {"id": "T2", "time": 2}, *extra], edges)


def ledger(tmp_path, text):
    d = tmp_path / ".superlite"
    d.mkdir(exist_ok=True)
    (d / "progress.md").write_text("# Progress ledger\n\n" + text, encoding="utf-8")


def lint(p):
    return pt("lint", "--stable", "--plan", p)


def line(cp, prefix):
    return next((x for x in cp.out.splitlines() if x.startswith(prefix)), "")


def test_waiting_task_not_in_dispatch_now(tmp_path):
    cp = lint(two(tmp_path))
    assert "DISPATCH NOW: T1" in cp.out and "DISPATCH NOW: T1 T2" not in cp.out
    assert "STABLE: T1 T2" in cp.out
    then = line(cp, "THEN LOG")
    assert "T1" in then and "T2" not in then


def test_ready_after_commit(tmp_path):
    ledger(tmp_path, "- commit T1 abc1234567 task t1\n")
    cp = lint(two(tmp_path))
    assert "DISPATCH NOW: T2" in cp.out


def test_send_before_edit_ready_only(tmp_path):
    p = two(tmp_path, extra=[{"id": "T3", "time": 9}])
    cp = lint(p)
    send = line(cp, "SEND BEFORE ANY PLAN EDIT")
    assert "T1" in send and "T2" not in send, cp.out


def test_pending_field_ready_only(tmp_path):
    lint(two(tmp_path))
    rec = [json.loads(x) for x in (tmp_path / ".superlite" / "lint-log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rec[-1]["pending"] == ["T1"]


def test_draft_not_dispatched(tmp_path):
    p = make_plan(tmp_path, [{"id": "T1", "time": 2}, {"id": "T2", "time": 2}])
    p.write_text(p.read_text(encoding="utf-8").replace("### T2 task t2 · Complexity 3 (O-1) · Est. context 40k\n",
                                                       "### T2 task t2 · Complexity 3 (O-1) · Est. context 40k\n**Status:** draft\n"),
                 encoding="utf-8")
    cp = lint(p)
    assert "DISPATCH NOW: T1" in cp.out and "T2" not in line(cp, "DISPATCH NOW")


def test_listed_never_sent_not_frozen(tmp_path):
    lint(two(tmp_path))
    cp = lint(two(tmp_path, produces="f(x: str) -> int"))
    assert "FROZEN" not in cp.out, cp.out


def test_sent_task_still_frozen(tmp_path):
    lint(two(tmp_path))
    ledger(tmp_path, "- unblocked: dispatched T1 at 10:00:00; waiting on fixes: none\n")
    cp = lint(two(tmp_path, produces="f(x: str) -> int"))
    assert "FROZEN: T1 interface changed after dispatch" in cp.out


def test_finish_no_false_never_dispatched(tmp_path):
    import sys
    from test_run_scripts import SCRIPTS
    sys.path.insert(0, str(SCRIPTS))
    import finish
    p = two(tmp_path)
    lint(p)
    ledger(tmp_path, "- unblocked: dispatched T1 at 10:00:00; waiting on fixes: none\n")
    lint(p)
    out = finish.unblocked_report(tmp_path / ".superlite" / "progress.md", tmp_path / ".superlite" / "lint-log.jsonl")
    assert out.startswith("unblocked: yes"), out


def test_start_first_when_all_stable_wait(tmp_path):
    p = two(tmp_path)
    base = lint(p)
    assert "START FIRST" in base.out, base.out
    for f in (tmp_path / ".superlite" / "briefs").glob("wave0.md"):
        f.unlink()
    ledger(tmp_path, "- unblocked: dispatched T1 at 10:00:00; waiting on fixes: none\n")
    cp = lint(p)
    assert "DISPATCH NOW: none" in cp.out
    assert "START FIRST" in cp.out, cp.out


def test_hard_edge_waits_despite_consumes(tmp_path):
    p = make_plan(tmp_path, [{"id": "T1", "time": 2, "produces": PROD}, {"id": "T2", "time": 2, "consumes": PROD}], ())
    p.write_text(p.read_text(encoding="utf-8").replace("flowchart LR\n", "flowchart LR\n  T1 -->|hard| T2\n"), encoding="utf-8")
    ledger(tmp_path, "- commit T0 abc1234567 skeleton\n")
    cp = lint(p)
    assert "DISPATCH NOW: T1" in cp.out and "DISPATCH NOW: T1 T2" not in cp.out, cp.out
