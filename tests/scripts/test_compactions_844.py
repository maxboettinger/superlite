"""#844: compact_boundary entries counted per main and lead session: metrics, the batch and main cost rows, sl report."""
from __future__ import annotations

import importlib
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402
import report  # noqa: E402
from test_batch_cost_680 import WAKE0, _fake_grade, _fake_snapshot  # noqa: E402
from test_coordinator_run_scope import session_with_design  # noqa: E402
from test_main_cost_680 import abc, env, mc, root  # noqa: E402,F401
from test_routing import mech_plan  # noqa: E402

T0 = 1794520000.0


def stamp(off):
    return datetime.fromtimestamp(T0 + off, timezone.utc).isoformat().replace("+00:00", "Z")


def turn(mid, off):
    return {"type": "assistant", "timestamp": stamp(off),
            "message": {"id": mid, "model": "claude-opus-4-8", "content": [{"type": "text", "text": "x"}],
                        "usage": {"input_tokens": 2, "cache_read_input_tokens": 300, "output_tokens": 30}}}


def boundary(off, pre, uid, side=False, trigger="auto", ts=None):
    return {"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted", "uuid": uid,
            "isSidechain": side, "timestamp": ts or stamp(off),
            "compactMetadata": {"trigger": trigger, "preTokens": pre, "postTokens": 30000}}


TWO = [turn("m1", 0), boundary(10, 367994, "u1"), turn("m2", 20), boundary(30, 150000, "u2", trigger="manual"),
       turn("m3", 40), boundary(35, 999999, "u3", side=True)]


def write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return path


def test_compaction_reads_one_boundary_entry():
    assert metrics.compaction(boundary(10, 367994, "u1")) == {"t": T0 + 10, "pre_tokens": 367994, "trigger": "auto"}
    assert metrics.compaction(turn("m1", 0)) is None
    assert metrics.compaction({"type": "system", "subtype": "other"}) is None
    assert metrics.compaction({"type": "system", "subtype": "compact_boundary"}) == {"t": None, "pre_tokens": 0, "trigger": None}
    for bad in ("9", True, -5, 2.5, None):
        e = {"type": "system", "subtype": "compact_boundary", "compactMetadata": {"preTokens": bad, "trigger": 3}}
        assert metrics.compaction(e) == {"t": None, "pre_tokens": 0, "trigger": None}
    assert metrics.compaction({"type": "system", "subtype": "compact_boundary", "compactMetadata": "x"})["pre_tokens"] == 0


def test_session_usage_counts_two_compactions(tmp_path):
    p = write(tmp_path / "t.jsonl", TWO + [boundary(10, 367994, "u1")])  # a repeated uuid counts once
    u = metrics.session_usage(p)
    assert u["compactions"] == 2 and u["pre_tokens"] == 367994 and u["compaction_tokens"] == [367994, 150000]
    assert u["turns"] == 3
    s = metrics.session_usage(p, sidechain=True)
    assert s["compactions"] == 3 and s["pre_tokens"] == 999999


def test_session_usage_window_untimed_and_empty(tmp_path):
    untimed = {"type": "system", "subtype": "compact_boundary", "uuid": "u4", "compactMetadata": {"preTokens": 5}}
    p = write(tmp_path / "t.jsonl", TWO + [untimed])
    w = metrics.session_usage(p, since=T0 + 15, until=T0 + 40)
    assert w["compactions"] == 1 and w["pre_tokens"] == 150000 and w["compaction_tokens"] == [150000]
    assert metrics.session_usage(p, since=T0 + 30, until=T0 + 30)["compactions"] == 1  # inclusive edges
    assert metrics.session_usage(p)["compactions"] == 3  # the untimed one counts only unwindowed
    e = metrics.session_usage(write(tmp_path / "e.jsonl", [turn("m1", 0)]))
    assert (e["compactions"], e["pre_tokens"], e["compaction_tokens"]) == (0, 0, [])
    gone = metrics.session_usage(tmp_path / "gone.jsonl")
    assert (gone["compactions"], gone["pre_tokens"], gone["compaction_tokens"]) == (0, 0, [])


def test_coordinator_record_counts_run_and_session(tmp_path):
    tr = write(tmp_path / "main.jsonl", TWO)
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "metrics.jsonl").write_text(json.dumps({"session_transcript": str(tr)}) + "\n")
    whole = metrics.coordinator_record(sl, agents=[])
    assert whole["scope"] == "session" and whole["compactions"] == 2 and whole["pre_tokens"] == 367994
    assert whole["compaction_tokens"] == [367994, 150000]
    assert whole["session"]["compactions"] == 2 and whole["session"]["pre_tokens"] == 367994
    run = metrics.coordinator_record(sl, agents=[{"first_abs": T0 + 25}])
    assert run["scope"] == "run" and run["compactions"] == 1 and run["pre_tokens"] == 150000
    assert run["compaction_tokens"] == [150000] and run["session"]["compactions"] == 2


@pytest.fixture
def bcr(monkeypatch):
    """batch_cost with fake batch_waits and batch_grade and the real metrics.session_usage."""
    w = types.ModuleType("batch_waits")
    w.lead_kind = lambda blocks: "wait"
    w.waits = lambda p: {"wakeups": dict(WAKE0), "blocked_wait_s": 0.0}
    g = types.ModuleType("batch_grade")
    g.snapshot, g.grade = _fake_snapshot, _fake_grade
    monkeypatch.setitem(sys.modules, "batch_waits", w)
    monkeypatch.setitem(sys.modules, "batch_grade", g)
    monkeypatch.delitem(sys.modules, "batch_cost", raising=False)
    mod = importlib.import_module("batch_cost")
    yield mod
    sys.modules.pop("batch_cost", None)


