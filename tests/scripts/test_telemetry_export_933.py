"""`sl telemetry export` (#933): the backfill rebuilds contract lines from the existing ledgers."""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import telemetry  # noqa: E402
import telemetry_export  # noqa: E402

SINCE = date(2026, 11, 1)


def home() -> Path:
    return Path(os.environ["SUPERLITE_HOME"])


def jl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows), encoding="utf-8")


def rebuild(root, since=SINCE):
    lines = telemetry_export.rebuild(since, [root], home())
    for line in lines:
        assert telemetry.validate(line) == []
        assert line["backfill"] is True
    return lines


def of(lines, kind):
    return [x for x in lines if x["kind"] == kind]


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "proj"
    (r / ".superlite" / "runs").mkdir(parents=True)
    return r


def archive(root, name="20261102-101500-b1", **manifest):
    d = root / ".superlite" / "runs" / name
    d.mkdir(parents=True)
    jl(d / "run.json", [])
    (d / "run.json").write_text(json.dumps({"id": name, "batch": "B1", "branch": "feat/x", "plan": "/w/plans/p.md",
                                            "ended": "2026-11-02T11:00:00", **manifest}), encoding="utf-8")
    return d


def test_kind_agent_stop_export_history(root):
    jl(home() / "history.jsonl", [
        {"v": 1, "date": "2026-11-02", "run": "r1", "task": "T1", "model": "sonnet", "duration_s": 12.5,
         "tokens": {"in": 1, "out": 2, "cache_read": 3, "cache_write": 4}, "cost_usd": 0.25, "tool_calls": 7},
        {"v": 1, "date": "2026-10-01", "run": "r0", "task": "T9"},
    ])
    (line,) = of(rebuild(root), "agent_stop")
    assert line["t"] == "2026-11-02T00:00:00.000Z" and line["run"] == "r1"
    assert (line["task"], line["model"], line["duration_s"], line["cost_usd"], line["tool_calls"]) == ("T1", "sonnet", 12.5, 0.25, 7)
    assert line["tokens"] == {"in": 1, "out": 2, "cache_read": 3, "cache_write": 4}
    assert line["account"] is None and line["status"] is None


