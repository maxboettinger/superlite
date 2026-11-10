#!/usr/bin/env python3
"""Append-only incident log: add, hotspots, summary. Stdlib only.
--plan P (anywhere): accepted and ignored; lead briefs pass it to every sl call (#336)."""
# Complexity notation:
#   i = entries in the log, B = bytes of the log, f = distinct files in the log, d = distinct values of one field,
#   k = entries printed (--max), c = length of the context text, w = width of one log line, a = length of --files
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import sys  # O(1)
import time  # O(1)
from collections import Counter  # O(1)
from pathlib import Path  # O(1)

DEFAULT_LOG = ".superlite/incidents.jsonl"  # O(1)
KINDS = ("test-failure", "exception", "workaround", "spec-ambiguity",  # O(1)
         "assumption", "flaky", "perf", "unsure", "verified")  # O(1)
CONFIDENCE = ("low", "medium", "high")  # O(1)
MAX_CONTEXT = 200  # O(1)

if os.name == "nt":  # O(1)
    import msvcrt  # O(1)

    def _lock(f):  # O(1) per attempt
        f.seek(0)  # O(1)
        while True:  # O(1) per attempt: retries until the lock is free (contention wait)
            try:  # O(1)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # O(1)
                return  # O(1)
            except OSError:  # O(1)
                time.sleep(0.01)  # O(1) 10 ms sleep per retry

    def _unlock(f):  # O(1)
        f.seek(0)  # O(1)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)  # O(1)
else:  # O(1)
    import fcntl  # O(1)

    def _lock(f):  # O(1)
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # O(1) + blocks until the lock is free

    def _unlock(f):  # O(1)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # O(1)


def _die(msg):  # O(1)
    print(f"error: {msg}", file=sys.stderr)  # O(1)
    sys.exit(2)  # O(1)


def _clean(s):  # O(len(s))
    return s.encode("utf-8", "surrogateescape").decode("utf-8", "replace") if isinstance(s, str) else s  # O(len(s))


def make_entry(file, line, context, agent=None, kind=None, resolution=None,  # O(c)
               confidence=None):
    """One validated log entry; ValueError on bad input."""
    file, context, agent, resolution = _clean(file), _clean(context), _clean(agent), _clean(resolution)  # O(c)
    if line < 0:  # O(1)
        raise ValueError("line must be >= 0")  # O(1)
    if kind is not None and kind not in KINDS:  # O(1)
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")  # O(1)
    if confidence is not None and confidence not in CONFIDENCE:  # O(1)
        raise ValueError(f"confidence must be one of: {', '.join(CONFIDENCE)}")  # O(1)
    if not file or not context:  # O(1)
        raise ValueError("file and context are required")  # O(1)
    ctx = context  # O(1)
    if len(ctx) > MAX_CONTEXT:  # O(1)
        ctx = ctx[:MAX_CONTEXT - 1] + "…"  # O(c)
    entry = {"file": file, "line": int(line), "context": ctx}  # O(c)
    for key, val in (("agent", agent), ("kind", kind), ("resolution", resolution),  # O(1) iterations (4)
                     ("confidence", confidence)):
        if val is not None:  # O(1)
            entry[key] = val  # O(1)
    now = time.time()  # O(1)
    entry["time"] = time.strftime("%H:%M:%S", time.localtime(now))  # O(1)
    entry["epoch"] = now  # comparable with a test run's start, across midnight too (#101) | O(1)
    return entry  # O(1)


def append(log, entries):  # O(total c) + one open, lock and fsync for the whole batch
    """Append entries (dicts from make_entry) under one lock: one open and one fsync."""
    if not entries:  # O(1)
        return  # O(1)
    data = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries).encode("utf-8")  # O(total c)
    path = Path(log)  # O(1)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    with open(path, "ab+") as f:  # O(1)
        _lock(f)  # O(1)
        try:  # O(1)
            f.seek(0, os.SEEK_END)  # O(1)
            f.write(data)  # O(total c) append
            f.flush()  # O(1)
            os.fsync(f.fileno())  # O(total c) I/O flush
        finally:  # O(1)
            _unlock(f)  # O(1)


def cmd_add(a):  # O(c) + file append O(c) + fsync
    try:  # O(1)
        entry = make_entry(a.file, a.line, a.context, a.agent, a.kind, a.resolution,  # O(c)
                           a.confidence)
    except ValueError as e:  # O(1)
        _die(str(e))  # O(1)
    append(a.log, [entry])  # O(c) + fsync
    return 0  # O(1)


def _read(log):  # O(B)
    path = Path(log)  # O(1)
    if not path.exists():  # O(1)
        return []  # O(1)
    out = []  # O(1)
    with open(path, encoding="utf-8", errors="replace") as f:  # O(1) open
        for ln in f:  # O(i) iterations
            ln = ln.strip()  # O(w)
            if not ln:  # O(1)
                continue  # O(1)
            try:  # O(1)
                e = json.loads(ln)  # O(w)
            except json.JSONDecodeError:  # O(1)
                continue  # O(1)
            if isinstance(e, dict) and "file" in e and "line" in e:  # O(1)
                out.append(e)  # O(1)
    return out  # O(1)


