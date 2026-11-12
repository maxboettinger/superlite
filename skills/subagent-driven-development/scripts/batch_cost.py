#!/usr/bin/env python3
"""One cost and quality row per backlog batch (#680): `<root>/.superlite/batch-costs.jsonl`, append-only.

    batch_cost.record(root, batch, end)         build the row and append it; None when anything fails
    batch_cost.save_snapshot(root, bid, wt)     keep the lead worktree's workers, tests and quality before ship removes it
    batch_cost.read_rows(root)                  every row of the file
"""
# Complexity notation: w = workers, m = lines of metrics.jsonl, T = transcript lines, r = rows
import json  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import batch_grade  # noqa: E402 | O(1)
import batch_waits  # noqa: E402 | O(1)
import fleet_io  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import metrics  # noqa: E402 | O(1)

TOKENS = ("input", "cache_read", "cache_write", "output", "thinking")  # O(1)


def costs_path(root) -> Path:  # O(1)
    return Path(root) / ".superlite" / "batch-costs.jsonl"  # O(1)


def read_rows(root) -> list:  # O(r)
    try:  # O(1)
        lines = costs_path(root).read_text(encoding="utf-8", errors="replace").splitlines()  # O(r)
    except OSError:  # O(1)
        return []  # O(1)
    out = []  # O(1)
    for line in lines:  # O(r) iterations
        try:  # O(1)
            row = json.loads(line)  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(row, dict):  # O(1)
            out.append(row)  # O(1)
    return out  # O(r)


def _snap_path(root, bid) -> Path:  # O(1)
    return Path(root) / ".superlite" / "backlog" / f"{bid}.snapshot.json"  # O(1)


def save_snapshot(root, bid, wt):  # O(T + w)
    try:  # O(1)
        sd = Path(wt) / ".superlite"  # O(1)
        if not sd.is_dir():  # O(1)
            return None  # O(1)
        snap = batch_grade.snapshot(sd)  # O(T + w)
        p = _snap_path(root, bid)  # O(1)
        p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        p.write_text(json.dumps(snap, sort_keys=True), encoding="utf-8")  # O(len)
        return p  # O(1)
    except Exception:  # recording never changes an outcome | O(1)
        return None  # O(1)


def _snapshot(root, batch) -> dict:  # fresh worktree, else the saved file, else an empty one | O(T + w)
    wt = batch.get("worktree")  # O(1)
    if wt and (Path(wt) / ".superlite").is_dir():  # O(1)
        save_snapshot(root, batch["id"], wt)  # O(T + w)
        return batch_grade.snapshot(Path(wt) / ".superlite")  # O(T + w)
    try:  # O(1)
        snap = json.loads(_snap_path(root, batch["id"]).read_text(encoding="utf-8"))  # O(len)
        if isinstance(snap, dict):  # O(1)
            return snap  # O(1)
    except (OSError, ValueError):  # O(1)
        pass  # O(1)
    return batch_grade.snapshot(Path(root) / ".superlite" / "backlog" / "missing-worktree")  # O(1)


