#!/usr/bin/env python3
"""Machine memory admission (#560, #643): a new agent starts while measured memory leaves room for one more.

`measure` reads one `ps` call (process trees of the agent CLIs in AGENTS, with every descendant; their mean
resident size) and one OS memory read (macOS `sysctl`, Linux `/proc`). `room` admits one more agent when free memory
minus one mean agent stays at or above the floor (`SUPERLITE_MACHINE_FLOOR`, else `<home>/machine.json` `floor`,
else 15 percent; 0 = off) and the memory pressure is not critical (`warn` alone refuses nothing, #916). An optional count cap (`SUPERLITE_MACHINE_LIMIT`, else
`machine.json` `limit`; 0 = none) bounds the agents too. No CPU or load-average check: builds are admitted outside
superlite. `gate` waits up to `wait_s` for room and returns None to go ahead, else the busy line, which names the largest
process outside the agent trees.
"""
import json  # O(1)
import os  # O(1)
import re  # O(1)
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


def _roots(procs: list) -> dict:  # pid -> the outermost agent above it (itself included), for each pid inside an agent tree | O(p * depth)
    info = {p[0]: p for p in procs}  # O(p)
    out = {}  # O(1)
    for pid, *_ in procs:  # O(p)
        seen, cur, top = set(), pid, None  # O(1)
        while cur in info and cur not in seen:  # walk to the outermost agent above | O(depth)
            seen.add(cur)  # O(1)
            if os.path.basename(info[cur][3]) in AGENTS:  # O(1)
                top = cur  # O(1)
            cur = info[cur][1]  # O(1)
        if top is not None:  # O(1)
            out[pid] = top  # O(1)
    return out  # O(p)


def _sums(procs: list, roots: dict) -> list:  # O(p)
    sums = {}  # O(1)
    for pid, _, rss, _ in procs:  # O(p)
        if pid in roots:  # O(1)
            sums[roots[pid]] = sums.get(roots[pid], 0) + rss  # O(1)
    return [sums[k] for k in sorted(sums)]  # O(roots)


def agent_trees(procs: list) -> list:  # O(p * depth)
    return _sums(procs, _roots(procs))  # O(p * depth)


def _other(procs: list, roots: dict):  # (name, rss) of the largest process outside every agent tree, or None (#916) | O(p)
    rest = [p for p in procs if p[0] not in roots]  # O(p)
    if not rest:  # O(1)
        return None  # O(1)
    top = max(rest, key=lambda p: p[2])  # O(p)
    return os.path.basename(top[3]) or top[3], top[2]  # O(1)


UNITS = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}  # vm.swapusage units | O(1)


def _swap_darwin(text: str):  # (total, used) bytes from the `vm.swapusage` line, or (None, None) | O(1)
    got = {k: re.search(k + r"\s*=\s*([0-9.]+)([KMGT])", text) for k in ("total", "used")}  # O(1)
    if not all(got.values()):  # O(1)
        return None, None  # O(1)
    return tuple(int(float(g.group(1)) * UNITS[g.group(2)]) for g in got.values())  # O(1)


def _compressed_darwin(vm: str):  # bytes the compressor occupies, from `vm_stat`, or None | O(lines)
    page = re.search(r"page size of (\d+) bytes", vm)  # O(1)
    occ = re.search(r"Pages occupied by compressor:\s*(\d+)", vm)  # O(1)
    return int(page.group(1)) * int(occ.group(1)) if page and occ else None  # O(1)


def _darwin(text: str, vm: str = ""):  # O(1)
    words = text.split()  # O(1)
    try:  # O(1)
        total, level, pr = (int(x) for x in words[:3])  # O(1)
    except ValueError:  # O(1)
        return None  # O(1)
    swap_total, swap_used = _swap_darwin(" ".join(words[3:]))  # O(1)
    return {"total": total, "free": total * level // 100, "pressure": {2: "warn", 4: "critical"}.get(pr, "normal"),
            "swap_total": swap_total, "swap_used": swap_used, "compressed": _compressed_darwin(vm)}  # O(1)


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
    swap = ("SwapTotal" in kb and "SwapFree" in kb)  # O(1)
    return {"total": kb["MemTotal"], "free": kb["MemAvailable"], "pressure": pressure,
            "swap_total": kb["SwapTotal"] if swap else None, "swap_used": kb["SwapTotal"] - kb["SwapFree"] if swap else None,
            "compressed": None}  # O(1)


