#!/usr/bin/env python3
"""Machine memory admission (#560, #643): a new agent starts while measured memory leaves room for one more.

`measure` reads one `ps` call (process trees of the agent CLIs in AGENTS, with every descendant; their mean
resident size) and one OS memory read (macOS `sysctl`, Linux `/proc`). `room` admits one more agent when free memory
minus one mean agent stays at or above the floor (`SUPERLITE_MACHINE_FLOOR`, else `<home>/machine.json` `floor`,
else 15 percent; 0 = off) and the memory pressure is normal. An optional count cap (`SUPERLITE_MACHINE_LIMIT`, else
`machine.json` `limit`; 0 = none) bounds the agents too. No CPU or load-average check: builds are admitted outside
superlite. `gate` waits up to `wait_s` for room and returns None to go ahead, else the busy line.
"""
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from history import home  # $SUPERLITE_HOME | O(1)

AGENTS = ("claude", "codex", "gemini", "opencode", "droid", "cursor-agent", "qwen", "kimi", "copilot", "pi")  # O(1)
DEFAULT_EACH = 1 << 30  # assumed size of one agent when none runs | O(1)


def _ps() -> list:  # O(p)
    try:  # O(1)
        r = subprocess.run(["ps", "-axo", "pid=,ppid=,rss=,comm="], capture_output=True, text=True, errors="replace", timeout=10)  # O(p)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return []  # O(1)
    out = []  # O(1)
    for line in r.stdout.splitlines():  # O(p)
        parts = line.split(None, 3)  # O(1)
        if len(parts) < 4:  # O(1)
            continue  # O(1)
        try:  # O(1)
            out.append((int(parts[0]), int(parts[1]), int(parts[2]) * 1024, parts[3].strip()))  # O(1)
        except ValueError:  # O(1)
            continue  # O(1)
    return _named(out, _args(out))  # O(p)


RUNTIMES = ("node", "bun", "deno")  # script runtimes whose comm hides the agent CLI | O(1)


def _args(procs: list) -> dict:  # one extra ps call, only for runtime processes | O(p)
    pids = [p[0] for p in procs if os.path.basename(p[3]) in RUNTIMES]  # O(p)
    if not pids:  # O(1)
        return {}  # O(1)
    try:  # O(1)
        r = subprocess.run(["ps", "-o", "pid=,args=", "-p", ",".join(map(str, pids))], capture_output=True, text=True, errors="replace", timeout=10)  # O(p)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return {}  # O(1)
    out = {}  # O(1)
    for line in r.stdout.splitlines():  # O(p)
        parts = line.split(None, 1)  # O(1)
        if len(parts) == 2 and parts[0].isdigit():  # O(1)
            out[int(parts[0])] = parts[1].strip()  # O(1)
    return out  # O(p)


def _named(procs: list, args_by_pid: dict) -> list:  # O(p)
    out = []  # O(1)
    for pid, ppid, rss, comm in procs:  # O(p)
        words = args_by_pid.get(pid, "").split()  # O(1)
        if os.path.basename(comm) in RUNTIMES and words:  # O(1)
            for w in words[:2]:  # process.title sets argv[0]; else argv[1] is the script | O(1)
                name = os.path.basename(w)  # O(1)
                for ext in (".js", ".mjs", ".cjs", ".ts"):  # O(1)
                    if name.endswith(ext):  # O(1)
                        name = name[:-len(ext)]  # O(1)
                        break  # O(1)
                if name in AGENTS:  # O(1)
                    comm = name  # O(1)
                    break  # O(1)
        out.append((pid, ppid, rss, comm))  # O(1)
    return out  # O(p)


def agent_trees(procs: list) -> list:  # O(p * depth)
    info = {p[0]: p for p in procs}  # O(p)
    isagent = lambda pid: os.path.basename(info[pid][3]) in AGENTS  # O(1)
    sums = {}  # O(1)
    for pid, _, rss, _ in procs:  # O(p)
        seen, cur, top = set(), pid, None  # O(1)
        while cur in info and cur not in seen:  # walk to the outermost agent above | O(depth)
            seen.add(cur)  # O(1)
            if isagent(cur):  # O(1)
                top = cur  # O(1)
            cur = info[cur][1]  # O(1)
        if top is not None:  # O(1)
            sums[top] = sums.get(top, 0) + rss  # O(1)
    return [sums[k] for k in sorted(sums)]  # O(roots)


