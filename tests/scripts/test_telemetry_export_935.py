"""`sl telemetry export`: exported run lines carry mode, orchestrator and fleet from run.json (#935)."""
import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import telemetry  # noqa: E402
import telemetry_export  # noqa: E402


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "proj"
    (r / ".superlite" / "runs").mkdir(parents=True)
    return r


def archive(root, **manifest):
    d = root / ".superlite" / "runs" / "20261102-101500-b1"
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"id": d.name, "branch": "feat/x", "plan": "/w/plans/p.md",
                                            "ended": "2026-11-02T11:00:00", **manifest}), encoding="utf-8")
    (d / "lint-log.jsonl").write_text(json.dumps({"time": "2026-11-02T10:15:00", "stable": 2}) + "\n", encoding="utf-8")
    return d


def run_lines(root):
    lines = telemetry_export.rebuild(date(2026, 11, 1), [root], Path(os.environ["SUPERLITE_HOME"]))
    out = {x["kind"]: x for x in lines if x["kind"] in ("run_start", "run_end")}
    for x in out.values():
        assert telemetry.validate(x) == [] and x["backfill"] is True
    return out["run_start"], out["run_end"]


def test_kind_run_end_export_carries_run_tags(root):
    archive(root, batch=None, mode="feature", orchestrator="ai", fleet=True)
    for line in run_lines(root):
        assert (line["mode"], line["orchestrator"], line["fleet"]) == ("feature", "ai", True)


def test_kind_run_end_export_old_lead_archive_is_backlog(root):
    archive(root, batch="B7")
    for line in run_lines(root):
        assert (line["mode"], line["orchestrator"], line["fleet"]) == ("backlog", None, None)


def test_kind_run_end_export_old_archive_nulls(root):
    archive(root, batch=None)
    for line in run_lines(root):
        assert (line["mode"], line["orchestrator"], line["fleet"]) == (None, None, None)


def test_kind_run_end_export_bad_values_dropped(root):
    archive(root, batch=None, mode=7, orchestrator="robot", fleet="on")
    for line in run_lines(root):
        assert (line["mode"], line["orchestrator"], line["fleet"]) == (None, None, None)