def memory():  # O(1)
    try:  # O(1)
        if sys.platform == "darwin":  # O(1)
            r = subprocess.run(["sysctl", "-n", "hw.memsize", "kern.memorystatus_level", "kern.memorystatus_vm_pressure_level", "vm.swapusage"],
                               capture_output=True, text=True, errors="replace", timeout=10)  # O(1)
            try:  # O(1)
                vm = subprocess.run(["vm_stat"], capture_output=True, text=True, errors="replace", timeout=10).stdout  # O(1)
            except (OSError, subprocess.SubprocessError):  # O(1)
                vm = ""  # O(1)
            return _darwin(r.stdout, vm)  # O(1)
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
    procs = _ps() if procs is None else procs  # O(p)
    roots = _roots(procs)  # O(p * depth)
    trees = _sums(procs, roots)  # O(p)
    mem = memory() if mem is None else mem  # O(1)
    mem = mem or {"total": None, "free": None, "pressure": None}  # O(1)
    swap = {k: mem.get(k) for k in ("swap_total", "swap_used", "compressed")}  # O(1)
    each = sum(trees) // len(trees) if trees else DEFAULT_EACH  # O(roots)
    return {"agents": len(trees), "each": each, "total": mem["total"], "free": mem["free"], "pressure": mem["pressure"], **swap,
            "other": _other(procs, roots)}  # O(p)


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


def _fleet(m: dict) -> str:  # O(1)
    n = m["agents"]  # O(1)
    gb = f"{m['each'] / 2**30:.1f}"  # O(1)
    return f"no agents, {gb} GB assumed" if n == 0 else f"{n} agent{'' if n == 1 else 's'}, about {gb} GB each"  # O(1)


def _extra(m: dict) -> list:  # the swap and compressor parts that are known (#902) | O(1)
    out = []  # O(1)
    st, su = m.get("swap_total"), m.get("swap_used")  # O(1)
    if st is not None and su is not None:  # O(1)
        out.append(f"swap {su / 2**30:.1f} of {st / 2**30:.1f} GB used ({(st - su) / 2**30:.1f} GB free)" if st else "no swap in use")  # O(1)
    if m.get("compressed") is not None:  # O(1)
        out.append(f"compressor {m['compressed'] / 2**30:.1f} GB")  # O(1)
    return out  # O(1)


def figures(m: dict) -> str:  # the figures a refusal rests on, no percentage (#902) | O(1)
    return ", ".join([f"pressure {m.get('pressure') or 'unknown'}"] + _extra(m))  # O(1)


def describe(m: dict, floor_pct: float) -> str:  # O(1)
    fleet = _fleet(m)  # O(1)
    if m["total"] is None or m["free"] is None:  # O(1)
        return f"memory unknown ({fleet})"  # O(1)
    pr = f"pressure {m['pressure']}, " if m["pressure"] not in (None, "normal") else ""  # O(1)
    return "".join([f"memory {pr}{m['free'] * 100 // m['total']}% free, floor {floor_pct:g}%"] + [", " + x for x in _extra(m)] + [f" ({fleet})"])  # O(1)


def cause(m: dict, floor_pct: float, lim: int):  # why a new agent is refused: count, critical, floor, or None (#902) | O(1)
    if lim and m["agents"] >= lim:  # O(1)
        return "count"  # O(1)
    if floor_pct <= 0 or m["total"] is None or m["free"] is None:  # O(1)
        return None  # O(1)
    if m["pressure"] == "critical":  # `warn` alone refuses nothing: the floor below decides (#916) | O(1)
        return "critical"  # O(1)
    return None if (m["free"] - m["each"]) * 100 >= floor_pct * m["total"] else "floor"  # O(1)


def room(m: dict, floor_pct: float, lim: int) -> bool:  # O(1)
    return cause(m, floor_pct, lim) is None  # O(1)


def _line(m: dict, flo: float, lim: int, src: str) -> str:  # O(1)
    s = describe(m, flo)  # O(1)
    return s + (f"; {m['agents']} agents of limit {lim} from {src}" if lim else "")  # O(1)


