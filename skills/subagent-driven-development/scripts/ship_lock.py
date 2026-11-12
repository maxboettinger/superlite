#!/usr/bin/env python3
"""Machine-wide ship lock: one lead ships at a time per repository (phase 3).

Lock file `<superlite home>/locks/ship-<repo slug>.lock` = {batch, lead, agent, repo, time} (ms, mode 0600). Every
operation holds an flock on `<lock>.guard`. A lock is stale when its agent is known and not live, or when it is older
than 2 hours. An unreadable, broken or symlinked lock is read as holder `?` (never followed, never released).
Waiters: `<lock>.queue` (JSON list of {batch, lead, agent, time, seen}) serves them first come first served (#588):
a free lock goes to the queue head only; a waiter whose agent is gone, or unseen for 10 minutes, is dropped; a broken
queue file reads empty; `release` also drops the batch's entry.
Library: lock_path, acquire, release, holder. Stdlib only.
"""
import contextlib  # O(1)
import fcntl  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import sys  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
STALE_MS = 2 * 3600 * 1000  # O(1)
QUEUE_STALE_MS = 600000  # a waiter unseen this long leaves the queue | O(1)


def lock_path(repo, home=None):  # O(len(repo))
    slug = re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")  # O(len(repo))
    if not slug:  # O(1)
        raise ValueError(f"no usable repo name in {repo!r}")  # O(1)
    if home is None:  # O(1)
        import state  # O(1)
        home = state.home()  # O(1)
    return Path(home) / "locks" / f"ship-{slug}.lock"  # O(1)


@contextlib.contextmanager
def _guard(p):  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)  # O(1)
    fd = os.open(str(p) + ".guard", os.O_RDWR | os.O_CREAT, 0o600)  # O(1)
    try:  # O(1)
        fcntl.flock(fd, fcntl.LOCK_EX)  # O(1) blocking
        yield  # O(1)
    finally:  # O(1)
        os.close(fd)  # O(1) releases the flock


def _read(p):  # O(size of the lock file)
    try:  # O(1)
        st = os.lstat(p)  # O(1)
    except FileNotFoundError:  # O(1)
        return None  # O(1)
    unknown = {"batch": "?", "lead": "?", "agent": "?", "repo": "?", "time": int(st.st_mtime * 1000)}  # O(1)
    try:  # O(1)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)  # O(1)
        with os.fdopen(fd, "r") as f:  # O(1)
            obj = json.load(f)  # O(size)
    except (OSError, ValueError):  # O(1) symlink, unreadable or broken
        return unknown  # O(1)
    return obj if isinstance(obj, dict) and obj.get("batch") and isinstance(obj.get("time"), int) else unknown  # O(1)


def _stale(h, live, now_ms):  # O(1)
    agent = h.get("agent")  # O(1)
    if agent not in (None, "?") and live is not None:  # O(1) Herdr readable: only a gone agent makes it stale
        return agent not in live  # O(1)
    return now_ms - h["time"] > STALE_MS  # O(1)


def _write(p, obj):  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".")  # O(1) mode 0600
    try:  # O(1)
        with os.fdopen(fd, "w") as f:  # O(1)
            json.dump(obj, f)  # O(1)
        os.replace(tmp, p)  # O(1)
    except BaseException:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


def _qpath(p):  # O(1)
    return Path(str(p) + ".queue")  # O(1)


def _qread(p):  # O(size of the queue file)
    try:  # O(1)
        fd = os.open(_qpath(p), os.O_RDONLY | os.O_NOFOLLOW)  # O(1)
        with os.fdopen(fd, "r") as f:  # O(1)
            obj = json.load(f)  # O(size)
    except (OSError, ValueError):  # O(1) absent, symlinked or broken
        return []  # O(1)
    return obj if isinstance(obj, list) and all(isinstance(e, dict) for e in obj) else []  # O(q)


def _prune(q, holder_batch, live, now_ms):  # O(q)
    keep = []  # O(1)
    for e in q:  # O(q)
        agent = e.get("agent")  # O(1)
        seen = e.get("seen")  # O(1)
        if agent not in (None, "?") and live is not None and agent not in live:  # O(1)
            continue  # O(1) its agent is gone
        if not isinstance(seen, int) or now_ms - seen > QUEUE_STALE_MS or e.get("batch") == holder_batch:  # O(1)
            continue  # O(1)
        keep.append(e)  # O(1)
    return keep  # O(q)


def acquire(p, owner, live, now_ms):  # O(q)
    """Take the lock in request order; {"acquired", "holder" (previous or blocking one), "took_over", "place" (1-based wait, 0 when acquired), "queued", "first" (queue head or None)}."""
    p = Path(p)  # O(1)
    with _guard(p):  # O(q)
        h = _read(p)  # O(1)
        old = _qread(p)  # O(q)
        me = owner["batch"]  # O(1)
        live_holder = h is not None and not _stale(h, live, now_ms)  # O(1)
        q = _prune(old, h["batch"] if live_holder else None, live, now_ms)  # O(q)
        if h is not None and h["batch"] == me:  # O(1)
            rest = [e for e in q if e.get("batch") != me]  # O(q)
            if rest != old:  # O(q)
                _write(_qpath(p), rest)  # O(q)
            return {"acquired": True, "holder": None, "took_over": False, "place": 0, "queued": len(rest), "first": None}  # O(1) re-entry, nothing else written
        others = [e for e in q if e.get("batch") != me]  # O(q)
        if live_holder or (q and q[0].get("batch") != me):  # O(1)
            mine = next((e for e in q if e.get("batch") == me), None)  # O(q)
            if mine is None:  # O(1)
                q.append({**{k: owner.get(k) for k in ("batch", "lead", "agent")}, "time": now_ms, "seen": now_ms})  # O(1)
            else:  # O(1)
                mine["seen"] = now_ms  # O(1)
            if q != old:  # O(q)
                _write(_qpath(p), q)  # O(q)
            place = next(i for i, e in enumerate(q) if e.get("batch") == me) + 1  # O(q)
            return {"acquired": False, "holder": h if live_holder else None, "took_over": False, "place": place, "queued": len(q), "first": q[0]}  # O(1)
        _write(p, {**{k: owner.get(k) for k in ("batch", "lead", "agent", "repo")}, "time": now_ms})  # O(1)
        if others != old:  # O(q)
            _write(_qpath(p), others)  # O(q)
        return {"acquired": True, "holder": h, "took_over": h is not None, "place": 0, "queued": len(others), "first": None}  # O(1)


def release(p, batch):  # O(q)
    p = Path(p)  # O(1)
    with _guard(p):  # O(q)
        old = _qread(p)  # O(q)
        rest = [e for e in old if e.get("batch") != batch]  # O(q)
        if rest != old:  # O(q)
            _write(_qpath(p), rest)  # O(q)
        h = _read(p)  # O(1)
        if h is None or h["batch"] == "?" or h["batch"] != batch:  # O(1)
            return False  # O(1)
        os.unlink(p)  # O(1)
        return True  # O(1)


def holder(p):  # O(1)
    p = Path(p)  # O(1)
    if not p.parent.exists():  # O(1)
        return None  # O(1)
    with _guard(p):  # O(1)
        return _read(p)  # O(1)
