#!/usr/bin/env python3
"""Pool bookkeeping by script: the coordinator never edits .superlite/pool.json by hand.

    pool.py add ID --tier T [--current Tn] [--pool .superlite/pool.json]
    pool.py busy ID Tn | free ID | remove ID | list | sync | prune

Each subcommand writes atomically and prints one line; an unknown agent exits 2 with one stderr line.
`remove ID` drops the agent from the pool (`removed ID`); dispatch does this for every agent it evicts.
`sync` fills per agent `context_k` (the transcript's last assistant message: input + cache read +
cache write tokens, in thousands), `idle_min` (from its latest stop in metrics.jsonl) and clears `busy`
when that stop is newer than `busy_since`. A missing or unreadable transcript keeps the old context_k.
`add` records `session` (the session id), so a later session can tell an in-process agent that is gone.
`prune` drops agents that no longer exist and prints one `removed ID (reason)` line per agent, a `kept ID (reason)`
line for one it cannot judge, then a summary: a fleet worker is gone when fleet.json says stopped or Herdr no longer
lists it (kept while Herdr is unreachable); an in-process agent is gone when its `session` is not this session
(kept when it has none).
An agent matches a stop when agent_id equals its id, else when the transcript is `agent-<id>.jsonl`.
"""

# Complexity notation:
# a = agents in the pool, m = lines of metrics.jsonl, T = transcript bytes
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import assign as asg  # noqa: E402 | O(1)
import metrics as mx  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)


def currents(ag):  # O(len current)
    """The tasks an agent is on: `current` is "Tn", a batch "Tn,Tm", or a list."""
    cur = ag.get("current") or []  # O(1)
    parts = cur if isinstance(cur, list) else str(cur).split(",")  # O(len)
    return [str(x).strip() for x in parts if str(x).strip()]  # O(len)


def load(path):  # O(pool bytes)
    p = Path(path)  # O(1)
    if not p.exists():  # O(1)
        return {"agents": []}  # O(1)
    try:  # O(1)
        data = json.loads(p.read_text(encoding="utf-8"))  # O(pool bytes)
    except (ValueError, OSError) as e:  # a corrupt pool.json: one stderr line, no traceback | O(1)
        raise SystemExit(f"pool.json unreadable ({p}): {e}")  # O(1)
    if not isinstance(data, dict):  # O(1)
        raise SystemExit(f"pool.json unreadable ({p}): top level is not an object")  # O(1)
    return data  # O(1)


def save(path, data):  # O(pool bytes), atomic
    p = Path(path)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")  # O(1) unique per process: dispatch and `sl pool` may save at once
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")  # O(pool bytes)
    tmp.replace(p)  # O(1) atomic rename


def find(data, aid):  # O(a)
    return next((ag for ag in data.setdefault("agents", []) if ag.get("id") == aid), None)  # O(a)


def add(data, aid, tier, current=None):  # O(a)
    ag = find(data, aid)  # O(a)
    if ag is None:  # O(1)
        ag = {"id": aid, "tier": tier, "tasks": [], "files": [], "context_k": asg.DEFAULT_CONTEXT_K, "idle_min": 0, "busy": False}  # O(1)
        data["agents"].append(ag)  # O(1)
    ag["tier"] = tier  # O(1)
    if current:  # O(1)
        ag["busy"] = True  # O(1)
        ag["current"] = current  # O(1)
    return ag  # O(1)


def _busy_part(ag):  # O(len current)
    cur = currents(ag)  # O(len current)
    return f"; was busy with {','.join(cur)}" if ag.get("busy") and cur else ""  # O(len current)


def prune(data, workers, sid, live):  # O(a)
    """Drop agents that no longer exist from data["agents"] in place. -> (removed, kept): lists of (id, reason);
    `kept` holds the agents it could not judge. workers: {wid: {"name", "state"}}; live: Herdr agent names or None."""
    removed, kept, keep = [], [], []  # O(1)
    for ag in data.get("agents") or []:  # O(a) iterations
        aid, w, why = ag.get("id"), workers.get(ag.get("id")), None  # O(1)
        if w is not None:  # a fleet worker | O(1)
            if w.get("state") == "stopped":  # O(1)
                why = "fleet worker stopped"  # O(1)
            elif live is None:  # O(1)
                kept.append((aid, "Herdr unreachable"))  # O(1)
            elif w.get("name") not in live:  # O(1)
                why = "fleet worker gone from Herdr"  # O(1)
        elif not ag.get("session"):  # O(1)
            kept.append((aid, f"no session recorded; sl pool remove {aid} if it is gone"))  # O(1)
        elif sid is None:  # O(1)
            kept.append((aid, "no session id to check it against"))  # O(1)
        elif ag["session"] != sid:  # O(1)
            why = f"in-process agent of session {ag['session']}, not this session"  # O(1)
        if why is None:  # O(1)
            keep.append(ag)  # O(1)
        else:  # O(1)
            removed.append((aid, why + _busy_part(ag)))  # O(len current)
    if "agents" in data:  # O(1)
        data["agents"][:] = keep  # O(a)
    return removed, kept  # O(1)


