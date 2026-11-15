#!/usr/bin/env python3
"""Scoreboard: rolling cost and quality board over the shipped batch rows (free: reads batch-costs.jsonl only).

    scoreboard.py [--root R] [--window N] [--json]

Prints one line per metric (`name now base change`), then flags and outliers; exits 1 when a flag is set.
"""
# Complexity notation: r = rows
import argparse  # O(1)
import json  # O(1)
import statistics  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

MEDIANS = ("lead_usd", "total_usd", "lead_turns")  # O(1) rise above RISE flags
MEANS = ("points", "first_pass")  # O(1)
RISE = 0.30  # O(1)
POINTS_UP = 2.0  # O(1)
PASS_DOWN = 0.10  # O(1)
COST_X = 3  # O(1) a total above COST_X times the baseline median is an outlier
BAD_LETTERS = ("D", "E", "F")  # O(1)


def _num(v):  # O(1)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None  # O(1)


def metrics(row: dict) -> dict:  # O(1)
    lead = row["lead"]  # O(1) KeyError = malformed row
    grade = row.get("grade") if isinstance(row.get("grade"), dict) else {}  # O(1)
    lead_usd = float(lead["cost_usd"])  # O(1)
    workers = row.get("workers_total") if isinstance(row.get("workers_total"), dict) else {}  # O(1)
    tasks = _num(grade.get("tasks"))  # O(1)
    first = _num(grade.get("first_time_pass"))  # O(1)
    return {"lead_usd": lead_usd, "total_usd": lead_usd + (_num(workers.get("cost_usd")) or 0.0),
            "lead_turns": _num(lead.get("turns")), "points": _num(grade.get("points")),
            "first_pass": first / tasks if tasks and first is not None else None}  # O(1)


def shipped(rows: list) -> list:  # O(r)
    last = {}  # O(1)
    for i, r in enumerate(rows):  # O(r)
        if isinstance(r, dict) and r.get("row") == "batch" and r.get("batch") is not None:  # O(1)
            last.pop(r["batch"], None)  # O(1) a later row moves the batch to its own place
            last[r["batch"]] = r  # O(1)
    out = []  # O(1)
    for r in last.values():  # O(r)
        if r.get("end") != "shipped":  # O(1)
            continue  # O(1)
        try:  # O(1)
            out.append((r, metrics(r)))  # O(1)
        except (KeyError, TypeError, ValueError):  # O(1)
            continue  # O(1)
    return out  # O(r)


def _vals(items: list, name: str) -> list:  # O(r)
    return [m[name] for _, m in items if m.get(name) is not None]  # O(r)


def _fmt(name: str, v: float) -> str:  # O(1)
    return f"{v:.2f}" if name in ("lead_usd", "total_usd", "first_pass") else (f"{v:.0f}" if name == "lead_turns" else f"{v:.1f}")  # O(1)


def board(rows: list, window: int = 15) -> dict:  # O(r)
    items = shipped(rows)  # O(r)
    now, base = (items[-window:], items[:-window]) if window > 0 else ([], items)  # O(r)
    out = {"enough": len(now) >= window > 0 and len(base) >= window, "window": window, "now": len(now), "baseline": len(base),
           "metrics": {}, "flags": [], "outliers": []}  # O(1)
    for r, m in now:  # O(w)
        if str(r.get("grade", {}).get("letter") if isinstance(r.get("grade"), dict) else "") in BAD_LETTERS:  # O(1)
            out["outliers"].append(f"{r['batch']} grade {r['grade']['letter']}")  # O(1)
    tot = _vals(base, "total_usd")  # O(r)
    med = statistics.median(tot) if tot else 0  # O(r log r)
    for r, m in now:  # O(w)
        if med > 0 and m["total_usd"] > COST_X * med:  # O(1)
            out["outliers"].append(f"{r['batch']} cost {m['total_usd']:.2f} ({COST_X}x median {med:.2f})")  # O(1)
    if not out["enough"]:  # O(1)
        return out  # O(1)
    for name in MEDIANS + MEANS:  # O(1)
        a, b = _vals(base, name), _vals(now, name)  # O(r)
        if not a or not b:  # O(1)
            continue  # O(1)
        f = statistics.median if name in MEDIANS else statistics.fmean  # O(1)
        x, y = f(a), f(b)  # O(r)
        out["metrics"][name] = {"base": x, "now": y}  # O(1)
        if name in MEDIANS:  # O(1)
            if x > 0 and round((y - x) / x, 6) > RISE:  # O(1)
                out["flags"].append(f"{name} +{round((y - x) / x * 100):d}% ({_fmt(name, x)} -> {_fmt(name, y)})")  # O(1)
        elif name == "points" and round(y - x, 6) >= POINTS_UP:  # O(1)
            out["flags"].append(f"points +{y - x:.1f} ({_fmt(name, x)} -> {_fmt(name, y)})")  # O(1)
        elif name == "first_pass" and round(x - y, 6) >= PASS_DOWN:  # O(1)
            out["flags"].append(f"first_pass {y - x:+.2f} ({_fmt(name, x)} -> {_fmt(name, y)})")  # O(1)
    return out  # O(1)


def main(argv=None) -> int:  # O(r)
    ap = argparse.ArgumentParser(prog="scoreboard.py")  # O(1)
    ap.add_argument("--root")  # O(1)
    ap.add_argument("--window", type=int, default=15)  # O(1)
    ap.add_argument("--json", action="store_true")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    import batch_cost  # O(1)
    if a.root:  # O(1)
        root = Path(a.root)  # O(1)
    else:  # O(1)
        import backlog_state  # O(1)
        try:  # O(1)
            root = backlog_state.main_root(Path.cwd())  # O(1)
        except RuntimeError as e:  # O(1)
            print(f"scoreboard: {e}", file=sys.stderr)  # O(1)
            return 2  # O(1)
    rows = batch_cost.read_rows(root)  # O(r)
    b = board(rows, a.window)  # O(r)
    if a.json:  # O(1)
        print(json.dumps(b))  # O(1)
        return 1 if b["flags"] else 0  # O(1)
    if not shipped(rows):  # O(r)
        print("scoreboard: no batch rows")  # O(1)
        return 0  # O(1)
    print(f"scoreboard: {b['now']} now, {b['baseline']} baseline, window {b['window']}" + ("" if b["enough"] else " (not enough rows)"))  # O(1)
    for name, v in b["metrics"].items():  # O(1)
        ch = (v["now"] - v["base"]) / v["base"] * 100 if v["base"] and name in MEDIANS else v["now"] - v["base"]  # O(1)
        print(f"{name} {_fmt(name, v['now'])} {_fmt(name, v['base'])} " + (f"{ch:+.0f}%" if name in MEDIANS else f"{ch:+.2f}"))  # O(1)
    for f in b["flags"]:  # O(1)
        print(f"FLAG {f}")  # O(1)
    for o in b["outliers"]:  # O(w)
        print(f"OUTLIER {o}")  # O(w)
    return 1 if b["flags"] else 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
