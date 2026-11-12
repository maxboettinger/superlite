#!/usr/bin/env python3
"""Name the background test runs of a state folder after a Herdr restart (#577).

    fleet_rearm.test_run_lines(sd) -> ["test run ended|running|died: <summary> ..."]
"""
import json  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import run_tests  # noqa: E402  O(1)

SL = str(Path(__file__).resolve().parent / "sl")  # O(1) absolute path of the sl launcher
RECENT_S = 12 * 3600  # O(1) runs older than this are left out


def _mtime(p):  # O(1) file mtime or None
    try:  # O(1)
        return p.stat().st_mtime  # O(1)
    except OSError:  # O(1)
        return None  # O(1)


def _summaries(sd):  # O(p) distinct summary paths named by the test-summary*.latest pointers
    out = set()  # O(1)
    for ptr in Path(sd).glob("test-summary*.latest"):  # O(p)
        try:  # O(1)
            name = json.loads(ptr.read_text(encoding="utf-8")).get("summary")  # O(1)
        except (OSError, ValueError, AttributeError):  # O(1)
            continue  # O(1)
        if isinstance(name, str) and name:  # O(1)
            out.add(name)  # O(1)
    return sorted(out)  # O(p log p)


def test_run_lines(sd, now_s=None):  # O(p) one line per recent background run, sorted by summary path
    now = time.time() if now_s is None else now_s  # O(1)
    lines = []  # O(1)
    for name in _summaries(sd):  # O(p)
        p = Path(name)  # O(1)
        stamp = _mtime(p)  # O(1)
        if stamp is not None:  # summary written: ended | O(1)
            if now - stamp > RECENT_S:  # O(1)
                continue  # O(1)
            try:  # O(1)
                lines.append(f"test run ended: {name} {run_tests.summary_line(json.loads(p.read_text(encoding='utf-8')))}")  # O(1)
            except (OSError, ValueError, KeyError, AttributeError):  # O(1)
                continue  # O(1)
            continue  # O(1)
        stamp = _mtime(p.with_suffix(".pid"))  # O(1)
        if stamp is None or now - stamp > RECENT_S:  # O(1)
            continue  # O(1)
        if run_tests.pid_alive(p):  # O(1)
            lines.append(f"test run running: {name}; re-arm: {SL} run_tests --wait {name}")  # O(1)
        else:  # O(1)
            lines.append(f"test run died: {name} (no summary, pid gone)")  # O(1)
    return lines  # O(1)
