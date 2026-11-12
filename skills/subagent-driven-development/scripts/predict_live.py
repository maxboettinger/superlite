#!/usr/bin/env python3
"""Live inputs of the plan forecast (#605): a project's test-run minutes and the machine's contention.

    project_tests(root, cfg)  minutes per fast and full run, where they came from, the build slots
    contention(root, cfg)     other live superlite runs, the full-suite lock, the factors

Test minutes, per mode: `run_min` in the test-cmd.json in effect (a positive number sets both modes, a dict sets `fast` and
`full`; a bad value is ignored; a user-level entry counts too), else the median `seconds=` of the newest `- tests fast|full`
ledger lines (runs that ran nothing do not count) in the repository's checkouts (`.superlite/progress.md` and
`.superlite/runs/*/progress.md`), when at least `history_min_runs` lines exist. `slots` is an int >= 1 or None.
Contention: other runs are session bindings with a live pid, a started run (`state.has_run`) outside `root` (this run's task
trees included) and a marker or ledger changed within `active_window_min`; two sessions of one run count once. The full-suite
lock counts when a live process outside `root` holds it. factor = max(1, (1 + others) / slots); full_factor = 1 +
full_wait_share x max(others, 1 when the lock is held). Stdlib only; predict.py wraps every call, so a failure here never
breaks a prediction.
"""
# Complexity notation:
#   c = checkouts, f = ledger files read, L = lines in them, s = session bindings
from __future__ import annotations  # O(1)

import os  # O(1)
import statistics  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import finish  # noqa: E402  # O(1) module load
import run_tests  # noqa: E402  # O(1) module load
import state  # noqa: E402  # O(1) module load
import testcmd  # noqa: E402  # O(1) module load
import worktree  # noqa: E402  # O(1) module load

MARKERS = ("progress.md", "stable.json", "pool.json", "prime.md", "fleet.json")  # files whose mtime shows a run is active | O(1)
SOURCES = {"test-cmd.json": "test-cmd.json", "user": "user test-cmd.json"}  # config_source label to the shown label | O(1)


def _num(v) -> bool:  # a positive int or float, not a bool | O(1)
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0  # O(1)


def config_minutes(config: dict | None) -> tuple[dict, int | None]:  # ({mode: minutes}, slots) from a test-cmd.json dict | O(1)
    mins: dict = {}  # O(1)
    slots = None  # O(1)
    if isinstance(config, dict):  # O(1)
        rm = config.get("run_min")  # O(1)
        if _num(rm):  # O(1)
            mins = {"fast": float(rm), "full": float(rm)}  # O(1)
        elif isinstance(rm, dict):  # O(1)
            mins = {m: float(rm[m]) for m in ("fast", "full") if _num(rm.get(m))}  # O(1)
        s = config.get("slots")  # O(1)
        if isinstance(s, int) and not isinstance(s, bool) and s >= 1:  # O(1)
            slots = s  # O(1)
    return mins, slots  # O(1)


def checkouts(root: Path) -> list[Path]:  # root first, then every worktree of the repository | O(c) + spawn
    root = Path(root)  # O(1)
    out = [root.resolve()]  # O(1)
    try:  # O(1)
        code, text, _ = worktree.git(root, "worktree", "list", "--porcelain")  # O(output)
    except Exception:  # O(1)
        return out  # O(1)
    if code != 0:  # O(1)
        return out  # O(1)
    for line in text.splitlines():  # O(c) iterations
        if line.startswith("worktree "):  # O(1)
            p = Path(line[len("worktree "):]).resolve()  # O(1)
            if p not in out:  # O(c)
                out.append(p)  # O(1)
    return out  # O(1)


def ledger_paths(root: Path, limit: int = 20) -> list[Path]:  # the newest ledgers of the checkouts | O(c log c)
    found: list[Path] = []  # O(1)
    for co in checkouts(root):  # O(c) iterations
        sd = co / ".superlite"  # O(1)
        for p in [sd / "progress.md", *sorted((sd / "runs").glob("*/progress.md"))]:  # O(runs) iterations
            if p.is_file() and p not in found:  # O(f)
                found.append(p)  # O(1)

    def mtime(p: Path) -> float:  # O(1)
        try:  # O(1)
            return p.stat().st_mtime  # O(1)
        except OSError:  # O(1)
            return 0.0  # O(1)

    found.sort(key=mtime, reverse=True)  # O(f log f)
    return found[:limit]  # O(limit)


def ledger_minutes(paths: list[Path], keep: int = 50) -> dict:  # {"fast": [min...], "full": [min...]}, newest first | O(L)
    out: dict = {"fast": [], "full": []}  # O(1)
    for p in paths:  # O(f) iterations
        try:  # O(1)
            lines = Path(p).read_text(encoding="utf-8", errors="replace").splitlines()  # O(file)
        except OSError:  # O(1)
            continue  # O(1)
        for line in reversed(lines):  # O(L) iterations
            m = finish.TESTS.match(line)  # O(w) regex
            if not m or m.group(1) not in out or len(out[m.group(1)]) >= keep:  # O(1)
                continue  # O(1)
            if int(m.group(2)) + int(m.group(3)) > 0:  # O(1)
                out[m.group(1)].append(float(m.group(5)) / 60.0)  # O(1)
    return out  # O(1)


