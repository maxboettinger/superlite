#!/usr/bin/env python3
"""Machine-wide load (#560): leads, fixers and xcodebuild processes counted across repositories.

`register(name, role, root)` writes `<home>/load/<name>.json` (`{"role", "root", "since"}`). `count` crosses that
registry with the live Herdr agent names (a registered name not live does not count; one older than 24 h is dropped)
and adds `xcodebuild` processes. `limit()` is `SUPERLITE_MACHINE_LIMIT`, else `<home>/machine.json` `{"limit": N}`,
else max(2, min(cores // 3, memory GB // 8)); 0 means no limit. Busy means total >= limit. `gate` waits up to
`wait_s` for the machine to drop below the limit and returns None to go ahead, else the busy line.
"""
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from history import home  # $SUPERLITE_HOME | O(1)

STALE_S = 24 * 3600  # O(1)
COUNTED = "counted machine-wide: leads and fixers in live Herdr panes, xcodebuild processes"  # O(1)


def _dir() -> Path:  # O(1)
    return home() / "load"  # O(1)


def register(name: str, role: str, root: str) -> None:  # O(1)
    d = _dir()  # O(1)
    d.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = d / f".{name}.{os.getpid()}.tmp"  # O(1)
    tmp.write_text(json.dumps({"role": role, "root": root, "since": time.time()}))  # O(1)
    os.replace(tmp, d / f"{name}.json")  # atomic | O(1)


def _live_names() -> set:  # O(a)
    import herdr_client  # O(1)
    return {a["name"] for a in herdr_client.agents()}  # O(a)


def _procs() -> list:  # O(p)
    try:  # O(1)
        r = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=10)  # O(p)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return []  # O(1)
    return r.stdout.splitlines()  # O(p)


def _cores() -> int:  # O(1)
    return os.cpu_count() or 1  # O(1)


def _mem_gb() -> int:  # O(1)
    try:  # O(1)
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1 << 30)  # O(1)
    except (ValueError, OSError, AttributeError):  # O(1)
        return 16  # O(1)


def count(live=None, procs=None) -> dict:  # O(registry + p)
    herdr = True  # O(1)
    if live is None:  # O(1)
        try:  # O(1)
            live = _live_names()  # O(a)
        except Exception:  # herdr down: processes only | O(1)
            live, herdr = set(), False  # O(1)
    if procs is None:  # O(1)
        procs = _procs()  # O(p)
    leads = fixers = 0  # O(1)
    now = time.time()  # O(1)
    for f in sorted(_dir().glob("*.json")) if _dir().is_dir() else []:  # O(registry)
        try:  # O(1)
            e = json.loads(f.read_text())  # O(1)
        except (OSError, ValueError):  # O(1)
            continue  # O(1)
        if f.stem in live:  # O(1)
            role = str(e.get("role", ""))  # O(1)
            leads += role == "lead"  # O(1)
            fixers += role.startswith("fixer")  # O(1)
        elif now - float(e.get("since", now)) > STALE_S:  # O(1)
            f.unlink(missing_ok=True)  # O(1)
    xcb = sum(1 for p in procs if os.path.basename(p.strip()) == "xcodebuild")  # O(p)
    return {"leads": leads, "fixers": fixers, "xcodebuild": xcb, "total": leads + fixers + xcb, "herdr": herdr}  # O(1)


def limit() -> tuple:  # O(1)
    env = os.environ.get("SUPERLITE_MACHINE_LIMIT")  # O(1)
    if env is not None and env.strip().isdigit():  # O(1)
        return int(env), "SUPERLITE_MACHINE_LIMIT"  # O(1)
    f = home() / "machine.json"  # O(1)
    try:  # O(1)
        return int(json.loads(f.read_text())["limit"]), str(f)  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        pass  # O(1)
    return max(2, min(_cores() // 3, _mem_gb() // 8)), "default"  # O(1)


def _parts(c: dict) -> str:  # O(1)
    pl = lambda n, w: f"{n} {w}" + ("" if n == 1 else "s")  # O(1)
    return f"{pl(c['leads'], 'lead')}, {pl(c['fixers'], 'fixer')}, {c['xcodebuild']} xcodebuild = {c['total']}"  # O(1)


def gate(what: str, wait_s: float, over: bool = False, poll_s: float = 10.0):  # O(wait_s / poll_s * count)
    lim, src = limit()  # O(1)
    if lim == 0:  # O(1)
        return None  # O(1)
    t0 = time.monotonic()  # O(1)
    waited = False  # O(1)
    while True:  # O(wait_s / poll_s)
        c = count()  # O(registry + p)
        el = int(time.monotonic() - t0)  # O(1)
        if c["total"] < lim:  # O(1)
            if waited:  # O(1)
                print(f"machine below its limit after {el} s: {_parts(c)} of limit {lim}; starting {what}", file=sys.stderr)  # O(1)
            return None  # O(1)
        if over:  # O(1)
            print("machine limit overridden (--over-limit)", file=sys.stderr)  # O(1)
            return None  # O(1)
        if time.monotonic() - t0 >= wait_s:  # O(1)
            return f"machine busy after {el} s: {_parts(c)} of limit {lim}"  # O(1)
        if not waited:  # O(1)
            print(f"machine busy: {_parts(c)} of limit {lim} ({COUNTED}; limit {lim} from {src}); waiting up to {int(wait_s)} s for {what}", file=sys.stderr)  # O(1)
            waited = True  # O(1)
        time.sleep(poll_s)  # O(1)


def snapshot_text() -> str:  # O(registry + p)
    lim, _ = limit()  # O(1)
    c = count()  # O(registry + p)
    return f"machine: {_parts(c)} of " + (f"limit {lim}" if lim else "no limit")  # O(1)