def _norm(p):  # O(len(path))
    return str(p).replace("\\", "/")  # O(len(path))


TOOL_KINDS = {"probe": "probe_run", "contract": "pt_review"}  # --kind names for the tools that log without a kind | O(1)


def _newest(entries):  # O(i)
    """Location -> its newest entry (the one the packet and `finish` count), in first-seen order."""
    newest = {}  # O(1)
    for e in entries:  # O(i)
        newest[(_norm(e["file"]), e["line"])] = e  # O(1)
    return newest  # O(1)


def _tool(e):  # O(1)
    return e.get("agent") or e.get("tool")  # O(1)


def _bulk_resolve(a, entries, pt_review):  # O(i) + one locked append
    """Close every open location whose newest entry has kind K or was logged by tool K (#416)."""
    want = TOOL_KINDS.get(a.kind, a.kind)  # O(1)
    is_open = lambda e: str(e.get("resolution", "")).lower() not in pt_review.RESOLVED  # O(1)
    newest = _newest(entries)  # O(i)
    opened = [e for e in newest.values() if is_open(e)]  # O(l)
    hit = [e for e in opened if e.get("kind") == a.kind or want in (e.get("kind"), _tool(e))
           or (a.kind == "unknown" and not e.get("kind"))]  # `unknown` is how the no-match list names a kind-less entry | O(l)
    if not hit:  # O(1)
        kinds = Counter(e.get("kind") or "unknown" for e in opened)  # O(l)
        tools = Counter(_tool(e) for e in opened if _tool(e))  # O(l)
        lists = [f"open by kind: {', '.join(f'{k}={n}' for k, n in sorted(kinds.items()))}"]  # O(k log k)
        if tools:  # O(1)
            lists.append(f"by agent: {', '.join(f'{k}={n}' for k, n in sorted(tools.items()))}")  # O(t log t)
        _die(f"no open incident of kind {a.kind}; " + ("; ".join(lists) if opened else "none is open"))  # O(1)
    batch = []  # O(1)
    for base in hit:  # O(l)
        kind = base.get("kind") if base.get("kind") in KINDS else None  # O(1)
        try:  # O(1)
            batch.append(make_entry(base["file"], base["line"], f"{a.resolution}: {a.ruling}", a.agent, kind, a.resolution))  # O(c)
        except ValueError as e:  # O(1)
            _die(str(e))  # O(1)
    append(a.log, batch)  # O(total c) + one fsync
    for base in hit:  # O(l)
        print(f"{a.resolution} {base['file']}:{base['line']}")  # O(1)
    print(f"closed {len(hit)} of kind {a.kind} ({a.resolution})")  # O(1)
    return 0  # O(1)


def cmd_resolve(a):  # O(B) + one locked append
    """Close the incident at --file/--line (or every open one of --kind K) with a ruling: append an entry with that
    location's kind and a resolved resolution, so the packet and `finish` (newest non-verified entry per location)
    stop counting it as open."""
    import pt_review  # the resolutions the packet counts as closed; lazy, `add` stays light | O(module)
    if a.resolution not in pt_review.RESOLVED:  # O(1)
        _die(f"--resolution must be one of: {', '.join(sorted(pt_review.RESOLVED))}")  # O(1)
    if not a.ruling:  # O(1)
        _die("give the ruling: --ruling TEXT (or --reason TEXT)")  # O(1)
    if a.kind and (a.file is not None or a.line is not None):  # O(1)
        _die("give --file F --line N, or --kind K, not both")  # O(1)
    if not a.kind and (a.file is None or a.line is None):  # O(1)
        _die("give --file F --line N, or --kind K")  # O(1)
    entries = [e for e in _read(a.log) if e.get("kind") != "verified"]  # a `verified` entry is no incident | O(B)
    if a.kind:  # O(1)
        return _bulk_resolve(a, entries, pt_review)  # O(i)
    want = (_norm(a.file), a.line)  # O(1)
    at = [e for e in entries if (_norm(e["file"]), e["line"]) == want]  # O(i)
    if not at:  # O(1)
        newest = _newest(entries)  # location -> its newest entry, as the packet and `finish` count open | O(i)
        opened = sorted(f"{f}:{n}" for (f, n), e in newest.items()  # O(l log l)
                        if str(e.get("resolution", "")).lower() not in pt_review.RESOLVED)
        _die(f"no incident at {want[0]}:{a.line}" + (f"; open: {', '.join(opened[:20])}" if opened else "; none is open"))  # O(1)
    base = at[-1]  # the location's newest entry | O(1)
    kind = base.get("kind") if base.get("kind") in KINDS else None  # O(1)
    try:  # O(1)
        entry = make_entry(base["file"], a.line, f"{a.resolution}: {a.ruling}", a.agent, kind, a.resolution)  # the logged spelling | O(c)
    except ValueError as e:  # O(1)
        _die(str(e))  # O(1)
    append(a.log, [entry])  # O(c) + fsync
    print(f"{a.resolution} {base['file']}:{a.line}")  # O(1)
    return 0  # O(1)


