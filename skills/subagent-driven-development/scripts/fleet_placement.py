#!/usr/bin/env python3
"""Automatic placement of fleet workers (#919): which machine, this one or a saved Herdr machine, a new worker starts on.

`room(sd)` runs the `remote_room` command of `<home>/machine.json` (cached in `<sd>/room.json` for 60 s) and maps its machines to
`{"local": {...}, "<label>": {"state", "room"}}`; any failure means `{"local": unknown}`. `choose(sd, role, project)` returns a machine label or None (local):
a remote scores its room minus its live workers minus a margin (`remote_margin` of machine.json, an int, default 2), local scores its room minus its live workers, ties go local.
`skip(sd, label, why)` keeps a machine out of placement for some minutes; `set_mode(sd, "local"|"spread")` is the `placement` key of fleet.json.
A failure here never raises: it means local.
"""
# Complexity notation:
# w = workers, m = machines, k = keys of a json file
import contextlib  # O(1)
import fcntl  # O(1)
import json  # O(1)
import os  # O(1)
import socket  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

MARGIN = 2  # O(1) a remote must beat local by this much: the push and the pull cost something
TIMEOUT = 20  # O(1) seconds for the room command
LIVE = ("ready", "busy", "starting")  # O(1)
ROLES = ("implementer", "fixer", "package-reviewer", "final-reviewer", "research")  # O(1) roles that may run remote
MODES = ("spread", "local")  # O(1)
UNKNOWN = {"local": {"state": "unknown", "room": None}}  # O(1)


def _machine_cfg(key):  # O(k): an argv list of machine.json or None
    try:  # O(1)
        v = json.loads((state.home() / "machine.json").read_text(encoding="utf-8"))[key]  # O(k)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return None  # O(1)
    return list(v) if isinstance(v, list) and v and all(isinstance(x, str) for x in v) else None  # O(1)


def _margin():  # O(k): remote_margin of machine.json, an int (negative allowed); anything else means MARGIN
    try:  # O(1)
        v = json.loads((state.home() / "machine.json").read_text(encoding="utf-8"))["remote_margin"]  # O(k)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return MARGIN  # O(1)
    return v if isinstance(v, int) and not isinstance(v, bool) else MARGIN  # O(1)


def _json(p):  # O(k): the object in a file, {} when unreadable
    try:  # O(1)
        v = json.loads(Path(p).read_text(encoding="utf-8"))  # O(k)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return v if isinstance(v, dict) else {}  # O(1)


def _local_names():  # O(1)
    try:  # O(1)
        h = socket.gethostname().strip().lower()  # O(1)
    except OSError:  # O(1)
        return set()  # O(1)
    return {h, h.split(".")[0]} - {""}  # O(1)


def _write(p, data):  # O(k): replace a json file whole through a temp file in its folder, so a reader sees the old or the new content
    p = Path(p)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:  # O(1)
            fh.write(json.dumps(data))  # O(k)
        os.replace(tmp, p)  # O(1) atomic rename
    except BaseException:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


@contextlib.contextmanager
def _lock(sd):  # O(1) plus wait: its own lock file, so a caller holding fs.locked(sd) cannot deadlock here
    with open(Path(sd) / "room-skip.json.lock", "a") as lf:  # O(1)
        fcntl.flock(lf, fcntl.LOCK_EX)  # O(1) blocks until free
        yield  # O(1)


def _fetch():  # O(m): the mapped room of one command run, or None
    argv = _machine_cfg("remote_room")  # O(k)
    if not argv:  # O(1)
        return None  # O(1)
    try:  # O(1)
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT)  # O(1) bounded
        if r.returncode != 0:  # O(1)
            return None  # O(1)
        rows = json.loads(r.stdout)["machines"]  # O(m)
        names, out = _local_names(), {}  # O(1)
        for row in rows:  # O(m)
            name = str(row["name"])  # O(1)
            room = row.get("room")  # O(1)
            out["local" if name.lower() in names else name] = {"state": str(row.get("state", "unknown")), "room": room if isinstance(room, (int, float)) else None}  # O(1)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):  # O(1)
        return None  # O(1)
    out.setdefault("local", dict(UNKNOWN["local"]))  # O(1)
    return out  # O(1)