def project_tests(root: Path, cfg: dict) -> dict:  # minutes per mode, their source, the slots | O(L) when a mode lacks a config value
    cfg = cfg or {}  # O(1)
    config, source, _ = testcmd.config_source(Path(root))  # O(m + f)
    mins, slots = config_minutes(config) if source in SOURCES else ({}, None)  # O(1)
    label = SOURCES.get(source)  # O(1)
    out: dict = {"slots": slots}  # O(1)
    lacking = [m for m in ("fast", "full") if m not in mins]  # O(1)
    hist = ledger_minutes(ledger_paths(Path(root), int(cfg.get("history_files", 20))), int(cfg.get("history_keep", 50))) if lacking else {}  # O(L)
    need = int(cfg.get("history_min_runs", 3))  # O(1)
    res: dict = {}  # O(1)
    for m in ("fast", "full"):  # O(1) iterations (2)
        if m in mins:  # O(1)
            res[m] = (mins[m], label, 0)  # O(1)
        elif len(hist.get(m, [])) >= max(need, 1):  # O(1)
            res[m] = (round(statistics.median(hist[m]), 3), "history", len(hist[m]))  # O(k log k)
        else:  # O(1)
            res[m] = (None, None, 0)  # O(1)
    return {"fast_min": res["fast"][0], "full_min": res["full"][0], "fast_source": res["fast"][1], "full_source": res["full"][1],  # O(1)
            "fast_runs": res["fast"][2], "full_runs": res["full"][2], "slots": out["slots"]}  # O(1)


def is_alive(pid) -> bool:  # O(1) syscall
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:  # O(1)
        return False  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1)
    except ProcessLookupError:  # O(1)
        return False  # O(1)
    except PermissionError:  # O(1)
        return True  # O(1)
    except (OSError, OverflowError):  # O(1)
        return False  # O(1)
    return True  # O(1)


def _inside(path: Path, root: Path) -> bool:  # path is root or below it | O(d)
    return path == root or root in path.parents  # O(d)


def _newest(sd: Path) -> float:  # newest mtime of the run's marker files, 0 when none | O(1)
    best = 0.0  # O(1)
    for name in MARKERS:  # O(1) iterations (5)
        try:  # O(1)
            best = max(best, (sd / name).stat().st_mtime)  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
    return best  # O(1)


def other_runs(root: Path, window_min: float, now: float | None = None) -> int:  # live runs outside root, changed within the window | O(s)
    sessions = state.home() / "sessions"  # O(1)
    now = time.time() if now is None else now  # O(1)
    root = Path(root).resolve()  # O(1)
    seen: set = set()  # O(1)
    try:  # O(1)
        entries = sorted(sessions.iterdir())  # O(s log s)
    except OSError:  # O(1)
        return 0  # O(1)
    for f in entries:  # O(s) iterations
        try:  # O(1)
            if f.is_dir():  # O(1)
                continue  # O(1)
            lines = f.read_text(encoding="utf-8").splitlines()  # O(file)
            sd = Path(lines[0].strip())  # O(1)
            pid = int(lines[1].strip())  # O(1)
            if not sd.is_absolute() or not sd.is_dir():  # O(1)
                continue  # O(1)
            sd = sd.resolve()  # O(1)
        except (OSError, ValueError, IndexError):  # O(1)
            continue  # O(1)
        if sd in seen or not is_alive(pid) or not state.has_run(sd) or _inside(sd, root):  # O(d)
            continue  # O(1)
        if now - _newest(sd) <= window_min * 60.0:  # O(1)
            seen.add(sd)  # O(1)
    return len(seen)  # O(1)


def full_lock_held(root: Path) -> bool:  # a live process outside root holds the full-suite lock | O(1)
    info = run_tests.lock_holder(run_tests.full_lock_path())  # O(file)
    if not info or not is_alive(info.get("pid")):  # O(1)
        return False  # O(1)
    where = info.get("root")  # O(1)
    if not isinstance(where, str) or not where:  # O(1)
        return True  # O(1)
    return not _inside(Path(where).resolve(), Path(root).resolve())  # O(d)


def contention(root: Path, cfg: dict, slots: int | None = None) -> dict:  # others, lock, factors | O(s)
    cfg = cfg or {}  # O(1)
    if not (isinstance(slots, int) and not isinstance(slots, bool) and slots >= 1):  # O(1)
        slots = max(1, int(cfg.get("slots", 2)))  # O(1)
    others = other_runs(Path(root), float(cfg.get("active_window_min", 120)))  # O(s)
    lock = full_lock_held(Path(root))  # O(1)
    share = float(cfg.get("full_wait_share", 0.5))  # O(1)
    return {"others": others, "full_lock": lock, "slots": slots,  # O(1)
            "factor": round(max(1, (1 + others) / slots), 3),  # O(1)
            "full_factor": round(1 + share * max(others, 1 if lock else 0), 3)}  # O(1)