def _lead_root(tmp_path, stops):
    r = tmp_path / "main"
    sd = r / ".superlite"
    sd.mkdir(parents=True)
    (sd / "metrics.jsonl").write_text("".join(json.dumps({"ev": "stop", "t": 1000, "agent_id": wid, "transcript": str(p)}) + "\n"
                                              for wid, p in stops))
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W3": {"role": "lead", "tier": "opus"},
                                                           "W4": {"role": "lead", "tier": "sonnet"}}}))
    return r


def test_batch_row_lead_counts_two_compactions(bcr, tmp_path):
    a = write(tmp_path / "t" / "a.jsonl", TWO)
    row = bcr.build_row(_lead_root(tmp_path, [("W3", a)]), {"id": "B1", "lead": "W3"}, "shipped")
    assert row["lead"]["compactions"] == 2 and row["lead"]["pre_tokens"] == 367994
    assert row["leads"][0]["compactions"] == 2 and row["leads"][0]["pre_tokens"] == 367994


def test_batch_row_sums_leads_and_keeps_the_largest(bcr, tmp_path):
    a = write(tmp_path / "t" / "a.jsonl", TWO)
    b = write(tmp_path / "t" / "b.jsonl", [turn("n1", 100), boundary(110, 400000, "v1")])
    batch = {"id": "B1", "lead": "W4", "leads": [{"id": "W3", "phase": "plan"}, {"id": "W4", "phase": "build"}]}
    row = bcr.build_row(_lead_root(tmp_path, [("W3", a), ("W4", b)]), batch, "shipped")
    assert row["lead"]["compactions"] == 3 and row["lead"]["pre_tokens"] == 400000
    assert [(x["compactions"], x["pre_tokens"]) for x in row["leads"]] == [(2, 367994), (1, 400000)]
    none = write(tmp_path / "t" / "c.jsonl", [turn("k1", 0)])
    row0 = bcr.build_row(_lead_root(tmp_path / "z", [("W3", none)]), {"id": "B2", "lead": "W3"}, "shipped")
    assert row0["lead"]["compactions"] == 0 and row0["lead"]["pre_tokens"] == 0


def test_main_row_counts_compactions(mc, root, env):
    abc(env["CLAUDE_CONFIG_DIR"], root, extra=[boundary(10, 200000, "w1"), boundary(30, 250000, "w2")])
    row = mc.main_row(root, {"round": ["B1"], "main_sessions": [{"id": "abc", "t": 1.0}, {"id": "gone", "t": 2.0}]},
                      now=T0 + 100, env=env)
    assert row["compactions"] == 2 and row["pre_tokens"] == 250000
    row0 = mc.main_row(root, {"round": ["B2"], "main_sessions": [{"id": "gone", "t": 2.0}]}, now=T0 + 100, env=env)
    assert row0["compactions"] == 0 and row0["pre_tokens"] == 0


def test_report_text_shows_the_count():
    assert report.compactions_text(None) == "" and report.compactions_text({"compactions": 0, "pre_tokens": 9}) == ""
    assert report.compactions_text({"compactions": 1, "pre_tokens": 200000}) == ", 1 compaction, largest 200.0k tokens"
    rows = [{"row": "batch", "batch": "B1", "end": "shipped",
             "lead": {"cost_usd": 3.0, "turns": 40, "wall_s": 600.0, "blocked_wait_s": 300.0, "compactions": 2, "pre_tokens": 367994},
             "workers_total": {"n": 0, "cost_usd": 0.0}, "grade": {"points": 0, "letter": "A"}},
            {"row": "main", "round": ["B1"], "cost_usd": 0.5, "turns": 9, "compactions": 1, "pre_tokens": 200000}]
    t = report.batches_text(rows)
    assert "lead $3.00 40 turns, 2 compactions, largest 368.0k tokens, wall 10.0 min" in t
    assert "main B1: $0.50, 9 turns, 1 compaction, largest 200.0k tokens\n" in t
    old = [{"row": "batch", "batch": "B1", "end": "shipped", "lead": {"cost_usd": 3.0, "turns": 40}}]
    assert "compaction" not in report.batches_text(old)


def test_build_report_names_coordinator_compactions(tmp_path):
    sl = session_with_design(tmp_path)
    sess = tmp_path / "proj" / "sess.jsonl"
    extra = [boundary(0, 120000, "d1", ts="2026-10-18T09:10:00Z"), boundary(0, 367994, "r1", ts="2026-10-18T10:13:30Z"),
             boundary(0, 150000, "r2", ts="2026-10-18T10:14:02Z")]
    sess.write_text(sess.read_text(encoding="utf-8") + "".join(json.dumps(e) + "\n" for e in extra), encoding="utf-8")
    c = report.collect(mech_plan(tmp_path, 1), sl)
    co = c["cost_split"]["coordinator"]
    assert co["compactions"] == 2 and co["pre_tokens"] == 367994
    assert "peak 2.1k, 2 compactions, largest 368.0k tokens; session $" in report.render(c)