def herdr_names():  # O(a)
    """Names of Herdr's agents, or None when Herdr is missing, not running or answers with an error."""
    try:  # O(1)
        import herdr_client  # O(1)
        return set(herdr_client.agent_states())  # O(a)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def _workers(sd):  # O(w)
    """{wid: {"name", "state"}} of fleet.json; {} without fleet_state (it needs fcntl) and the no-op lock."""
    try:  # O(1)
        import contextlib  # O(1)
        import fleet_state  # O(1)
    except ImportError:  # O(1)
        return {}, contextlib.nullcontext()  # O(1)
    ws = fleet_state.load(sd).get("workers")  # O(w)
    ws = ws if isinstance(ws, dict) else {}  # O(1)
    return {wid: {"name": fleet_state.name_of(sd, wid, w), "state": w.get("state")} for wid, w in ws.items() if isinstance(w, dict)}, fleet_state.locked(sd)  # O(w)


def _count(n):  # O(1)
    return f"{n} agent" + ("" if n == 1 else "s")  # O(1)


def prune_file(path):  # O(a + w)
    """Prune the pool at `path` under the fleet lock, save when something went, return the lines to print."""
    p = Path(path)  # O(1)
    if not p.exists():  # O(1)
        return [f"pool: no pool.json in {p.parent}"]  # O(1)
    sd, sid = p.parent, state.session_id()  # O(1)
    other = state.live_owner(sd)  # O(d)
    if other:  # O(1)
        return [f"pool: not pruned: {sd} belongs to session {other}; take the run over first: sl orchestrator takeover --plan {sd}"]  # O(1)
    workers, lock = _workers(sd)  # O(w)
    live = None  # O(1)
    if any(workers.get(ag.get("id")) not in (None, {}) and workers[ag["id"]].get("state") != "stopped" for ag in load(p).get("agents") or []):  # O(a)
        live = herdr_names()  # O(a)
    with lock:  # O(1)
        workers = _workers(sd)[0]  # reread under the lock: fleet.py may have changed it meanwhile | O(w)
        data = load(p)  # O(pool bytes)
        total = len(data.get("agents") or [])  # O(1)
        removed, kept = prune(data, workers, sid, live)  # O(a)
        if removed:  # O(1)
            save(p, data)  # O(pool bytes)
    out = [f"removed {i} ({r})" for i, r in removed] + [f"kept {i} ({r})" for i, r in kept]  # O(a)
    out.append(f"pool: removed {len(removed)} of {_count(total)}" if removed else f"pool: nothing to prune ({_count(total)})")  # O(1)
    return out  # O(1)


def busy(data, aid, task, now_ms):  # O(a)
    ag = find(data, aid)  # O(a)
    if ag is None:  # O(1)
        raise KeyError(aid)  # O(1)
    ag.update({"busy": True, "current": task, "busy_since": int(now_ms)})  # O(1)
    return ag  # O(1)


def free(data, aid):  # O(a)
    ag = find(data, aid)  # O(a)
    if ag is None:  # O(1)
        raise KeyError(aid)  # O(1)
    ag["busy"] = False  # O(1)
    ag.pop("current", None)  # O(1)
    ag.pop("busy_since", None)  # O(1)
    return ag  # O(1)


def remove(data, aid):  # O(a)
    """Drop agent `aid` from data["agents"] in place. True when it was there, False (data untouched) when not."""
    agents = data.get("agents") or []  # O(1)
    keep = [ag for ag in agents if ag.get("id") != aid]  # O(a)
    if len(keep) == len(agents):  # O(1)
        return False  # O(1)
    agents[:] = keep  # O(a) same list object
    return True  # O(1)


def context_k(transcript):  # O(T)
    """Last assistant message's input + cache read + cache write (5m + 1h) tokens in thousands, or None."""
    try:  # O(1)
        lines = Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines()  # O(T)
    except OSError:  # O(1)
        return None  # O(1)
    usage = None  # O(1)
    for ln in lines:  # O(lines)
        try:  # O(1)
            e = json.loads(ln)  # O(line)
        except ValueError:  # O(1)
            continue  # O(1)
        msg = e.get("message") if isinstance(e, dict) and e.get("type") == "assistant" else None  # O(1)
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):  # O(1)
            usage = msg["usage"]  # O(1)
    if usage is None:  # O(1)
        return None  # O(1)
    cc = usage.get("cache_creation")  # O(1)
    write = (cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0)) if isinstance(cc, dict) \
        else usage.get("cache_creation_input_tokens", 0)  # O(1)
    return round((usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + write) / 1000, 1)  # O(1)