def room(sd, ttl=60.0, now=None):  # O(m)
    now = time.time() if now is None else now  # O(1)
    cache = Path(sd) / "room.json"  # O(1)
    c = _json(cache)  # O(k)
    if isinstance(c.get("room"), dict) and isinstance(c.get("at"), (int, float)) and 0 <= now - c["at"] < ttl:  # O(1)
        return c["room"]  # O(1)
    got = _fetch()  # O(m)
    if got is None:  # O(1)
        return {"local": dict(UNKNOWN["local"])}  # O(1)
    try:  # O(1)
        _write(cache, {"at": now, "room": got})  # O(m)
    except OSError:  # O(1)
        pass  # O(1)
    return got  # O(1)


def enabled(sd):  # O(w)
    mode = fs.load(sd).get("placement")  # O(w)
    return bool(_machine_cfg("remote_room") and _machine_cfg("remote_tree")) and mode != "local"  # O(k)


def set_mode(sd, mode):  # O(w)
    if mode not in MODES:  # O(1)
        raise ValueError("placement mode must be one of %s, not %r" % (", ".join(MODES), mode))  # O(1)
    with fs.locked(sd):  # O(1)
        data = fs.load(sd)  # O(w)
        data["placement"] = mode  # O(1)
        fs.save(sd, data)  # O(w)


def _skips(sd):  # O(k)
    return _json(Path(sd) / "room-skip.json")  # O(k)


def skip(sd, label, why, minutes=10.0, now=None):  # O(k)
    now = time.time() if now is None else now  # O(1)
    try:  # O(1)
        with _lock(sd):  # the read-modify-write of two parallel rounds must not drop an entry | O(1) plus wait
            d = _skips(sd)  # O(k)
            d[label] = {"until": now + minutes * 60, "why": why}  # O(1)
            _write(Path(sd) / "room-skip.json", d)  # O(k)
    except OSError:  # O(1)
        pass  # O(1)


def _swift(project):  # O(entries)
    p = Path(project)  # O(1)
    try:  # O(1)
        if (p / "Package.swift").exists() or any(c.suffix in (".xcodeproj", ".xcworkspace") for c in p.iterdir()):  # O(entries)
            return True  # O(1)
    except OSError:  # O(1)
        return False  # O(1)
    return _json(p / ".superlite" / "test-cmd.json").get("language") == "swift"  # O(k)


def _live(sd):  # O(w): live workers per machine, None key = local
    out = {}  # O(1)
    for w in fs.load(sd).get("workers", {}).values():  # O(w)
        if isinstance(w, dict) and w.get("state") in LIVE:  # O(1)
            out[w.get("machine") or None] = out.get(w.get("machine") or None, 0) + 1  # O(1)
    return out  # O(1)


def choose(sd, role, project, now=None):  # O(w + m)
    try:  # O(1)
        if role not in ROLES or not enabled(sd) or _swift(project):  # O(entries)
            return None  # O(1)
        now = time.time() if now is None else now  # O(1)
        rm, live, skips = room(sd, now=now), _live(sd), _skips(sd)  # O(w + m)
        saved = {m.get("label") for m in hc.machines() if m.get("enabled")} if len(rm) > 1 else set()  # O(m)
        loc = rm.get("local", {}).get("room")  # O(1)
        best, best_score = None, (loc if isinstance(loc, (int, float)) else 0) - live.get(None, 0)  # local's score; a tie keeps local | O(1)
        margin = _margin()  # O(k)
        for label, info in rm.items():  # O(m)
            if label == "local" or label not in saved or info.get("state") != "ready" or not isinstance(info.get("room"), (int, float)):  # O(1)
                continue  # O(1)
            until = (skips.get(label) or {}).get("until")  # O(1)
            if isinstance(until, (int, float)) and until > now:  # O(1)
                continue  # O(1)
            score = info["room"] - live.get(label, 0) - margin  # O(1)
            if score > 0 and score > best_score:  # O(1)
                best, best_score = label, score  # O(1)
        return best  # O(1)
    except Exception:  # O(1) placement never blocks a spawn
        return None  # O(1)
