#!/usr/bin/env python3
"""Main's cost per plan round (#680): notes main's sessions in backlog.json, writes one main row per round.

A main row sums main's session transcripts since the previous main row's window end; a session whose transcript is gone is listed as unmeasured.
Recording never raises: note_session and record_main return None on any error."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import backlog_state
import batch_cost
import batch_waits
import fleet_io
import metrics

TOKEN_KEYS = ("input", "cache_read", "cache_write", "output", "thinking")  # O(1)


def _env(env):  # the environment mapping to read | O(1)
    return os.environ if env is None else env  # O(1)


def _session_id(env):  # main's session id, empty for a fleet worker or none | O(1)
    if env.get("SUPERLITE_FLEET_WORKER"):  # O(1)
        return ""  # O(1)
    return env.get("SUPERLITE_SESSION_ID") or env.get("CLAUDE_CODE_SESSION_ID") or ""  # O(1)


def main_transcript(root, session, env=None):  # the transcript of a main session, None when no candidate exists | O(candidates)
    env = _env(env)  # O(1)
    cfg = env.get("CLAUDE_CONFIG_DIR")  # O(1)
    bases = ([Path(cfg)] if cfg else []) + [Path.home() / ".claude"]  # O(1)
    r = Path(root)  # O(1)
    paths = [str(r)]  # O(1)
    try:
        res = str(r.resolve())  # O(len)
    except OSError:
        res = str(r)  # O(1)
    if res not in paths:  # O(1)
        paths.append(res)  # O(1)
    for base in bases:  # O(bases)
        for p in paths:  # O(paths)
            cand = base / "projects" / fleet_io.project_dir(p) / f"{session}.jsonl"  # O(1)
            if cand.is_file():  # O(1)
                return cand  # O(1)
    return None  # O(1)


def note_session(root, env=None):  # add main's session id to backlog.json main_sessions once | O(sessions)
    try:
        sid = _session_id(_env(env))  # O(1)
        if not sid:  # O(1)
            return None  # O(1)

        def add(d):  # O(sessions)
            lst = d.setdefault("main_sessions", [])  # O(1)
            if not any(isinstance(s, dict) and s.get("id") == sid for s in lst):  # O(sessions)
                lst.append({"id": sid, "t": time.time()})  # O(1)

        backlog_state.update(backlog_state.path(root), add)  # O(size)
        return sid  # O(1)
    except Exception:
        return None  # O(1)


def _last_until(rows, sid):  # the window end of the last main row naming a session | O(rows)
    for row in reversed(rows):  # O(rows)
        if row.get("row") == "main" and sid in (row.get("sessions") or []):  # O(sessions)
            w = (row.get("windows") or {}).get(sid)  # O(1)
            return w[1] if isinstance(w, list) and len(w) == 2 else None  # O(1)
    return None  # O(1)


def main_row(root, data, now=None, env=None):  # the main row for the sessions in data | O(sessions * transcript)
    now = time.time() if now is None else now  # O(1)
    rows = batch_cost.read_rows(root)  # O(rows)
    ids = []  # O(1)
    for s in data.get("main_sessions") or []:  # O(sessions)
        if isinstance(s, dict) and s.get("id") and s["id"] not in ids:  # O(sessions)
            ids.append(s["id"])  # O(1)
    tokens = dict.fromkeys(TOKEN_KEYS, 0)  # O(1)
    kinds, windows, unmeasured = {}, {}, []  # O(1)
    turns, cost, wall = 0, 0.0, 0.0  # O(1)
    for sid in ids:  # O(sessions)
        path = main_transcript(root, sid, env)  # O(candidates)
        if path is None:  # O(1)
            unmeasured.append(sid)  # O(1)
            continue  # O(1)
        since = _last_until(rows, sid)  # O(rows)
        u = metrics.session_usage(path, since, now, kind=batch_waits.main_kind)  # O(entries)
        windows[sid] = [since, now]  # O(1)
        turns += u["turns"]  # O(1)
        cost += u["cost_usd"]  # O(1)
        wall += u["wall_s"] or 0.0  # O(1)
        for k in TOKEN_KEYS:  # O(1)
            tokens[k] += u["tokens"].get(k, 0)  # O(1)
        for k, v in (u.get("kinds") or {}).items():  # O(kinds)
            cur = kinds.setdefault(k, {"turns": 0, "cost_usd": 0.0})  # O(1)
            cur["turns"] += v["turns"]  # O(1)
            cur["cost_usd"] = round(cur["cost_usd"] + v["cost_usd"], 6)  # O(1)
    stamp = datetime.fromtimestamp(time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # O(1)
    return {"v": 1, "row": "main", "t": stamp, "round": data.get("round"), "sessions": ids, "unmeasured": unmeasured,
            "windows": windows, "turns": turns, "tokens": tokens, "cost_usd": round(cost, 6), "wall_s": round(wall, 3),
            "kinds": kinds}  # O(1)


def record_main(root, env=None):  # append the main row once per plan round | O(size)
    try:
        p = backlog_state.path(root)  # O(1)
        if not p.is_file():  # O(1)
            return None  # O(1)
        data = backlog_state.load(p)  # O(size)
        mains = [r for r in batch_cost.read_rows(root) if r.get("row") == "main"]  # O(rows)
        if mains and mains[-1].get("round") == data.get("round"):  # O(1)
            return None  # O(1)
        row = main_row(root, data, env=env)  # O(sessions * transcript)
        cp = batch_cost.costs_path(root)  # O(1)
        cp.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        with open(cp, "a") as f:  # O(1)
            f.write(json.dumps(row) + "\n")  # O(size)
        return row  # O(1)
    except Exception:
        return None  # O(1)
