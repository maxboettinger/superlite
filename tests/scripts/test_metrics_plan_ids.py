"""metrics.py: plan task ids (D1, P2, UI3a), not only T<n>, map agents and handovers to tasks."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import history  # noqa: E402
import metrics  # noqa: E402

SONNET = "claude-sonnet-4-5"
READ_PRIME = "Read /x/.superlite/prime.md, then reply READY"


def task(tid):
    return (f"### {tid} task {tid.lower()} · Complexity 3 · Est. context 30k\n**Owns:** src/pkg/{tid.lower()}.py, tests/test_{tid.lower()}.py\n"
            "**Est. time:** 2 min\n**Components:** 1\n**LOC owned:** 60\n**Tests:** fast\n\n")


def plan(tmp_path, ids):
    head = "# Plan\n**Goal:** x.\n**Tech stack:** Python\n\nGlobal constraints (from SPEC): stdlib only.\n\n```mermaid\n%% taskgraph\nflowchart LR\n```\n\n"
    p = tmp_path / "plan.md"
    p.write_text(head + "".join(task(t) for t in ids), encoding="utf-8")
    return p


def ts(sec):
    return f"2026-11-09T10:{sec // 60:02d}:{sec % 60:02d}Z"


def write_transcript(path, heading, mid):
    path.parent.mkdir(parents=True, exist_ok=True)
    usage = {"input_tokens": 100, "output_tokens": 200, "cache_read_input_tokens": 1000}

    def asst(sec, n, text):
        return {"type": "assistant", "timestamp": ts(sec), "message": {"id": f"{mid}{n}", "model": SONNET, "usage": usage,
                                                                      "content": [{"type": "text", "text": text}]}}

    def user(sec, text):
        return {"type": "user", "timestamp": ts(sec), "message": {"role": "user", "content": text}}

    lines = [user(0, READ_PRIME), asst(1, 0, "READY")]
    if heading:
        lines.append(user(5, heading))
    lines += [asst(10, 1, "working"), asst(70, 2, "Status: DONE")]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def metrics_file(tmp_path, rows):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return sl


def fleet_rows(tmp_path, workers):
    rows = []
    for wid, acct, tid in workers:
        tp = tmp_path / acct / "projects" / "p" / f"{wid.lower()}.jsonl"
        write_transcript(tp, f'\n<pasted_content id="fe26">\n# Task {tid}\nPLAN=/x/p.md', wid)
        rows.append({"ev": "launch", "t": 1_700_000_000_000, "agent_id": wid, "type": "fleet:superlite:implementer", "model": "sonnet",
                     "desc": f"fleet worker {acct} pane wB2:p1"})
        rows.append({"ev": "stop", "t": 1_700_000_100_000, "agent_id": wid, "type": "fleet:superlite:implementer", "transcript": str(tp),
                     "last": "Status: DONE"})
    return rows


def test_id_re_plan_ids():
    assert metrics.id_re({"D1", "UI3a"}).findall("D1 and UI3a then T4, not W3 or UTF8") == ["D1", "UI3a", "T4"]
    assert metrics.id_re().findall("D1 T4 T12b") == ["T4", "T12b"]


def test_handover_plan_ids():
    assert metrics.handover('\n<pasted_content id="fe26">\n# Task F1\nPLAN=/x/p.md', metrics.id_re({"D1", "F1"})) == ["F1"]
    assert metrics.handover("# Task F1", metrics.TID) is None
    assert metrics.handover("Tasks P1 P2 (after D0)", metrics.id_re({"P1", "P2", "D0"})) == ["P1", "P2"]
    assert metrics.handover("W3: next one", metrics.id_re({"D1"})) is None
    assert metrics.handover("Task T2", metrics.id_re({"D1"})) == ["T2"]
    assert metrics.handover("T4's tests. Task T5") == ["T5"]


def test_fleet_workers_other_accounts(tmp_path):
    p = plan(tmp_path, ["D0", "D1", "F1", "P1"])
    sl = metrics_file(tmp_path, fleet_rows(tmp_path, [("W5", "acct1", "F1"), ("W6", "acct2", "D1")]))
    rows = {r["task"]: r for r in metrics.task_records(sl, p)}
    assert {"D1", "F1"} <= set(rows)
    assert "W5" not in rows and "W6" not in rows
    for t in ("D1", "F1"):
        assert rows[t]["cost_usd"] > 0
        assert rows[t]["duration_s"] >= 60


def test_resumed_run_keeps_first_lead_rows(tmp_path):
    p = plan(tmp_path, ["D0", "D1", "F1", "P1"])
    a1 = tmp_path / "projA" / "sessA" / "subagents" / "agent-a1.jsonl"
    write_transcript(a1, None, "a1")
    rows = [{"ev": "launch", "t": 1_700_000_000_000, "agent_id": "a1", "type": "superlite:implementer", "model": "sonnet", "desc": "D0 Theme tokens"},
            {"ev": "stop", "t": 1_700_000_100_000, "agent_id": "a1", "type": "superlite:implementer", "transcript": str(a1), "last": "Status: DONE"}]
    rows += fleet_rows(tmp_path, [("W1", "acct2", "P1")])
    sl = metrics_file(tmp_path, rows)
    recs = {r["task"]: r for r in metrics.task_records(sl, p)}
    assert {"D0", "P1"} <= set(recs)
    assert recs["D0"]["cost_usd"] > 0 and recs["P1"]["cost_usd"] > 0
    assert len(history.run_rows(p, sl)) == 2


def test_no_plan_keeps_t_ids(tmp_path):
    p = plan(tmp_path, ["F1", "T2"])
    sl = metrics_file(tmp_path, fleet_rows(tmp_path, [("W5", "acct1", "F1")]))
    assert "F1" not in {r["task"] for r in metrics.task_records(sl)}
    sl2 = tmp_path / "run2"
    sl2.mkdir()
    rows = fleet_rows(tmp_path, [("W7", "acct1", "T2")])
    (sl2 / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert "T2" in {r["task"] for r in metrics.task_records(sl2)}
    assert "T2" in {r["task"] for r in metrics.task_records(sl2, p)}
