"""One batch end to end: park, ship, snapshot and main round write the rows `report --batches` prints (#680)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402
import batch_cost  # noqa: E402
import fleet_io  # noqa: E402
import main_cost  # noqa: E402
import report  # noqa: E402
from _fixtures import FIXTURES  # noqa: E402
from backlog_fixtures import batch as mk  # noqa: E402

FIX = FIXTURES / "batch_cost_680"


def jdump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    root = tmp_path / "main"
    sd = root / ".superlite"
    wt = root / ".claude" / "worktrees" / "superlite-b1-t"
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    lead_tr = cfg / "projects" / fleet_io.project_dir(wt) / "lead.jsonl"  # where a real lead session stores it
    lead_tr.parent.mkdir(parents=True)
    worker_tr = tmp_path / "worker.jsonl"
    shutil.copy(FIX / "lead.jsonl", lead_tr)
    shutil.copy(FIX / "worker.jsonl", worker_tr)
    jdump(sd / "fleet.json", {"on": False, "workers": {"W3": {"role": "lead", "tier": "opus"}}})
    (sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": 1, "agent_id": "W3", "transcript": str(lead_tr)}) + "\n", encoding="utf-8")
    wsd = wt / ".superlite"
    jdump(wsd / "fleet.json", {"workers": {"W1": {"role": "implementer"}}})
    (wsd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": 2, "agent_id": "W1", "type": "fleet:implementer", "transcript": str(worker_tr)}) + "\n", encoding="utf-8")
    jdump(wsd / "fleet" / "reports" / "T1.json", {"label": "T1", "role": "implementer", "status": "DONE"})
    jdump(wsd / "fleet" / "reports" / "FR1.json", {"label": "FR1", "role": "final-reviewer", "status": "APPROVED"})
    jdump(wsd / "test-summary-20261112T214640.json", {"mode": "full", "seconds": 120, "passed": 12, "failed": 0})
    p = bs.path(root)
    parked = mk("B1", ["a.py"], "running", lead="W3", worktree=str(wt), branch="superlite/b1-t", ship_reds=1, ship_runs=0)
    bs.update(p, lambda d: d.update({"repo": "o/r", "round": ["B1"], "batches": [parked]}))
    monkeypatch.setattr(br, "_stop", lambda sd_, lead: None)
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: (0, "shipped"))
    return type("W", (), {"root": root, "sd": sd, "wt": wt, "p": p, "tmp": tmp_path, "batch": parked})


def rows(w):
    return batch_cost.read_rows(w.root)


def test_park_then_ship_two_rows_report_latest(world):
    w = world
    br._park(w.p, w.sd, "o/r", dict(w.batch), "tui red", [])
    shipped = {**w.batch, "ship_reds": 0, "pr": 201, "version": "1.5.8"}
    br._shipped(w.p, w.sd, w.root, shipped, w.wt, push=True)
    rs = rows(w)
    assert [(r["row"], r["end"]) for r in rs] == [("batch", "parked"), ("batch", "shipped")]
    first, second = rs
    assert first["grade"]["letter"] == "B" and second["grade"]["letter"] == "A"
    lead = second["lead"]
    assert lead["turns"] == 6 and lead["wakeups"] == {"report": 1, "busy": 0, "timeout": 1, "test_wait": 1, "lock": 0, "prompt": 1}
    assert lead["blocked_wait_s"] == 420.0
    assert lead["tokens"]["thinking"] == 30 and {"wait", "read", "dispatch", "text"} <= set(lead["kinds"])
    assert second["workers"]["implementer"]["n"] == 1 and second["workers"]["implementer"]["tokens"]["thinking"] == 50
    assert second["tests"]["full"] == 1 and second["pr"] == 201
    text = report.batches_text(rs)
    assert "B1 shipped grade A (0)" in text and "B1 parked" not in text


def test_worktree_gone_uses_snapshot(world):
    w = world
    assert batch_cost.save_snapshot(w.root, "B1", w.wt).is_file()
    shutil.rmtree(w.wt)
    br._shipped(w.p, w.sd, w.root, {**w.batch, "pr": 201}, None, push=False)
    row = rows(w)[-1]
    assert row["end"] == "shipped" and row["workers"]["implementer"]["n"] == 1
    assert row["grade"]["tasks"] == 1 and row["tests"]["full"] == 1


def test_a_failing_record_never_changes_the_outcome(world, monkeypatch):
    w = world
    monkeypatch.setattr(batch_cost, "record", lambda *a: 1 / 0)
    out = []
    br._park(w.p, w.sd, "o/r", dict(w.batch), "tui red", out)
    assert out == ["B1 parked: tui red"] and bs.batch(bs.load(w.p), "B1")["state"] == "parked"


def test_main_row_from_fixture(world):
    w = world
    cfg = w.tmp / "cfg"
    tr = cfg / "projects" / fleet_io.project_dir(w.root) / "sess-main.jsonl"
    tr.parent.mkdir(parents=True)
    shutil.copy(FIX / "main.jsonl", tr)
    env = {"CLAUDE_CONFIG_DIR": str(cfg), "SUPERLITE_SESSION_ID": "sess-main"}
    assert main_cost.note_session(w.root, env) == "sess-main"
    assert main_cost.note_session(w.root, env) == "sess-main"
    assert len(bs.load(w.p)["main_sessions"]) == 1
    row = main_cost.record_main(w.root, env)
    assert row and row["turns"] == 3 and row["unmeasured"] == [] and row["round"] == ["B1"]
    assert {"plan", "wait", "text"} <= set(row["kinds"]) and row["tokens"]["thinking"] == 30
    assert main_cost.record_main(w.root, env) is None
    mains = [r for r in rows(w) if r["row"] == "main"]
    assert len(mains) == 1
    assert "main B1:" in report.batches_text(rows(w))
