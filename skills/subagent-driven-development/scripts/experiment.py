#!/usr/bin/env python3
"""A one-shot run setting for a measurement (#53): the next big enough build runs with it, nobody passes flags.

    experiment.py set --id ID [--prime full|slim] [--batch N] [--min-tasks N] [--runs N]
    experiment.py show | clear

Config arms (#682): per backlog batch, one run config out of a list, state in `<root>/.superlite/experiments.json`.

    experiment.py set --id ID --arms A,B[,C] [--batches N] [--margin PTS] [--min-per-arm N] [--force] [--seed N] [--root R]
    experiment.py next --batch B [--root R]     the arm of batch B (the same one when asked again)
    experiment.py report ID [--json] [--rows FILE] [--margin PTS] [--min N] [--root R]

`$SUPERLITE_HOME/experiment.json` (default `~/.superlite/`) holds the experiment. A sonnet `build_prime` without
`--prime` calls `claim`: the first plan with at least min_tasks tasks whose run has not dispatched yet takes one run (runs_left - 1, under a lock) and
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
import random  # O(1)
import sys  # O(1)
from datetime import date  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from history import home  # $SUPERLITE_HOME | O(1)
from incident import _lock, _unlock  # the cross-platform file lock | O(1)

NAME = "experiment.json"  # O(1)
ARMS_NAME = "experiments.json"  # O(1)
SECTIONS = ("lead", "cache_ttl", "workers")  # O(1)


class ExperimentError(ValueError):  # O(1)
    pass  # O(1)


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
    """This plan's claim: kept when it has one, else one run of the global experiment when the run has not
    dispatched yet (no agents in sl_dir/pool.json), the plan has at least min_tasks tasks and runs are left. None
    otherwise (also for an unreadable plan)."""
    mine = for_plan(plan, sl_dir)  # O(f)
    if mine:  # O(1)
        return mine  # O(1)
    g = global_path()  # O(1)
    if not g.is_file():  # O(1)
        return None  # O(1)
    if ((load(Path(sl_dir) / "pool.json") or {}).get("agents")):  # the run already dispatched: a mid-run rebuild | O(pool)
        return None  # stays on the settings it started with | O(1)
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


def _arms_path(root) -> Path:  # O(1)
    return Path(root) / ".superlite" / ARMS_NAME  # O(1)


def _read_arms(root) -> dict:  # O(f)
    """The arms store; a missing file is empty, an unreadable one raises ExperimentError."""
    p = _arms_path(root)  # O(1)
    try:  # O(1)
        text = p.read_text(encoding="utf-8")  # O(f)
    except FileNotFoundError:  # O(1)
        return {"active": None, "experiments": {}}  # O(1)
    except OSError as e:  # O(1)
        raise ExperimentError(f"{p}: unreadable: {e}") from None  # O(1)
    try:  # O(1)
        data = json.loads(text)  # O(f)
    except ValueError:  # O(1)
        data = None  # O(1)
    if not isinstance(data, dict) or not isinstance(data.get("experiments"), dict):  # O(1)
        raise ExperimentError(f"{p}: not an experiments store; fix or remove the file")  # O(1)
    data.setdefault("active", None)  # O(1)
    return data  # O(1)


class _Locked:  # O(1)
    def __init__(self, root):  # O(1)
        p = _arms_path(root)  # O(1)
        p.parent.mkdir(parents=True, exist_ok=True)  # O(depth)
        self.f = open(p.with_name(ARMS_NAME + ".lock"), "a+", encoding="utf-8")  # O(1)

    def __enter__(self):  # O(1)
        _lock(self.f)  # O(1) + wait
        return self  # O(1)

    def __exit__(self, *exc):  # O(1)
        _unlock(self.f)  # O(1)
        self.f.close()  # O(1)


def _flat(cfg) -> dict:  # O(k)
    return {f"{s}.{k}": v for s in SECTIONS for k, v in (cfg.get(s) or {}).items()}  # O(k)


def config_diff(a: dict, b: dict) -> list:  # O(k log k)
    """Sorted dotted keys (`lead.model`) whose value differs between two resolved run configs."""
    fa, fb = _flat(a), _flat(b)  # O(k)
    return sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))  # O(k log k)


def set_arms(root, exp_id: str, arms: list, batches: int = 10, margin: float = 10.0, min_per_arm: int = 5,  # O(f + L)
             force: bool = False, seed: int | None = None) -> dict:
    """Start experiment exp_id over the named run configs. Refuses (ExperimentError) a corrupt store, a second active or
    reused id, fewer than two distinct arms, an unknown or identical config and more than one differing factor."""
    import run_config  # O(1)
    arms = list(arms)  # O(a)
    if len(arms) < 2 or len(set(arms)) != len(arms):  # O(a)
        raise ExperimentError("--arms needs at least two different run config names")  # O(1)
    if batches < 1:  # O(1)
        raise ExperimentError("--batches must be at least 1")  # O(1)
    with _Locked(root):  # O(1)
        store = _read_arms(root)  # O(f)
        if exp_id in store["experiments"]:  # O(1)
            raise ExperimentError(f"experiment id {exp_id} was used before; pick a new id")  # O(1)
        if store["active"]:  # O(1)
            raise ExperimentError(f"experiment {store['active']} is still active; let it end or remove it first")  # O(1)
        try:  # O(1)
            res = {a: run_config.resolve(a, root) for a in arms}  # O(a*L)
        except run_config.ConfigError as e:  # O(1)
            raise ExperimentError(str(e)) from None  # O(1)
        factor = set()  # O(1)
        for a in arms[1:]:  # O(a)
            d = config_diff(res[arms[0]], res[a])  # O(k)
            if not d:  # O(1)
                raise ExperimentError(f"{arms[0]} and {a} have the same config")  # O(1)
            factor.update(d)  # O(k)
        factor = sorted(factor)  # O(k log k)
        if len(factor) > 1 and not force:  # O(1)
            raise ExperimentError(f"the arms differ in {len(factor)} factors ({', '.join(factor)}); the result could not "
                                  "say which one mattered. Change one, or pass --force")
        if seed is None:  # O(1)
            seed = random.SystemRandom().randrange(2 ** 31)  # O(1)
        k = random.Random(seed).randrange(len(arms))  # O(1)
        rot = arms[k:] + arms[:k]  # O(a)
        exp = {"id": exp_id, "arms": arms, "configs": {a: res[a]["id"] for a in arms}, "factor": factor,  # O(a)
               "batches": batches, "order": [rot[i % len(rot)] for i in range(batches)], "assigned": {},
               "margin": float(margin), "min_per_arm": int(min_per_arm), "seed": seed,
               "set": date.today().isoformat(), "ended": None}
        store["experiments"][exp_id] = exp  # O(1)
        store["active"] = exp_id  # O(1)
        _write(_arms_path(root), store)  # O(f)
        return exp  # O(1)


def assign(root, batch: str) -> dict | None:  # O(f)
    """The arm of this batch in the active experiment (the next slot, kept for a batch asked twice); None without one.
    The last slot ends the experiment."""
    with _Locked(root):  # O(1)
        store = _read_arms(root)  # O(f)
        for eid, old in store["experiments"].items():  # O(e)
            if isinstance(old, dict) and batch in (old.get("assigned") or {}):  # O(1)
                arm = old["assigned"][batch]  # O(1)
                return {"experiment": eid, "arm": arm, "config": arm}  # O(1)
        exp = store["experiments"].get(store["active"] or "")  # O(1)
        if not exp:  # O(1)
            return None  # O(1)
        arm = exp["assigned"].get(batch)  # O(1)
        if arm is None:  # O(1)
            arm = exp["order"][len(exp["assigned"])]  # O(1)
            exp["assigned"][batch] = arm  # O(1)
            if len(exp["assigned"]) >= exp["batches"]:  # O(1)
                exp["ended"] = date.today().isoformat()  # O(1)
                store["active"] = None  # O(1)
            _write(_arms_path(root), store)  # O(f)
        return {"experiment": exp["id"], "arm": arm, "config": arm}  # O(1)


def assignment(root, batch: str) -> dict | None:  # O(f)
    """Read-only: the experiment and arm that batch was assigned to, else None (also for an unreadable store)."""
    try:  # O(1)
        store = _read_arms(root)  # O(f)
    except ExperimentError:  # O(1)
        return None  # O(1)
    for eid, exp in store["experiments"].items():  # O(e)
        if isinstance(exp, dict) and batch in (exp.get("assigned") or {}):  # O(1)
            return {"experiment": eid, "arm": exp["assigned"][batch]}  # O(1)
    return None  # O(1)


def load_arms(root, exp_id: str) -> dict | None:  # O(f)
    """The stored record of exp_id, else None."""
    exp = _read_arms(root)["experiments"].get(exp_id)  # O(f)
    return exp if isinstance(exp, dict) else None  # O(1)


def _rows_file(path) -> list:  # O(r)
    text = Path(path).read_text(encoding="utf-8", errors="replace")  # O(r)
    try:  # O(1)
        data = json.loads(text)  # O(r)
        if isinstance(data, list):  # O(1)
            return [r for r in data if isinstance(r, dict)]  # O(r)
    except ValueError:  # O(1)
        pass  # O(1)
    out = []  # O(1)
    for line in text.splitlines():  # O(r)
        try:  # O(1)
            r = json.loads(line)  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(r, dict):  # O(1)
            out.append(r)  # O(1)
    return out  # O(1)


def _report(a, root) -> int:  # O(f + r)
    import report  # O(1)
    if a.rows:  # O(1)
        try:  # O(1)
            allrows = _rows_file(a.rows)  # O(r)
        except OSError as e:  # O(1)
            raise ExperimentError(f"{a.rows}: unreadable: {e}") from None  # O(1)
    else:  # O(1)
        import batch_cost  # O(1)
        allrows = batch_cost.read_rows(root)  # O(r)
    rows = [r for r in allrows if r.get("experiment") == a.id]  # O(r)
    exp = load_arms(root, a.id)  # O(f)
    if exp is None:  # O(1)
        arms = next((r["arms"] for r in rows if isinstance(r.get("arms"), list)), None)  # O(r)
        if not a.rows or not arms:  # O(1)
            raise ExperimentError(f"unknown experiment {a.id}")  # O(1)
        exp = {"id": a.id, "arms": arms, "configs": {}, "margin": 10.0, "min_per_arm": 3}  # O(1)
    exp = dict(exp)  # O(1)
    if a.margin is not None:  # O(1)
        exp["margin"] = a.margin  # O(1)
    if a.min is not None:  # O(1)
        exp["min_per_arm"] = a.min  # O(1)
    rep = report.experiment_report(rows, exp)  # O(r)
    if a.json:  # O(1)
        print(json.dumps(rep, indent=2, sort_keys=True))  # O(r)
    else:  # O(1)
        print(report.experiment_text(rep).rstrip("\n"))  # O(r)
    return 0  # O(1)


def _arms_main(a) -> int:  # O(f + L)
    from backlog_state import main_root  # O(1)
    try:  # O(1)
        root = Path(a.root) if a.root else main_root(Path.cwd())  # O(1)
        if a.cmd == "set":  # O(1)
            if a.prime or a.batch is not None:  # O(1)
                raise ExperimentError("--arms cannot be combined with --prime or --batch")  # O(1)
            exp = set_arms(root, a.id, [x for x in a.arms.split(",") if x], a.batches, a.margin, a.min_per_arm,
                           a.force, a.seed)
            print(f"experiment {exp['id']}: arms {','.join(exp['arms'])}, factor {','.join(exp['factor'])}, "
                  f"{exp['batches']} batches, order {','.join(exp['order'])}")  # O(a)
        elif a.cmd == "next":  # O(1)
            r = assign(root, a.batch)  # O(f)
            if r is None:  # O(1)
                print("no active experiment")  # O(1)
            else:  # O(1)
                print(f"{a.batch} arm={r['arm']}: " + "sl backlog " + f"start {a.batch} --config {r['config']}")  # O(1)
                exp = load_arms(root, r["experiment"]) or {}  # O(f)
                if exp.get("ended") and list(exp["assigned"])[-1:] == [a.batch]:  # O(1)
                    print(f"experiment {exp['id']}: all {exp['batches']} batches assigned; ended")  # O(1)
        else:  # O(1)
            return _report(a, root)  # O(f + r)
    except (ExperimentError, RuntimeError) as e:  # O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    return 0  # O(1)


def main(argv=None) -> int:  # O(f)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("set")  # O(1)
    s.add_argument("--id", required=True)  # O(1)
    s.add_argument("--prime", choices=("full", "slim"))  # O(1)
    s.add_argument("--batch", type=int)  # O(1)
    s.add_argument("--min-tasks", type=int, default=0)  # O(1)
    s.add_argument("--runs", type=int, default=1)  # O(1)
    s.add_argument("--arms")  # O(1)
    s.add_argument("--batches", type=int, default=10)  # O(1)
    s.add_argument("--margin", type=float, default=10.0)  # O(1)
    s.add_argument("--min-per-arm", type=int, default=5)  # O(1)
    s.add_argument("--force", action="store_true")  # O(1)
    s.add_argument("--seed", type=int)  # O(1)
    s.add_argument("--root")  # O(1)
    n = sub.add_parser("next")  # O(1)
    n.add_argument("--batch", required=True)  # O(1)
    n.add_argument("--root")  # O(1)
    r = sub.add_parser("report")  # O(1)
    r.add_argument("id")  # O(1)
    r.add_argument("--json", action="store_true")  # O(1)
    r.add_argument("--rows")  # O(1)
    r.add_argument("--margin", type=float)  # O(1)
    r.add_argument("--min", type=int)  # O(1)
    r.add_argument("--root")  # O(1)
    sub.add_parser("show")  # O(1)
    sub.add_parser("clear")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    if a.cmd in ("next", "report") or (a.cmd == "set" and a.arms):  # O(1)
        return _arms_main(a)  # O(f + L)
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