def _bound_text(bounds) -> str:  # the given bounds as flags (#902) | O(1)
    b = bounds or {}  # O(1)
    parts = []  # O(1)
    if b.get("max_workers") is not None:  # O(1)
        parts.append(f"--max-workers {b['max_workers']}")  # O(1)
    if b.get("min_swap_free_mb") is not None:  # O(1)
        parts.append(f"--min-swap-free-mb {b['min_swap_free_mb']}")  # O(1)
    return " and ".join(parts)  # O(1)


def bounded_cause(m: dict, bounds: dict, run_workers):  # why `--over-limit` with bounds still refuses, or None (#902) | O(1)
    if m.get("pressure") == "critical":  # O(1)
        return "critical"  # O(1)
    mb, st, su = bounds.get("min_swap_free_mb"), m.get("swap_total"), m.get("swap_used")  # O(1)
    if mb is not None and st and su is not None and st - su < mb * 2**20:  # O(1)
        return "swap"  # O(1)
    mw = bounds.get("max_workers")  # O(1)
    if mw is not None and run_workers is not None and run_workers >= mw:  # O(1)
        return "workers"  # O(1)
    return None  # O(1)


WAIT_TTL = 3600  # a review waiter older than this is stale | O(1)


def _wait_dir() -> Path:  # O(1)
    return home() / "machine-wait"  # O(1)


def _alive(pid: int) -> bool:  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1)
    except ProcessLookupError:  # O(1)
        return False  # O(1)
    except (PermissionError, OSError):  # O(1)
        return True  # O(1)
    return True  # O(1)


def review_waiting(own_pid=None, now=None):  # what a live review spawn waits for, or None; dead waiters' files go (#902) | O(files)
    now = time.time() if now is None else now  # O(1)
    for f in sorted(_wait_dir().glob("*.json")):  # O(files)
        try:  # O(1)
            d = json.loads(f.read_text())  # O(1)
            pid, rank, what, t = int(d["pid"]), d["rank"], str(d["what"]), float(d["t"])  # O(1)
        except (OSError, ValueError, KeyError, TypeError):  # O(1)
            continue  # O(1)
        if not _alive(pid):  # O(1)
            f.unlink(missing_ok=True)  # O(1)
            continue  # O(1)
        if pid != own_pid and rank == 0 and now - t <= WAIT_TTL:  # O(1)
            return what  # O(1)
    return None  # O(1)


def _register(what: str) -> Path:  # O(1)
    f = _wait_dir() / f"{os.getpid()}.json"  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    f.write_text(json.dumps({"pid": os.getpid(), "rank": 0, "what": what, "t": time.time()}))  # O(1)
    return f  # O(1)


def refusal(m: dict, floor_pct: float, lim: int, src: str, why: str, bounds=None, run_workers=None, waiter=None) -> str:  # the figures that drive the refusal; the percentage only when the floor refused (#902) | O(1)
    head = f"memory {m['free'] * 100 // m['total']}% free, floor {floor_pct:g}%, " if why == "floor" else "memory "  # O(1)
    mb, mw = (bounds or {}).get("min_swap_free_mb"), (bounds or {}).get("max_workers")  # O(1)
    extra = {"count": f"; {m['agents']} agents of limit {lim} from {src}", "swap": f"; swap free under --min-swap-free-mb {mb}",
             "workers": f"; {run_workers} live workers in this run, --max-workers {mw}",
             "review": f"; a review spawn waits first: {waiter}"}.get(why, "")  # O(1)
    other = m.get("other")  # O(1)
    held = f"; largest non-agent process {other[0]} {other[1] / 2**30:.1f} GB" if other else ""  # O(1)
    return f"{head}{figures(m)} ({_fleet(m)}){extra}{held}"  # O(1)


PHRASES = {"count": "agent count at the limit", "critical": "pressure critical", "floor": "free memory under the floor",
           "review": "a review spawn waits first"}  # O(1)