def _lead_transcripts(sd, wid, worker) -> list:  # distinct own stop transcripts in order | O(m)
    out = []  # O(1)
    try:  # O(1)
        lines = (Path(sd) / "metrics.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()  # O(m)
    except OSError:  # O(1)
        return out  # O(1)
    for line in lines:  # O(m) iterations
        try:  # O(1)
            e = json.loads(line)  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if not isinstance(e, dict) or e.get("ev") != "stop" or e.get("agent_id") != wid or not e.get("transcript"):  # O(1)
            continue  # O(1)
        if e["transcript"] not in out and fleet_io.own_stop(e, worker):  # O(len)
            out.append(e["transcript"])  # O(1)
    return out  # O(m)


def _effort(worker):  # O(a)
    argv = ((worker or {}).get("launch") or {}).get("argv") or []  # O(1)
    for i, a in enumerate(argv[:-1]):  # O(a) iterations
        if a == "--effort":  # O(1)
            return str(argv[i + 1])  # O(1)
    return None  # O(1)


def _lead(sd, batch) -> dict:  # O(m + T)
    wid = batch.get("lead")  # O(1)
    try:  # O(1)
        worker = fs.load(sd)["workers"].get(wid) or {}  # O(w)
    except (OSError, ValueError, KeyError, AttributeError):  # O(1)
        worker = {}  # O(1)
    wt = batch.get("worktree") or worker.get("worktree")  # only transcripts of this batch's worktree count | O(1)
    own = dict(worker, worktree=wt) if wt else worker  # O(1)
    tokens, cost, turns, wall, blocked, kinds = dict.fromkeys(TOKENS, 0), 0.0, 0, 0.0, 0.0, {}  # O(1)
    wake, best_model, best_turns = {}, None, 0  # O(1)
    for tr in _lead_transcripts(sd, wid, own):  # O(stops) iterations
        u = metrics.session_usage(tr, kind=batch_waits.lead_kind)  # O(T)
        turns += u["turns"]  # O(1)
        cost += u["cost_usd"]  # O(1)
        wall += u.get("wall_s") or 0.0  # O(1)
        for k in TOKENS:  # O(1)
            tokens[k] += u["tokens"].get(k, 0)  # O(1)
        for kind, v in (u.get("kinds") or {}).items():  # O(kinds)
            c = kinds.setdefault(kind, {"turns": 0, "cost_usd": 0.0})  # O(1)
            c["turns"] += v["turns"]  # O(1)
            c["cost_usd"] = round(c["cost_usd"] + v["cost_usd"], 6)  # O(1)
        if u["turns"] > best_turns:  # O(1)
            best_turns, best_model = u["turns"], u.get("model")  # O(1)
        w = batch_waits.waits(tr)  # O(T)
        blocked += w.get("blocked_wait_s") or 0.0  # O(1)
        for k, n in (w.get("wakeups") or {}).items():  # O(1)
            wake[k] = wake.get(k, 0) + n  # O(1)
    return {"model": best_model or worker.get("tier"), "effort": _effort(worker), "turns": turns, "tokens": tokens,
            "cost_usd": round(cost, 6), "wall_s": round(wall, 3), "blocked_wait_s": round(blocked, 3), "wakeups": wake, "kinds": kinds}  # O(1)


def build_row(root, batch, end) -> dict:  # O(m + T + w)
    sd = Path(root) / ".superlite"  # O(1)
    snap = _snapshot(root, batch)  # O(T + w)
    workers = snap.get("workers") or {}  # O(1)
    total_tokens = dict.fromkeys(TOKENS, 0)  # O(1)
    for v in workers.values():  # O(w) iterations
        for k in TOKENS:  # O(1)
            total_tokens[k] += (v.get("tokens") or {}).get(k, 0)  # O(1)
    total = {"n": sum(v.get("n", 0) for v in workers.values()), "tokens": total_tokens,
             "cost_usd": round(sum(v.get("cost_usd", 0.0) for v in workers.values()), 6)}  # O(w)
    return {"v": 1, "row": "batch", "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "batch": batch["id"],
            "issues": batch.get("issues"), "config": "default", "end": end, "pr": batch.get("pr"), "version": batch.get("version"),
            "lead": _lead(sd, batch), "workers": workers, "workers_total": total, "tests": snap.get("tests") or {},
            "grade": batch_grade.grade(snap.get("quality") or {}, batch)}  # O(m + T + w)


def record(root, batch, end):  # build and append one row; None on any failure | O(m + T + w)
    try:  # O(1)
        row = build_row(root, batch, end)  # O(m + T + w)
        p = costs_path(root)  # O(1)
        p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        with p.open("a", encoding="utf-8") as f:  # O(1)
            f.write(json.dumps(row, sort_keys=True) + "\n")  # one write | O(len)
        return row  # O(1)
    except Exception:  # recording never changes an outcome | O(1)
        return None  # O(1)
