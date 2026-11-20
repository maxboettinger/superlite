"""`status.lead_progress` (#906): one progress line per live lead, read from the lead's own run folder."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import status  # noqa: E402

PLAN = """# Plan

**Goal:** g

### T1 one
**Owns:** src/a.py, tests/test_a.py
**Tests:** fast

### T2 two
**Owns:** src/b.py, tests/test_b.py
**Tests:** fast

### T3 three
**Owns:** src/c.py, tests/test_c.py
**Tests:** fast
"""


def lead(tmp_path, **extra):
    b = tmp_path / "b"
    sd = b / ".superlite"
    sd.mkdir(parents=True)
    w = {"role": "lead", "state": "busy", "lead_sd": str(sd), "worktree": str(b)}
    w.update(extra)
    return b, sd, w


def test_tasks_and_busy_workers(tmp_path):
    b, sd, w = lead(tmp_path, sent=1)
    (sd / "plan.md").write_text(PLAN, encoding="utf-8")
    (sd / "progress.md").write_text("- commit T1 abc1234 first\n", encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"state": "busy", "task": "T2"}}}), encoding="utf-8")
    assert status.lead_progress("W4", w) == (
        f"lead W4 {b}: plan {sd}/plan.md (3 tasks); tasks: checkpointed 1: T1; running 1: T2 (W1); open 1: T3; "
        "workers busy 1; question: none")


def test_empty_run(tmp_path):
    b, sd, w = lead(tmp_path, state="ready")
    assert status.lead_progress("W4", w) == f"lead W4 {b}: plan: none yet; workers busy 0; question: none"


def test_open_question(tmp_path):
    b, sd, w = lead(tmp_path, sent=1)
    (sd / "question.json").write_text("{}", encoding="utf-8")
    assert status.lead_progress("W4", w).endswith(f"question: open {sd}/question.json")


def test_question_answered_is_none(tmp_path):
    b, sd, w = lead(tmp_path)
    q = sd / "question.json"
    q.write_text("{}", encoding="utf-8")
    old = time.time() - 100
    os.utime(q, (old, old))
    w["sent"] = int(time.time() * 1000)
    assert status.lead_progress("W4", w).endswith("question: none")


def test_corrupt_plan_never_raises(tmp_path, monkeypatch):
    b, sd, w = lead(tmp_path)
    (sd / "plan.md").write_text(PLAN, encoding="utf-8")
    import plan_tools

    def boom(path):
        raise plan_tools.PlanError("bad")
    monkeypatch.setattr(plan_tools.Plan, "load", staticmethod(boom))
    line = status.lead_progress("W4", w)
    assert f"plan {sd}/plan.md (unreadable)" in line
    assert "tasks:" not in line


def test_record_plan_fallback(tmp_path):
    b, sd, w = lead(tmp_path)
    p = tmp_path / "elsewhere.md"
    p.write_text(PLAN, encoding="utf-8")
    w["plan"] = str(p)
    assert f"plan {p} (3 tasks)" in status.lead_progress("W4", w)


def test_not_a_live_lead(tmp_path):
    b, sd, w = lead(tmp_path)
    assert status.lead_progress("W1", dict(w, role="implementer")) is None
    assert status.lead_progress("W4", dict(w, state="stopped")) is None
    assert status.lead_progress("W4", dict(w, lead_sd=str(tmp_path / "nope"))) is None


def test_unexpected_error_is_a_line(tmp_path, monkeypatch):
    b, sd, w = lead(tmp_path)

    def boom(sd):
        raise RuntimeError("x")
    monkeypatch.setattr(status, "clean_state", boom)
    assert status.lead_progress("W4", w) == f"lead W4 {b}: progress unreadable (RuntimeError)"
