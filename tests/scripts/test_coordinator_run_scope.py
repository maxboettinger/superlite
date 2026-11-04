"""#112: the coordinator's cost covers the run alone (from the first dispatch to the transcript's end), the whole
session is reported beside it; reconcile, budget and the report read the right one."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from test_metrics_history import BUDGET, METRICS, transcript
from test_plan_tools import SCRIPTS, run
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402
import report  # noqa: E402

OPUS = "claude-opus-5-5"


def _ms(hms: str) -> int:
    return int(datetime.fromisoformat(f"2026-10-18T{hms}+00:00").timestamp() * 1000)


def _turn(mid, hms, ctx, tool=None):
    content = [{"type": "tool_use", "id": f"tu-{mid}", "name": tool, "input": {"description": "x"}}] if tool else [{"type": "text", "text": "x"}]
    return {"type": "assistant", "timestamp": f"2026-10-18T{hms}Z",
            "message": {"id": mid, "model": OPUS, "content": content,
                        "usage": {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": ctx, "cache_creation_input_tokens": 50}}}


DESIGN = [("d0", "09:00:00", 50_000, None), ("d1", "09:00:01", 50_000, None), ("d2", "09:00:02", 50_000, None),
          ("x0", "09:30:00", 50_000, "Agent")]  # brainstorming, planning, an Explore agent: before the run
RUN = [("p0", "10:13:10", 1_000, "Agent"), ("w0", "10:13:12", 1_200, None),  # the first dispatch, then the run
       ("r0", "10:14:00", 1_400, None), ("r1", "10:14:01", 1_600, None), ("r2", "10:14:02", 1_800, None), ("r3", "10:14:03", 2_000, None)]


def _cost(turns) -> float:
    price = metrics.load_prices()["opus"]
    return sum(metrics.cost_of({"input": 10, "output": 100, "cache_read": ctx, "cache_write_5m": 50, "cache_write_1h": 0}, price)
               for _, _, ctx, _ in turns)


def session_with_design(tmp_path):
    """<proj>/sess.jsonl: design turns, then the first dispatch (10:13:10) and the run; one agent starting at 10:13:20."""
    proj = tmp_path / "proj"
    (proj / "sess" / "subagents").mkdir(parents=True)
    lines = []
    for mid, hms, ctx, tool in DESIGN + RUN:
        lines += [_turn(mid, hms, ctx, tool), _turn(mid, hms, ctx, tool)]  # a repeated snapshot: counted once
    (proj / "sess.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    agent = proj / "sess" / "subagents" / "agent-a.jsonl"
    transcript(agent, [("Implement T1 slug", [("Bash", "")], "Status: DONE")])  # entries from 10:13:20
    sl = tmp_path / ".superlite"
    sl.mkdir()
    rows = [{"ev": "launch", "t": _ms("10:13:15"), "agent_id": "a", "type": "superlite:implementer", "model": "sonnet", "desc": "T1 slug"},
            {"ev": "stop", "t": _ms("10:14:30"), "agent_id": "a", "type": "superlite:implementer", "transcript": str(agent), "last": "Status: DONE"}]
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return sl


def test_coordinator_counts_from_the_first_dispatch_and_keeps_the_session_total(tmp_path):
    sl = session_with_design(tmp_path)
    co = json.loads(run(METRICS, "--dir", sl, "--json", "--all", cwd=tmp_path).out)["coordinator"]
    assert co["scope"] == "run" and co["turns"] == len(RUN)
    assert abs(co["cost_usd"] - _cost(RUN)) < 1e-6
    assert co["context_peak"] == 2_060 and co["duration_s"] == 53.0  # 10:13:10 -> 10:14:03, no design context
    assert co["session"]["turns"] == len(DESIGN + RUN) and abs(co["session"]["cost_usd"] - _cost(DESIGN + RUN)) < 1e-6
    assert "session $" in run(METRICS, "--dir", sl, cwd=tmp_path).out


def test_reconcile_compares_the_session_total_with_the_stream_log(tmp_path):
    sl = session_with_design(tmp_path)
    log = tmp_path / "stream.jsonl"
    log.write_text(json.dumps({"type": "result", "total_cost_usd": 1.0}) + "\n", encoding="utf-8")
    rc = json.loads(run(METRICS, "--dir", sl, "--reconcile", log, cwd=tmp_path).out)
    assert abs(rc["coordinator_usd"] - _cost(RUN)) < 1e-6 and abs(rc["coordinator_session_usd"] - _cost(DESIGN + RUN)) < 1e-6
    assert abs(rc["metrics_usd"] - (rc["coordinator_session_usd"] + rc["agents_usd"])) < 1e-6


def test_budget_and_report_split_the_run_from_the_session(tmp_path):
    sl = session_with_design(tmp_path)
    p = mech_plan(tmp_path, 1)
    b = json.loads(run(BUDGET, "--plan", p, "--dir", sl, "--json", cwd=tmp_path).out)
    assert b["coordinator_usd"] == round(_cost(RUN), 3)
    c = report.collect(p, sl)
    cs = c["cost_split"]
    assert abs(cs["coordinator_usd"] - _cost(RUN)) < 1e-6 and abs(cs["coordinator_session_usd"] - _cost(DESIGN + RUN)) < 1e-6
    assert cs["coordinator"] == {"turns": len(RUN), "context_median": 1_660, "context_peak": 2_060}
    assert f"coordinator ${_cost(RUN):.2f} ({len(RUN)} turns, context median 1.7k, peak 2.1k; session ${_cost(DESIGN + RUN):.2f})" in report.render(c)


def test_without_any_agent_the_coordinator_is_the_whole_session(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    lines = [_turn(mid, hms, ctx, tool) for mid, hms, ctx, tool in DESIGN]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "metrics.jsonl").write_text(json.dumps({"session_transcript": str(proj / "s.jsonl")}) + "\n", encoding="utf-8")
    co = metrics.coordinator_record(sl)
    assert co["scope"] == "session" and co["turns"] == len(DESIGN) == co["session"]["turns"]
    assert co["cost_usd"] == co["session"]["cost_usd"]
