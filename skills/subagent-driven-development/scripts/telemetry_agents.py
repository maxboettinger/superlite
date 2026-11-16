#!/usr/bin/env python3
"""Agent stop telemetry (#933): `sl telemetry agent-stop` turns one subagent transcript into an `agent_stop` line and, for a
reviewer, a `review` line. Only counts and labels leave the transcript; no text of it is copied.

    telemetry_agents.agent_stop(transcript, agent_type, sd=None, agent_id=None) -> dict | None   (fields of the line)
    telemetry_agents.main(a) -> 0   (a: Namespace with transcript, agent_type, agent_id, cwd, sd; never raises)
"""
# Complexity notation:
# T = transcript entries, m = metrics rows
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import metrics as mx  # noqa: E402 | O(1)

TASK = re.compile(r"^\s*([A-Z]{1,3}\d+[A-Za-z]?)\b")  # a plan task id at the start of an Agent description | O(1)
REVIEWERS = {"package-reviewer": "package", "final-reviewer": "final"}  # O(1)


def role_of(agent_type) -> str | None:  # `superlite:implementer` -> implementer | O(1)
    return (agent_type or "").rsplit(":", 1)[-1] or None  # O(1)


def _task(sd, agent_id) -> str | None:  # the task id of this agent's launch row in metrics.jsonl | O(m)
    if not sd or not agent_id:  # O(1)
        return None  # O(1)
    for r in mx.read_jsonl(Path(sd) / "metrics.jsonl"):  # O(m)
        if r.get("ev") == "launch" and r.get("agent_id") == agent_id:  # O(1)
            m = TASK.match(r.get("desc") or "")  # O(1)
            return m.group(1) if m else None  # O(1)
    return None  # O(1)


def _scan(transcript) -> dict | None:  # facts of one transcript, or None when it holds no assistant turn | O(T)
    rows = mx.read_jsonl(transcript)  # O(T)
    stamps = [t for t in (mx._ts(e) for e in rows) if t is not None]  # O(T)
    calls, seen, models, text = 0, set(), {}, ""  # O(1)
    for e in rows:  # O(T)
        if e.get("type") != "assistant":  # O(1)
            continue  # O(1)
        msg = e.get("message") or {}  # O(1)
        if msg.get("model"):  # O(1)
            models[msg["model"]] = models.get(msg["model"], 0) + 1  # O(1)
        parts = []  # O(1)
        for b in msg.get("content") or []:  # O(blocks)
            if not isinstance(b, dict):  # O(1)
                continue  # O(1)
            if b.get("type") == "tool_use" and b.get("id") not in seen:  # a streamed snapshot repeats its blocks | O(1)
                seen.add(b.get("id"))  # O(1)
                calls += 1  # O(1)
            elif b.get("type") == "text" and isinstance(b.get("text"), str):  # O(1)
                parts.append(b["text"])  # O(1)
        if parts:  # O(1)
            text = "\n".join(parts)  # the last assistant text wins | O(len)
    if not models:  # O(1)
        return None  # O(1)
    return {"calls": calls, "text": text, "model": max(models, key=lambda m: (models[m], m)),  # O(1)
            "duration": round(max(stamps) - min(stamps), 1) if stamps else None}


def agent_stop(transcript, agent_type, sd=None, agent_id=None) -> dict | None:  # the `agent_stop` fields, None for an unreadable transcript | O(T + m)
    import fleet_report  # noqa: E402 | O(1)
    facts = _scan(transcript)  # O(T)
    if facts is None:  # O(1)
        return None  # O(1)
    u = mx.session_usage(transcript, sidechain=True)  # O(T)
    t = u["tokens"]  # O(1)
    status = fleet_report.parse(facts["text"])["status"]  # O(len)
    return {"task": _task(sd, agent_id), "role": role_of(agent_type), "model": facts["model"], "effort": None,  # O(1)
            "account": None, "machine": None, "duration_s": facts["duration"],
            "tokens": {"in": t["input"], "out": t["output"], "cache_read": t["cache_read"], "cache_write": t["cache_write"]},
            "cost_usd": u["cost_usd"], "tool_calls": facts["calls"], "status": None if status == "UNKNOWN" else status}


def _review(transcript, role, sd, fields, cwd) -> None:  # one `review` line for a reviewer stop | O(T + n)
    import fleet_report  # noqa: E402 | O(1)
    import telemetry  # noqa: E402 | O(1)
    kind = REVIEWERS.get(role)  # O(1)
    facts = _scan(transcript) if kind else None  # O(T)
    if not facts:  # O(1)
        return  # O(1)
    rep = fleet_report.parse(facts["text"])  # O(len)
    run = telemetry.run_id(Path(sd) if sd else None)  # O(1)
    if run is None:  # no run: the FR<n> label digits, else None; never a count over unrelated null-run lines | O(1)
        m = re.search(r"FR(\d+)", fields.get("task") or "")  # O(1)
        rnd = int(m.group(1)) if m else None  # O(1)
    else:  # O(1)
        rnd = 1 + telemetry.count("review", run, review_kind=kind)  # O(n)
    telemetry.emit("review", sd=sd, cwd=cwd, review_kind=kind, verdict=fields["status"], findings=len(rep["findings"]), round=rnd)  # O(s)


def main(a) -> int:  # emit the lines of one agent stop; never raises, always 0 | O(T + m + n)
    try:  # O(1)
        import telemetry  # noqa: E402 | O(1)
        sd = a.sd or None  # O(1)
        fields = agent_stop(Path(a.transcript), a.agent_type, sd, getattr(a, "agent_id", None))  # O(T + m)
        if fields is None:  # O(1)
            return 0  # O(1)
        telemetry.emit("agent_stop", sd=sd, cwd=getattr(a, "cwd", None), **fields)  # O(s)
        _review(Path(a.transcript), fields["role"], sd, fields, getattr(a, "cwd", None))  # O(T + n)
    except BaseException:  # noqa: BLE001 | a telemetry failure never reaches the hook | O(1)
        pass  # O(1)
    return 0  # O(1)
