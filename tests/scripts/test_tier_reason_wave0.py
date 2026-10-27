"""T7: tier reasons on the TIERS line, `**Wave0:** none` header."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, pt, run
from test_stable_split import DISPATCH
from test_routing import plan, task
from test_wave0 import PY, WAVE0, plan as w0plan

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import plan_tools  # noqa: E402
import routing  # noqa: E402


def test_tier_note_reasons():
    assert routing.tier_note({"critical_path": True, "mechanical": True}, "sonnet", "haiku", False) == "critical path"
    assert routing.tier_note({"critical_path": False, "mechanical": False}, "sonnet", "haiku", False) == "not mechanical"
    assert routing.tier_note({"critical_path": False, "mechanical": True}, "sonnet", "haiku", True) == "history gate"
    assert routing.tier_note({"critical_path": True, "mechanical": True}, "haiku", "haiku", False) is None
    assert routing.tier_note({}, "sonnet", None, False) is None


def test_lint_prints_planned_tier_reason(tmp_path):
    t1 = task("T1", True, 1.5).replace("**Est. time:**", "**Model:** haiku\n**Est. time:**")  # alone: critical path
    p = plan(tmp_path, [t1], [])
    cp = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    assert "T1=sonnet (planned haiku: critical path)" in cp.out, cp.out
    t1 = task("T1", True, 1.5).replace("**Est. time:**", "**Model:** haiku\n**Est. time:**")
    p = plan(tmp_path, [t1, task("T9", False, 6)], [], name="b.md")  # T1 has slack: haiku as planned, no reason
    cp = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    assert "T1=haiku" in cp.out and "planned" not in cp.out, cp.out


def _w0(tmp_path, header):
    p = w0plan(tmp_path, "**Tech stack:** Python", "x", PY)
    if header:
        p.write_text(p.read_text(encoding="utf-8").replace("**Goal:**", header + "\n**Goal:**", 1), encoding="utf-8")
    return p


def test_wave0_none_no_brief_no_start_first(tmp_path):
    p = _w0(tmp_path, "**Wave0:** None")
    assert plan_tools.wave0_off(p) is True
    cp = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    assert "START FIRST" not in cp.out
    assert not (tmp_path / ".superlite" / "briefs" / "wave0.md").exists()
    q = _w0(tmp_path, "")
    assert plan_tools.wave0_off(q) is False


def test_wave0_none_dispatch_no_t0(tmp_path):
    p = _w0(tmp_path, "**Wave0:** none")
    run(WAVE0, "--plan", p, cwd=tmp_path)  # a brief exists, the header still wins
    ledger = tmp_path / "l.md"
    ledger.write_text("- start\n", encoding="utf-8")
    out = run(DISPATCH, "--plan", p, "--pool", tmp_path / "pool.json", "--ledger", ledger, cwd=tmp_path).out
    assert "T0" not in out
    assert dispatch.skip_t0(ledger, p) is True
    assert dispatch.skip_t0(ledger) is False


def test_skip_ruling_still_works(tmp_path):
    f = tmp_path / "l.md"
    f.write_text("- Ruling: skip T0 - x - y\n", encoding="utf-8")
    p = _w0(tmp_path, "")
    assert dispatch.skip_t0(f, p) is True


def test_wave0_header_not_read_from_task_body(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("# P\n\n### T1 x\n**Wave0:** none\n", encoding="utf-8")
    assert plan_tools.wave0_off(p) is False