def _darwin(text: str):  # O(1)
    try:  # O(1)
        total, level, pr = (int(x) for x in text.split())  # O(1)
    except ValueError:  # O(1)
        return None  # O(1)
    return {"total": total, "free": total * level // 100, "pressure": {2: "warn", 4: "critical"}.get(pr, "normal")}  # O(1)


def _linux(meminfo: str, psi: str):  # O(lines)
    kb = {}  # O(1)
    for line in meminfo.splitlines():  # O(lines)
        k, _, v = line.partition(":")  # O(1)
        w = v.split()  # O(1)
        if w and w[0].isdigit():  # O(1)
            kb[k] = int(w[0]) * 1024  # O(1)
    if "MemTotal" not in kb or "MemAvailable" not in kb:  # O(1)
        return None  # O(1)
    avg = {}  # O(1)
    for line in psi.splitlines():  # O(lines)
        w = line.split()  # O(1)
        for tok in w[1:]:  # O(1)
            if tok.startswith("avg10=") and w:  # O(1)
                try:  # O(1)
                    avg[w[0]] = float(tok[6:])  # O(1)
                except ValueError:  # O(1)
                    pass  # O(1)
    pressure = "critical" if avg.get("full", 0) >= 10 else "warn" if avg.get("some", 0) >= 10 else "normal"  # O(1)
    return {"total": kb["MemTotal"], "free": kb["MemAvailable"], "pressure": pressure}  # O(1)


def memory():  # O(1)
    try:  # O(1)
        if sys.platform == "darwin":  # O(1)
            r = subprocess.run(["sysctl", "-n", "hw.memsize", "kern.memorystatus_level", "kern.memorystatus_vm_pressure_level"],
                               capture_output=True, text=True, errors="replace", timeout=10)  # O(1)
            return _darwin(r.stdout)  # O(1)
        if sys.platform.startswith("linux"):  # O(1)
            try:  # O(1)
                psi = Path("/proc/pressure/memory").read_text()  # O(1)
            except OSError:  # O(1)
                psi = ""  # O(1)
            return _linux(Path("/proc/meminfo").read_text(), psi)  # O(1)
    except (OSError, subprocess.SubprocessError, ValueError):  # O(1)
        return None  # O(1)
    return None  # O(1)


def measure(procs=None, mem=None) -> dict:  # O(p)
    trees = agent_trees(_ps() if procs is None else procs)  # O(p)
    mem = memory() if mem is None else mem  # O(1)
    mem = mem or {"total": None, "free": None, "pressure": None}  # O(1)
    each = sum(trees) // len(trees) if trees else DEFAULT_EACH  # O(roots)
    return {"agents": len(trees), "each": each, "total": mem["total"], "free": mem["free"], "pressure": mem["pressure"]}  # O(1)


def limit() -> tuple:  # O(1)
    env = os.environ.get("SUPERLITE_MACHINE_LIMIT")  # O(1)
    if env is not None and env.strip().isdigit():  # O(1)
        return int(env), "SUPERLITE_MACHINE_LIMIT"  # O(1)
    f = home() / "machine.json"  # O(1)
    try:  # O(1)
        return max(0, int(json.loads(f.read_text())["limit"])), str(f)  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return 0, "default"  # O(1)


def floor() -> tuple:  # O(1)
    env = os.environ.get("SUPERLITE_MACHINE_FLOOR")  # O(1)
    try:  # O(1)
        if env is not None and 0 <= float(env) <= 100:  # O(1)
            return float(env), "SUPERLITE_MACHINE_FLOOR"  # O(1)
    except ValueError:  # O(1)
        pass  # O(1)
    f = home() / "machine.json"  # O(1)
    try:  # O(1)
        v = float(json.loads(f.read_text())["floor"])  # O(1)
        if 0 <= v <= 100:  # O(1)
            return v, str(f)  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        pass  # O(1)
    return 15.0, "default"  # O(1)


def enabled() -> bool:  # O(1)
    return floor()[0] > 0 or limit()[0] > 0  # O(1)


def describe(m: dict, floor_pct: float) -> str:  # O(1)
    n = m["agents"]  # O(1)
    gb = f"{m['each'] / 2**30:.1f}"  # O(1)
    fleet = f"no agents, {gb} GB assumed" if n == 0 else f"{n} agent{'' if n == 1 else 's'}, about {gb} GB each"  # O(1)
    if m["total"] is None or m["free"] is None:  # O(1)
        return f"memory unknown ({fleet})"  # O(1)
    pr = f"pressure {m['pressure']}, " if m["pressure"] not in (None, "normal") else ""  # O(1)
    return f"memory {pr}{m['free'] * 100 // m['total']}% free, floor {floor_pct:g}% ({fleet})"  # O(1)


def room(m: dict, floor_pct: float, lim: int) -> bool:  # O(1)
    if lim and m["agents"] >= lim:  # O(1)
        return False  # O(1)
    if floor_pct <= 0 or m["total"] is None or m["free"] is None:  # O(1)
        return True  # O(1)
    if m["pressure"] in ("warn", "critical"):  # O(1)
        return False  # O(1)
    return (m["free"] - m["each"]) * 100 >= floor_pct * m["total"]  # O(1)


def _line(m: dict, flo: float, lim: int, src: str) -> str:  # O(1)
    s = describe(m, flo)  # O(1)
    return s + (f"; {m['agents']} agents of limit {lim} from {src}" if lim else "")  # O(1)


def gate(what: str, wait_s: float, over: bool = False, poll_s: float = 10.0):  # O(wait_s / poll_s * p)
    if not enabled():  # O(1)
        return None  # O(1)
    flo, _ = floor()  # O(1)
    lim, src = limit()  # O(1)
    t0 = time.monotonic()  # O(1)
    waited = False  # O(1)
    while True:  # O(wait_s / poll_s)
        m = measure()  # O(p)
        el = int(time.monotonic() - t0)  # O(1)
        if room(m, flo, lim):  # O(1)
            if waited:  # O(1)
                print(f"machine has room after {el} s: {_line(m, flo, lim, src)}; starting {what}", file=sys.stderr)  # O(1)
            return None  # O(1)
        if over:  # O(1)
            print(f"machine limit overridden (--over-limit): {_line(m, flo, lim, src)}", file=sys.stderr)  # O(1)
            return None  # O(1)
        if time.monotonic() - t0 >= wait_s:  # O(1)
            return f"machine busy after {el} s: {_line(m, flo, lim, src)}"  # O(1)
        if not waited:  # O(1)
            print(f"machine busy: {_line(m, flo, lim, src)}; waiting up to {int(wait_s)} s for {what}", file=sys.stderr)  # O(1)
            waited = True  # O(1)
        time.sleep(poll_s)  # O(1)


def snapshot_text() -> str:  # O(p)
    flo, _ = floor()  # O(1)
    lim, src = limit()  # O(1)
    m = measure()  # O(p)
    return f"machine: {_line(m, flo, lim, src)}" + ("" if lim else "; no count cap")  # O(1)