def gave_up(causes: list, el: int, m: dict, bounds=None, run_workers=None, waiter=None) -> str:  # what the gate saw and what would change it (#902) | O(k)
    k = len(causes)  # O(1)
    seen = list(dict.fromkeys(causes))  # first-seen order | O(k)
    ph = {**PHRASES, "swap": f"swap free under {(bounds or {}).get('min_swap_free_mb')} MB",
          "workers": f"this run at --max-workers {(bounds or {}).get('max_workers')}"}  # O(1)
    if len(seen) == 1:  # O(1)
        what = ph[seen[0]] + (" at every check" if k > 1 else "")  # O(1)
    else:  # O(1)
        what = ", ".join(f"{ph[c]} at {causes.count(c)}" for c in seen)  # O(k)
    ways = []  # O(1)
    if seen == ["workers"]:  # O(1)
        ways.append(f"workers of this run end ({run_workers} live, --max-workers {(bounds or {}).get('max_workers')})")  # O(1)
    elif seen == ["review"]:  # O(1)
        ways.append(f"the waiting review spawn ({waiter}) starts or gives up")  # O(1)
    elif m["agents"] > 0:  # O(1)
        ways.append(f"agents end ({m['agents']} running)")  # O(1)
    if m.get("other") and seen not in (["workers"], ["review"]):  # O(1)
        ways.append(f"{m['other'][0]} ({m['other'][1] / 2**30:.1f} GB) ends")  # O(1)
    room_part = "room comes when " + (" or when ".join(ways) if ways else "memory frees up")  # O(1)
    return f"gave up after {k} check{'' if k == 1 else 's'} in {el} s: {what}; {room_part}"  # O(1)


def gate(what: str, wait_s: float, over: bool = False, poll_s: float = 10.0, rank: int = 1, bounds=None, run_workers=None):  # O(wait_s / poll_s * p)
    has_b = bool(bounds) and any(v is not None for v in bounds.values())  # O(1)
    if not enabled() and not has_b:  # O(1)
        return None  # O(1)
    try:  # O(1)
        return _gate(what, wait_s, over, poll_s, rank, bounds if has_b else None, run_workers, lambda: _register(what) if rank == 0 else None)  # O(wait_s / poll_s * p)
    finally:  # O(1)
        if rank == 0:  # O(1)
            (_wait_dir() / f"{os.getpid()}.json").unlink(missing_ok=True)  # O(1)


def _count(run_workers):  # the run's live workers now; a callable is read again, one that raises counts as None | O(w)
    if not callable(run_workers):  # O(1)
        return run_workers  # O(1)
    try:  # O(1)
        return run_workers()  # O(w)
    except Exception:  # O(1)
        return None  # O(1)


def _gate(what, wait_s, over, poll_s, rank, bounds, run_workers, register):  # O(wait_s / poll_s * p)
    flo, _ = floor()  # O(1)
    lim, src = limit()  # O(1)
    t0 = time.monotonic()  # O(1)
    waited = False  # O(1)
    causes = []  # O(1)
    while True:  # O(wait_s / poll_s)
        m = measure()  # O(p)
        rw = _count(run_workers)  # O(w)
        el = int(time.monotonic() - t0)  # O(1)
        plain = cause(m, flo, lim)  # O(1)
        waiter = None  # O(1)
        if over and bounds is None:  # plain override: as before, no queue | O(1)
            if plain:  # O(1)
                print(f"machine limit overridden (--over-limit): {_line(m, flo, lim, src)}", file=sys.stderr)  # O(1)
            return None  # O(1)
        why = bounded_cause(m, bounds, rw) if over else plain  # O(1)
        if why is None and rank == 1:  # O(1)
            waiter = review_waiting(os.getpid())  # O(files)
            why = "review" if waiter else None  # O(1)
        if why is None:  # O(1)
            if over and plain:  # O(1)
                print(f"machine limit overridden (--over-limit within {_bound_text(bounds)}): {_line(m, flo, lim, src)}", file=sys.stderr)  # O(1)
            elif waited:  # O(1)
                print(f"machine has room after {el} s: {_line(m, flo, lim, src)}; starting {what}", file=sys.stderr)  # O(1)
            return None  # O(1)
        causes.append(why)  # O(1)
        text = refusal(m, flo, lim, src, why, bounds, rw, waiter)  # O(1)
        if time.monotonic() - t0 >= wait_s:  # O(1)
            return f"machine busy after {el} s: {text}; {gave_up(causes, el, m, bounds, rw, waiter)}"  # O(1)
        if not waited:  # O(1)
            print(f"machine busy: {text}; waiting up to {int(wait_s)} s for {what}", file=sys.stderr)  # O(1)
            waited = True  # O(1)
            register()  # O(1)
        time.sleep(poll_s)  # O(1)


def snapshot_text() -> str:  # O(p)
    flo, _ = floor()  # O(1)
    lim, src = limit()  # O(1)
    m = measure()  # O(p)
    return f"machine: {_line(m, flo, lim, src)}" + ("" if lim else "; no count cap")  # O(1)