def test_kind_run_start_export_archive(root):
    d = archive(root)
    jl(d / "lint-log.jsonl", [{"time": "2026-11-02T10:15:00", "stable": 3}, {"time": "2026-11-02T10:20:00", "stable": 5}])
    (d / "build-report.json").write_text(json.dumps({"tasks": [{}] * 5}), encoding="utf-8")
    (line,) = of(rebuild(root), "run_start")
    assert line["run"] == "20261102-101500-b1" and line["plan"] == "p.md" and line["branch"] == "feat/x"
    assert line["tasks"] == 5 and line["mode"] is None
    assert line["t"] == datetime.fromisoformat("2026-11-02T10:15:00").astimezone().astimezone(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_kind_run_end_export_archive(root):
    d = archive(root)
    jl(d / "lint-log.jsonl", [{"time": "2026-11-02T10:15:00", "stable": 2}])
    (d / "build-report.json").write_text(json.dumps({
        "headline": {"wall_min": {"projected": 10, "actual": 2.5}, "cost_usd_agents": {"actual": 1.5},
                     "agents": {"actual": 4}},
        "critical_path": {"projected_min": 7},
        "quality": {"tests": {"passed": 9, "failed": 1}, "first_time_pass": 2, "rework_dispatches": 1},
        "tasks": [{}, {}]}), encoding="utf-8")
    (line,) = of(rebuild(root), "run_end")
    assert line["run"] == "20261102-101500-b1" and line["outcome"] == "done"
    assert (line["wall_s"], line["cost_usd"], line["tasks"], line["agents"]) == (150, 1.5, 2, 4)
    assert (line["tests_passed"], line["tests_failed"], line["first_time_pass"], line["fix_rounds"]) == (9, 1, 2, 1)
    assert (line["projected_min"], line["critical_path_min"], line["questions"]) == (10, 7, None)


def test_run_id_from_manifest(root):
    d = archive(root, run_id="20261102T101500Z-abc123")
    (d / "build-report.json").write_text("{}", encoding="utf-8")
    assert {x["run"] for x in rebuild(root) if x["kind"].startswith("run_")} == {"20261102T101500Z-abc123"}


def test_kind_dispatch_export_metrics(root):
    d = archive(root)
    ms = int(datetime(2026, 11, 2, 10, 30).timestamp() * 1000)
    jl(d / "metrics.jsonl", [
        {"ev": "launch", "t": ms, "agent_id": "a1", "type": "superlite:implementer", "model": "sonnet",
         "desc": "T4 secret words"},
        {"ev": "stop", "t": ms + 5, "agent_id": "a1", "type": "x", "last": "secret"},
    ])
    (line,) = of(rebuild(root), "dispatch")
    assert (line["agent_type"], line["model"], line["task"], line["run"]) == ("superlite:implementer", "sonnet", "T4", d.name)
    assert "secret" not in json.dumps(line) and line["label"] is None


def test_kind_tests_export_summary(root):
    d = archive(root)
    p = d / "test-summary-T2.json"
    p.write_text(json.dumps({"passed": 3, "failed": 1, "skipped": 2, "seconds": 1.5, "mode": "fast", "task": "T2",
                             "failures": ["a::b: boom"], "started": 1793613600}), encoding="utf-8")
    (line,) = of(rebuild(root), "tests")
    assert (line["mode"], line["passed"], line["failed"], line["skipped"], line["seconds"], line["task"]) == ("fast", 3, 1, 2, 1.5, "T2")
    assert "boom" not in json.dumps(line)


def test_kind_batch_export_costs(root):
    jl(root / ".superlite" / "batch-costs.jsonl", [
        {"v": 1, "row": "batch", "t": "2026-11-03T08:00:00Z", "batch": "B7", "end": "shipped", "pr": 12,
         "lead": {"model": "opus"}},
        {"v": 1, "row": "batch", "t": "2026-10-03T08:00:00Z", "batch": "B6", "end": "parked"},
    ])
    (line,) = of(rebuild(root), "batch")
    assert (line["t"], line["batch"], line["state"], line["lead_model"], line["pr"]) == (
        "2026-11-03T08:00:00.000Z", "B7", "shipped", "opus", 12)


def test_kind_feedback_export(root):
    jl(home() / "feedback.jsonl", [
        {"v": 1, "id": "x", "date": "2026-11-04T09:00:00Z", "kind": "bug", "text": "private words", "reason": "private"},
        {"v": 1, "id": "y", "date": "2026-09-04T09:00:00Z", "kind": "idea", "text": "old"},
    ])
    (line,) = of(rebuild(root), "feedback")
    assert line["t"] == "2026-11-04T09:00:00.000Z" and line["fkind"] == "bug" and line["reason"] is None
    assert "private" not in json.dumps(line)


def test_export_since_filters(root):
    jl(home() / "history.jsonl", [{"date": "2026-10-31", "task": "T1"}, {"date": "2026-11-01", "task": "T2"}])
    assert [x["task"] for x in rebuild(root)] == ["T2"]
    assert rebuild(root, date(2026, 11, 2)) == []


def test_export_sorted_by_t(root):
    jl(home() / "history.jsonl", [{"date": "2026-11-05", "task": "T1"}])
    jl(root / ".superlite" / "batch-costs.jsonl", [{"t": "2026-11-03T08:00:00Z", "batch": "B", "end": "done"}])
    ts = [x["t"] for x in rebuild(root)]
    assert ts == sorted(ts) and len(ts) == 2


def test_export_skips_bad_lines(root):
    jl(home() / "history.jsonl", ["not json", "[1]", {"date": "garbage"}, {"date": "2026-11-02", "task": "T1"}])
    jl(root / ".superlite" / "batch-costs.jsonl", ["{oops"])
    assert [x["task"] for x in rebuild(root)] == ["T1"]


def test_export_prints_lines(root, capsys):
    jl(home() / "history.jsonl", [{"date": "2026-11-02", "task": "T1"}])
    ns = telemetry_export.argparse.Namespace(since="2026-11-01", root=[str(root)], out=None)
    assert telemetry_export.main(ns) == 0
    (out,) = capsys.readouterr().out.splitlines()
    assert json.loads(out)["task"] == "T1"
    assert not (home() / "events.jsonl").exists()


def test_export_out_replaces_file(root, tmp_path):
    jl(home() / "history.jsonl", [{"date": "2026-11-02", "task": "T1"}])
    out = tmp_path / "o.jsonl"
    out.write_text("old\n", encoding="utf-8")
    ns = telemetry_export.argparse.Namespace(since="2026-11-01", root=[str(root)], out=str(out))
    assert telemetry_export.main(ns) == 0
    assert [json.loads(x)["task"] for x in out.read_text(encoding="utf-8").splitlines()] == ["T1"]


def test_export_bad_date_exit_2(root, capsys):
    with pytest.raises(SystemExit) as e:
        telemetry.main(["export", "--since", "2026-13-40", "--root", str(root)])
    assert e.value.code == 2
    ns = telemetry_export.argparse.Namespace(since="nope", root=[str(root)], out=None)
    assert telemetry_export.main(ns) == 2
