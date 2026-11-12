#!/usr/bin/env python3
"""Arrival-order queue of the runs waiting for a toolchain's full-suite lock (B153, #655).

`<lock>.queue` holds a JSON list of waiters `{"id", "pid", "root", "task", "time", "seen"}`, oldest first,
changed under an flock on `<lock>.guard`; every write goes through a temp file and `os.replace`.
`join` adds a waiter (once per id), drops the dead ones (pid gone, or unseen for `STALE` s) and returns its place;
`leave` removes it. A queue file that is missing or not a JSON list reads empty.
"""
from __future__ import annotations

import contextlib  # O(1)
import json  # O(1)
import os  # O(1)
import tempfile  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

try:  # O(1)
    import fcntl  # O(1)
except ImportError:  # O(1)
    fcntl = None  # O(1)

STALE = 600.0  # O(1) seconds a waiter may go unseen before its place is dropped


def pid_alive(pid):  # O(1) True when a process with this pid exists; PermissionError counts alive
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:  # O(1)
        return False  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1)
    except PermissionError:  # O(1)
        return True  # O(1)
    except (OSError, OverflowError, ValueError):  # O(1)
        return False  # O(1)
    return True  # O(1)


def queue_path(lock):  # O(1) the queue file next to a lock file
    return Path(str(lock) + ".queue")  # O(1)


def read(lock):  # O(file) the queue entries, [] when the file is missing or broken
    if queue_path(lock).is_symlink():  # O(1)
        return []  # O(1)
    try:  # O(1)
        data = json.loads(queue_path(lock).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return []  # O(1)
    return [e for e in data if isinstance(e, dict) and isinstance(e.get("id"), str)] if isinstance(data, list) else []  # O(n)


def write(lock, entries):  # O(n) replace the queue file through a temp file
    path = queue_path(lock)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as f:  # O(1)
            f.write(json.dumps(entries))  # O(n)
        os.replace(tmp, path)  # O(1)
    except OSError:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


@contextlib.contextmanager
def guarded(lock):  # O(1) hold the flock on `<lock>.guard`
    Path(lock).parent.mkdir(parents=True, exist_ok=True, mode=0o700)  # O(1)
    fd = os.open(str(lock) + ".guard", os.O_RDWR | os.O_CREAT, 0o600)  # O(1)
    try:  # O(1)
        if fcntl is not None:  # O(1)
            fcntl.flock(fd, fcntl.LOCK_EX)  # O(1)
        yield  # O(1)
    finally:  # O(1)
        os.close(fd)  # O(1)


def seen_ok(entry, now):  # O(1) True when the entry was seen within STALE seconds
    seen = entry.get("seen", entry.get("time"))  # O(1)
    return isinstance(seen, (int, float)) and not isinstance(seen, bool) and now - seen <= STALE  # O(1)


def snapshot(entries, entry_id):  # O(n) place, queued and first entry for an id
    ids = [e["id"] for e in entries]  # O(n)
    return {"place": ids.index(entry_id) + 1 if entry_id in ids else len(ids) + 1, "queued": len(ids), "first": entries[0] if entries else None}  # O(n)


def join(lock, entry, alive=pid_alive, now=None):  # O(n) add or refresh a waiter; returns {"place", "queued", "first"}
    now = time.time() if now is None else now  # O(1)
    with guarded(lock):  # O(1)
        old = read(lock)  # O(file)
        kept = [e for e in old if e["id"] != entry["id"] and seen_ok(e, now) and alive(e.get("pid"))]  # O(n)
        mine = next((e for e in old if e["id"] == entry["id"]), None)  # O(n)
        if mine is not None:  # a refresh keeps the arrival place | O(n)
            slot = [e["id"] for e in old].index(entry["id"])  # O(n)
            before = len([e for e in old[:slot] if e["id"] != entry["id"] and seen_ok(e, now) and alive(e.get("pid"))])  # O(n)
            kept.insert(before, dict(entry, time=mine.get("time", entry.get("time"))))  # O(n)
        else:  # O(1)
            kept.append(dict(entry))  # O(1)
        if kept != old:  # O(n)
            write(lock, kept)  # O(n)
        return snapshot(kept, entry["id"])  # O(n)


def leave(lock, entry_id):  # O(n) remove a waiter; an unknown id changes nothing
    with guarded(lock):  # O(1)
        old = read(lock)  # O(file)
        kept = [e for e in old if e["id"] != entry_id]  # O(n)
        if len(kept) != len(old):  # O(1)
            write(lock, kept)  # O(n)
