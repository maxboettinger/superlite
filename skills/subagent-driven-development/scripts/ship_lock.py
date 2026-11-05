#!/usr/bin/env python3
"""Machine-wide ship lock: one lead ships at a time per repository (phase 3).

Lock file `<superlite home>/locks/ship-<repo slug>.lock` = {batch, lead, agent, repo, time} (ms, mode 0600). Every
operation holds an flock on `<lock>.guard`. A lock is stale when its agent is known and not live, or when it is older
than 2 hours. An unreadable, broken or symlinked lock is read as holder `?` (never followed, never released).
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


def acquire(p, owner, live, now_ms):  # O(1)
    """Take the lock; {"acquired", "holder" (the previous or blocking one), "took_over"}."""
    p = Path(p)  # O(1)
    with _guard(p):  # O(1)
        h = _read(p)  # O(1)
        if h is not None and h["batch"] == owner["batch"]:  # O(1)
            return {"acquired": True, "holder": None, "took_over": False}  # O(1) re-entry, nothing written
        if h is not None and not _stale(h, live, now_ms):  # O(1)
            return {"acquired": False, "holder": h, "took_over": False}  # O(1)
        _write(p, {**{k: owner.get(k) for k in ("batch", "lead", "agent", "repo")}, "time": now_ms})  # O(1)
        return {"acquired": True, "holder": h, "took_over": h is not None}  # O(1)


def release(p, batch):  # O(1)
    p = Path(p)  # O(1)
    with _guard(p):  # O(1)
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
