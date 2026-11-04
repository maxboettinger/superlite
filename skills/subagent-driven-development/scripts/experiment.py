#!/usr/bin/env python3
"""A one-shot run setting for a measurement (#53): the next big enough build runs with it, nobody passes flags.

    experiment.py set --id ID [--prime full|slim] [--batch N] [--min-tasks N] [--runs N]
    experiment.py show | clear

`$SUPERLITE_HOME/experiment.json` (default `~/.superlite/`) holds the experiment. A sonnet `build_prime` without
`--prime` calls `claim`: the first plan with at least min_tasks tasks takes one run (runs_left - 1, under a lock) and
its claim `{id, plan, prime, batch}` goes to `experiment.json` beside its prime (`.superlite/`); rebuilding that plan's
prime keeps the claim. `dispatch` without `--batch` and `history write` read the claim of their plan (`for_plan`), so
the run's dispatches use its batch and its history rows carry its id. Explicit `--prime`/`--batch` always win.
Stdlib only.
"""
# Complexity notation:
#   L = lines of the plan, f = bytes of an experiment file
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import sys  # O(1)
from datetime import date  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from history import home  # $SUPERLITE_HOME | O(1)
from incident import _lock, _unlock  # the cross-platform file lock | O(1)

NAME = "experiment.json"  # O(1)


def global_path() -> Path:  # O(1)
    return home() / NAME  # O(1)


def load(path) -> dict | None:  # O(f)
    try:  # O(1)
        data = json.loads(Path(path).read_text(encoding="utf-8"))  # O(f)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    return data if isinstance(data, dict) else None  # O(1)


def _write(path, data) -> None:  # O(f)
    path = Path(path)  # O(1)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(depth)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")  # O(1)
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # O(f)
    os.replace(tmp, path)  # atomic | O(1)


def for_plan(plan, sl_dir) -> dict | None:  # O(f)
    """The claim in sl_dir when it was made for this plan, else None."""
    c = load(Path(sl_dir) / NAME)  # O(f)
    return c if c and c.get("plan") == str(Path(plan).resolve()) else None  # O(1)


def claim(plan, sl_dir) -> dict | None:  # O(L + f)
    """This plan's claim: kept when it has one, else one run of the global experiment when the plan has at least
    min_tasks tasks and runs are left. None otherwise (also for an unreadable plan)."""
    mine = for_plan(plan, sl_dir)  # O(f)
    if mine:  # O(1)
        return mine  # O(1)
    g = global_path()  # O(1)
    if not g.is_file():  # O(1)
        return None  # O(1)
    import plan_tools as pt  # O(1)
    try:  # O(1)
        n = len(pt.Plan.load(str(plan)).tasks)  # O(L)
    except Exception:  # noqa: BLE001 | an unreadable plan claims nothing; build_prime reports it | O(1)
        return None  # O(1)
    with open(g.with_name(NAME + ".lock"), "a+", encoding="utf-8") as f:  # O(1)
        _lock(f)  # two builds starting at once: one claim | O(1) + wait
        try:  # O(1)
            exp = load(g)  # O(f)
            if not exp or int(exp.get("runs_left") or 0) < 1 or n < int(exp.get("min_tasks") or 0):  # O(1)
                return None  # O(1)
            exp["runs_left"] = int(exp["runs_left"]) - 1  # O(1)
            _write(g, exp)  # first: a crash after it loses the run instead of granting a second | O(f)
            c = {"id": exp.get("id"), "plan": str(Path(plan).resolve()), "prime": exp.get("prime"), "batch": exp.get("batch")}  # O(1)
            _write(Path(sl_dir) / NAME, c)  # O(f)
            return c  # O(1)
        finally:  # O(1)
            _unlock(f)  # O(1)


def main(argv=None) -> int:  # O(f)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("set")  # O(1)
    s.add_argument("--id", required=True)  # O(1)
    s.add_argument("--prime", choices=("full", "slim"))  # O(1)
    s.add_argument("--batch", type=int)  # O(1)
    s.add_argument("--min-tasks", type=int, default=0)  # O(1)
    s.add_argument("--runs", type=int, default=1)  # O(1)
    sub.add_parser("show")  # O(1)
    sub.add_parser("clear")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    g = global_path()  # O(1)
    if a.cmd == "set":  # O(1)
        if a.batch is not None and a.batch < 1:  # O(1)
            ap.error("--batch must be at least 1")  # O(1)
        _write(g, {"id": a.id, "prime": a.prime, "batch": a.batch, "min_tasks": a.min_tasks, "runs_left": a.runs,  # O(f)
                   "set": date.today().isoformat()})
        print(g)  # O(1)
    elif a.cmd == "show":  # O(1)
        exp = load(g)  # O(f)
        if exp:  # O(1)
            print(json.dumps(exp, sort_keys=True))  # O(f)
    elif g.exists():  # clear | O(1)
        g.unlink()  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(f)