def latest_stops(sl_dir):  # O(m)
    """{agent_id: (t, transcript)} of the newest stop per agent_id."""
    out = {}  # O(1)
    for e in mx.read_jsonl(Path(sl_dir) / "metrics.jsonl"):  # O(m) iterations
        if e.get("ev") == "stop" and e.get("agent_id") and isinstance(e.get("t"), (int, float)):  # O(1)
            if e["agent_id"] not in out or e["t"] >= out[e["agent_id"]][0]:  # O(1)
                out[e["agent_id"]] = (e["t"], e.get("transcript") or "")  # O(1)
    return out  # O(1)


def stop_for(aid, stops):  # O(m)
    cands = [v for k, v in stops.items() if k == aid or Path(v[1]).name == f"agent-{aid}.jsonl"]  # O(m)
    return max(cands, key=lambda v: v[0]) if cands else None  # O(m)


def sync(data, sl_dir, now_ms=None):  # O(a*m + a*T)
    now_ms = time.time() * 1000 if now_ms is None else now_ms  # O(1)
    stops = latest_stops(sl_dir)  # O(m)
    for ag in data.setdefault("agents", []):  # O(a) iterations
        st = stop_for(ag.get("id"), stops)  # O(m)
        if st is None:  # O(1)
            continue  # O(1)
        t, tr = st  # O(1)
        k = context_k(tr) if tr else None  # O(T)
        if k is not None:  # an unreadable transcript keeps the old value | O(1)
            ag["context_k"] = k  # O(1)
        ag["idle_min"] = max(0.0, round((now_ms - t) / 60000, 1))  # O(1)
        if ag.get("busy") and ag.get("busy_since") is not None and t > ag["busy_since"]:  # O(1)
            ag["busy"] = False  # O(1)
    return data  # O(1)


def synced_count(data, sl_dir):  # O(a*m)
    stops = latest_stops(sl_dir)  # O(m)
    return sum(1 for ag in data.get("agents", []) if stop_for(ag.get("id"), stops))  # O(a*m)


def line(ag):  # O(1)
    cur = f" current={ag['current']}" if ag.get("current") else ""  # O(1)
    return (f"{ag['id']} tier={ag.get('tier')} busy={bool(ag.get('busy'))}{cur} tasks={len(ag.get('tasks', []))} "
            f"context_k={ag.get('context_k')} idle_min={ag.get('idle_min')}")  # O(1)


def main(argv=None):  # O(a*m + a*T)
    common = argparse.ArgumentParser(add_help=False)  # O(1)
    common.add_argument("--pool", default=state.pool_path())  # the session's run, else ./.superlite | O(d)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("add", parents=[common])  # O(1)
    s.add_argument("id")  # O(1)
    s.add_argument("--tier", required=True)  # O(1)
    s.add_argument("--current")  # O(1)
    s = sub.add_parser("busy", parents=[common])  # O(1)
    s.add_argument("id")  # O(1)
    s.add_argument("task")  # O(1)
    s = sub.add_parser("free", parents=[common])  # O(1)
    s.add_argument("id")  # O(1)
    s = sub.add_parser("remove", parents=[common])  # O(1)
    s.add_argument("id")  # O(1)
    sub.add_parser("list", parents=[common])  # O(1)
    sub.add_parser("sync", parents=[common])  # O(1)
    sub.add_parser("prune", parents=[common])  # O(1)
    a = ap.parse_args(argv)  # O(1)
    if a.cmd == "prune":  # O(1)
        print("\n".join(prune_file(a.pool)))  # O(a + w)
        return 0  # O(1)
    data, now = load(a.pool), int(time.time() * 1000)  # O(pool bytes)
    try:  # O(1)
        if a.cmd == "add":  # O(1)
            ag = add(data, a.id, a.tier, a.current)  # O(a)
            if state.session_id():  # O(1)
                ag["session"] = state.session_id()  # O(1)
            if a.current:  # O(1)
                ag["busy_since"] = now  # O(1)
        elif a.cmd == "busy":  # O(1)
            ag = busy(data, a.id, a.task, now)  # O(a)
        elif a.cmd == "free":  # O(1)
            ag = free(data, a.id)  # O(a)
        elif a.cmd == "remove":  # O(a)
            if not remove(data, a.id):  # O(a)
                raise KeyError(a.id)  # O(1)
            save(a.pool, data)  # O(pool bytes)
            print(f"removed {a.id}")  # O(1)
            return 0  # O(1)
        elif a.cmd == "list":  # O(1)
            for ag in data.get("agents", []):  # O(a) iterations
                print(line(ag))  # O(1)
            return 0  # O(1)
        else:  # sync | O(a*m + a*T)
            sl = Path(a.pool).parent  # O(1)
            n = synced_count(data, sl)  # O(a*m)
            sync(data, sl, now)  # O(a*m + a*T)
            save(a.pool, data)  # O(pool bytes)
            print(f"synced {n} agent(s)")  # O(1)
            return 0  # O(1)
    except KeyError as e:  # O(1)
        print(f"unknown agent: {e.args[0]}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    save(a.pool, data)  # O(pool bytes)
    print(line(ag))  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