def cmd_hotspots(a):  # O(B + i log i)
    entries = _read(a.log)  # O(B)
    if a.files:  # O(1)
        wanted = {_norm(x.strip()) for arg in a.files for x in arg.split(",") if x.strip()}  # O(a + f)
        entries = [e for e in entries if _norm(e["file"]) in wanted]  # O(i)
    counts = Counter((_norm(e["file"]), e["line"]) for e in entries  # O(i) Counter
                     if e.get("kind") != "verified")  # O(1)
    import pt_review  # the resolutions the packet counts as closed; lazy | O(module)
    newest = {}  # location -> its newest non-verified entry, as the packet and `finish` count open | O(1)
    for e in entries:  # O(i)
        if e.get("kind") != "verified":  # O(1)
            newest[(_norm(e["file"]), e["line"])] = e  # O(1)
    entries = [e for e in entries  # one entry per location, none of the resolved | O(i)
               if e.get("kind") == "verified"
               or (newest[(_norm(e["file"]), e["line"])] is e
                   and str(e.get("resolution", "")).lower() not in pt_review.RESOLVED)]

    def key(e):  # O(1) per call
        loc = (_norm(e["file"]), e["line"])  # O(1)
        verified = e.get("kind") == "verified"  # O(1)
        repeated = not verified and counts[loc] > 1  # O(1)
        unresolved = not verified and e.get("resolution") in (None, "open")  # O(1)
        low = e.get("confidence") == "low"  # O(1)
        return (0 if repeated else 1, 0 if unresolved else 1,  # O(1)
                0 if low else 1, loc[0], loc[1])  # O(1)

    entries.sort(key=key)  # O(i log i)
    for e in entries[:a.max]:  # O(min(i, k)) iterations
        print(json.dumps(e, ensure_ascii=False))  # O(w)
    return 0  # O(1)


def cmd_summary(a):  # O(B + i + d log d + f)
    entries = _read(a.log)  # O(B)
    print(f"total: {len(entries)}")  # O(1)
    for name in ("kind", "resolution"):  # O(1) iterations (2)
        c = Counter(e.get(name, "-") for e in entries)  # O(i)
        print(f"{name}: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))  # O(d log d)
    c = Counter(_norm(e["file"]) for e in entries)  # O(i)
    print("files: " + ", ".join(f"{k}={v}" for k, v in c.most_common(10)))  # O(f) most_common(10)
    return 0  # O(1)


def main(argv=None):  # O(1) parser setup + command cost
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    import autocommit  # O(1)
    import state  # O(1)
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    argv, plan = autocommit.split_plan(argv)  # --plan P is accepted and ignored (#336) | O(len argv)
    if plan == "":  # O(1) --plan without a value
        print("usage: incident.py add|resolve|hotspots|summary ... [--plan P]", file=sys.stderr)  # O(1)
        return 2  # O(1)
    p = argparse.ArgumentParser(prog="incident.py", epilog="--plan P (anywhere): accepted and ignored; lead briefs pass it to every sl call (#336)")  # O(1)
    log = state.incident_log()  # the session's run, else ./.superlite (#87) | O(d)
    sub = p.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("add")  # O(1)
    s.add_argument("--file", required=True)  # O(1)
    s.add_argument("--line", type=int, required=True)  # O(1)
    s.add_argument("--context", required=True)  # O(1)
    s.add_argument("--agent")  # O(1)
    s.add_argument("--kind", choices=KINDS)  # `--help` lists them (#85) | O(1)
    s.add_argument("--resolution")  # O(1)
    s.add_argument("--confidence")  # O(1)
    s.add_argument("--log", default=log)  # O(1)
    s.set_defaults(fn=cmd_add)  # O(1)
    s = sub.add_parser("resolve", help="close the incident at FILE:LINE, or every open one of --kind K, with a ruling (#116, #416)")  # O(1)
    s.add_argument("--file")  # O(1)
    s.add_argument("--line", type=int)  # O(1)
    s.add_argument("--kind", help="close every open incident of this kind or logged by this tool (probe = probe_run, contract = pt_review); not with --file/--line")  # O(1)
    s.add_argument("--ruling", "--reason", dest="ruling", help="why it is closed; becomes the entry's context")  # O(1)
    s.add_argument("--resolution", default="resolved", help="fixed, resolved, closed, wontfix or accepted")  # O(1)
    s.add_argument("--agent")  # O(1)
    s.add_argument("--log", default=log)  # O(1)
    s.set_defaults(fn=cmd_resolve)  # O(1)
    s = sub.add_parser("hotspots")  # O(1)
    s.add_argument("--files", nargs="+", help="paths, separate or comma-separated")  # O(1)
    s.add_argument("--log", default=log)  # O(1)
    s.add_argument("--max", type=int, default=30)  # O(1)
    s.set_defaults(fn=cmd_hotspots)  # O(1)
    s = sub.add_parser("summary")  # O(1)
    s.add_argument("--log", default=log)  # O(1)
    s.set_defaults(fn=cmd_summary)  # O(1)
    a = p.parse_args(argv)  # O(len(argv))
    return a.fn(a)  # O(cmd cost)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
