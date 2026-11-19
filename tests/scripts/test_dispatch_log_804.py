"""#804: dispatch.run logs the tasks it hands to fresh (primed) agents in .superlite/dispatch-log.jsonl."""
from __future__ import annotations

import json
import sys

from test_dispatch_evict import pool_file
from test_plan_tools import SCRIPTS
from test_routing import mixed

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import orchestrator  # noqa: E402


def entries(sd):
    f = sd / "dispatch-log.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def test_log_fresh_examples(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    lines = [("T1", "agent=W2"), ("T3,T4", "fresh tier=sonnet agent=superlite:implementer"),
             ("T5", "fresh tier=haiku agent=superlite:implementer-haiku")]
    assert dispatch.log_fresh(sd, lines, now="2026-11-12T11:01:20") == ["T3", "T4", "T5"]
    assert entries(sd) == [{"time": "2026-11-12T11:01:20", "fresh": ["T3", "T4", "T5"]}]
    assert (sd / "dispatch-log.jsonl").read_text(encoding="utf-8").endswith("}\n")
    other = tmp_path / "o" / ".superlite"
    other.mkdir(parents=True)
    assert dispatch.log_fresh(other, [("T1", "agent=W2"), ("T2,T6", "poll W1,W3")]) == []
    assert not (other / "dispatch-log.jsonl").exists()


def test_run_logs_fresh_lines(tmp_path):
    pf = pool_file(tmp_path, [])
    lines, _ = dispatch.run(mixed(tmp_path), pf, tmp_path / ".superlite" / "progress.md", gate=False)
    fresh = [t for tasks, d in lines if d.startswith("fresh") for t in tasks.split(",")]
    assert fresh
    (e,) = entries(tmp_path / ".superlite")
    assert e["fresh"] == fresh and len(fresh) >= 2


def test_run_outside_superlite_writes_nothing(tmp_path):
    d = tmp_path / "pool"
    d.mkdir()
    pf = d / "pool.json"
    pf.write_text(json.dumps({"agents": []}), encoding="utf-8")
    dispatch.run(mixed(tmp_path), pf, d / "progress.md", gate=False)
    assert not (d / "dispatch-log.jsonl").exists()


def test_log_fresh_oserror_quiet(tmp_path):
    sd = tmp_path / "missing" / ".superlite"  # folder does not exist: the append fails
    assert dispatch.log_fresh(sd, [("T3,T4", "fresh tier=sonnet")]) == ["T3", "T4"]


def test_orchestrator_end_moves_dispatch_log(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "dispatch-log.jsonl").write_text('{"time": "t", "fresh": ["T1"]}\n', encoding="utf-8")
    (sd / "lint-log.jsonl").write_text("{}\n", encoding="utf-8")
    orchestrator.end(sd)
    (dest,) = [p for p in (sd / "runs").iterdir() if p.is_dir()]
    assert (dest / "dispatch-log.jsonl").is_file() and not (sd / "dispatch-log.jsonl").exists()


def test_docstring_names_plan_tools_lint():
    doc = dispatch.__doc__
    assert "rerun sl plan_tools lint --stable" in doc and "rerun sl lint --stable" not in doc
