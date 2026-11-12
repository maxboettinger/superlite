#!/usr/bin/env python3
"""`sl status`: the run state in one screen.

    status.py [--plan P]

P is a plan file or a run folder (default: the current run folder). Lines, in order: run folder and owner;
orchestrator mode; plan and its task count; tasks (checkpointed, running, held, open); fleet workers;
budget; last test run; one `full run waiting: ...` line per waiting full run; and `after a crash: sl orchestrator resume ...` while a pool agent or fleet worker is
busy. Exit 0. Stdlib only.
"""
# Complexity notation:
# t = tasks in the plan, a = pool agents, w = fleet workers, L = ledger lines
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import time  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)


def owner_text(sd: Path) -> str:  # O(1)
    import state  # O(1)
    own = state.owner(sd)  # O(1)
    if own is None:  # O(1)
        return "none"  # O(1)
    return "this session" if own == state.session_id() else f"session {own}"  # O(1)


def clean_state(sd: Path) -> tuple:  # O(a + w)
    """(pool data, fleet data) with only well-formed entries: a corrupt or oddly shaped file never raises."""
    import fleet_state  # O(1)
    import pool  # O(1)
    try:  # O(1)
        pool_data = pool.load(sd / "pool.json")  # O(pool bytes)
    except SystemExit:  # corrupt pool.json: status still answers | O(1)
        pool_data = {}  # O(1)
    agents = pool_data.get("agents")  # O(1)
    pool_data = {"agents": [a for a in agents if isinstance(a, dict)] if isinstance(agents, list) else []}  # O(a)
    fleet = dict(fleet_state.load(sd))  # O(w)
    workers = fleet.get("workers")  # O(1)
    fleet["workers"] = {k: w for k, w in workers.items() if isinstance(w, dict)} if isinstance(workers, dict) else {}  # O(w)
    return pool_data, fleet  # O(1)


def running_map(sd: Path, pool_data: dict, fleet: dict) -> dict:  # O(a + w)
    """{task id: [agent ids]} for busy pool agents and busy fleet workers."""
    import pool  # O(1)
    run = {}  # O(1)
    for ag in pool_data.get("agents", []):  # O(a) iterations
        if ag.get("busy"):  # O(1)
            for t in pool.currents(ag):  # O(len current)
                run.setdefault(t, []).append(str(ag.get("id")))  # O(1)
    for wid, w in (fleet.get("workers") or {}).items():  # O(w) iterations
        if w.get("state") == "busy" and w.get("task"):  # O(1)
            for t in str(w["task"]).split(","):  # O(len)
                if t.strip():  # O(1)
                    run.setdefault(t.strip(), []).append(wid)  # O(1)
    return run  # O(1)


def tasks_line(sd: Path, ids: list, pool_data: dict, fleet: dict) -> str:  # O(t + L + a + w)
    import commit_task  # O(1)
    import next_tasks  # O(1)
    ledger = sd / "progress.md"  # O(1)
    done = commit_task.committed_tasks(ledger)  # O(L)
    held = next_tasks.held_tasks(ledger)  # O(L)
    run = running_map(sd, pool_data, fleet)  # O(a + w)
    groups = {"checkpointed": [], "running": [], "held": [], "open": []}  # O(1)
    for t in ids:  # O(t) iterations
        if t in done:  # O(1)
            groups["checkpointed"].append(t)  # O(1)
        elif t in run:  # O(1)
            seen = list(dict.fromkeys(run[t]))  # O(agents)
            groups["running"].append(f"{t} ({', '.join(seen)})")  # O(agents)
        elif t in held:  # O(1)
            groups["held"].append(f"{t} ({held[t]})")  # O(1)
        else:  # O(1)
            groups["open"].append(t)  # O(1)
    parts = [f"{k} {len(v)}: {', '.join(v)}" for k, v in groups.items() if v]  # O(t)
    return "tasks: " + ("; ".join(parts) if parts else "none")  # O(t)


def fleet_line(fleet: dict) -> str:  # O(w)
    if not fleet.get("on"):  # O(1)
        return "fleet: off"  # O(1)
    live, stopped = [], []  # O(1)
    for wid, w in (fleet.get("workers") or {}).items():  # O(w) iterations
        if w.get("state") == "stopped":  # O(1)
            stopped.append(wid)  # O(1)
            continue  # O(1)
        agent = str(w.get("agent") or "?").replace("superlite:", "", 1)  # O(1)
        task = f" {w['task']}" if w.get("task") else ""  # O(1)
        live.append(f"{wid} {agent} {w.get('state')}{task}")  # O(1)
    line = "fleet: on; " + (", ".join(live) if live else "no workers")  # O(w)
    return line + (f"; stopped: {', '.join(stopped)}" if stopped else "")  # O(w)


def budget_line(sd: Path, plan) -> str:  # O(budget)
    import budget  # O(1)
    if plan is None:  # O(1)
        return "budget: no plan"  # O(1)
    if not (sd / "metrics.jsonl").is_file():  # O(1)
        return "budget: no metrics yet"  # O(1)
    try:  # O(1)
        return budget.line(budget.compute(str(plan), str(sd)))  # O(budget)
    except Exception as e:  # O(1)
        return f"budget: unavailable ({type(e).__name__}: {e})"  # O(1)


def pid_alive(pid: int) -> bool:  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1) signal syscall
    except PermissionError:  # alive, not ours | O(1)
        return True  # O(1)
    except (OSError, ValueError, OverflowError):  # O(1)
        return False  # O(1)
    return True  # O(1)


def waiting_line(d: dict, now: float) -> str:  # O(1)
    mins = max(0, int((now - float(d.get("since") or 0)) // 60))  # O(1)
    if d.get("admission"):  # O(1)
        return f"full run waiting: {mins} min for the admission command {d['admission']}"  # O(1)
    stem = Path(str(d.get("lock") or "")).stem  # O(1)
    tool = stem[len("full-suite-"):] if stem.startswith("full-suite-") and len(stem) > 11 else "python"  # O(1)
    out = f"full run waiting: {mins} min for the {tool} full-suite lock"  # O(1)
    if d.get("place") and d.get("queued"):  # O(1)
        out += f", queue place {d['place']} of {d['queued']}"  # O(1)
    h = d.get("holder")  # O(1)
    if isinstance(h, dict) and h.get("pid"):  # O(1)
        out += f" (held by pid {h['pid']}" + (f" in {h['root']}" if h.get("root") else "") + ")"  # O(1)
    return out  # O(1)


def waiting_lines(sd: Path, now: float | None = None, alive=None) -> list:  # O(n) notes
    """One line per waiting full run: the `.lockwait` notes of sd whose waiting pid is alive."""
    now = time.time() if now is None else now  # O(1)
    alive = alive or pid_alive  # O(1)
    out = []  # O(1)
    for f in sorted(Path(sd).glob("test-summary*.lockwait")):  # O(n log n)
        try:  # O(1)
            d = json.loads(f.read_text(encoding="utf-8"))  # O(file)
            if not isinstance(d, dict) or not d.get("pid") or not alive(int(d["pid"])):  # O(1)
                continue  # O(1)
            out.append(waiting_line(d, now))  # O(1)
        except (OSError, ValueError, TypeError, AttributeError):  # O(1)
            continue  # O(1)
    return out  # O(n)


def overview(sd: Path, plan) -> list:  # O(t + L + a + w)
    import orchestrator  # O(1)
    import plan_tools  # O(1)
    sd = Path(sd)  # O(1)
    pool_data, fleet = clean_state(sd)  # O(a + w)
    out = [f"run: {sd}; owner: {owner_text(sd)}", orchestrator.summary_line(sd)]  # O(file)
    if plan is None:  # O(1)
        out.append("plan: none found (pass --plan <plan.md>)")  # O(1)
    else:  # O(1)
        try:  # O(1)
            tasks = plan_tools.Plan.load(str(plan)).tasks  # O(plan)
        except Exception as e:  # O(1)
            tasks = None  # O(1)
            out.append(f"plan: {plan} unreadable: {e}")  # O(1)
        if tasks is not None:  # O(1)
            out.append(f"plan: {plan}: {len(tasks)} tasks")  # O(1)
            out.append(tasks_line(sd, [t.id for t in tasks], pool_data, fleet))  # O(t + L + a + w)
    out += [fleet_line(fleet), budget_line(sd, plan), orchestrator.test_run_line(sd)]  # O(w + budget)
    out += waiting_lines(sd)  # O(n log n) notes
    busy = any(a.get("busy") for a in pool_data.get("agents", [])) or any(
        w.get("state") == "busy" for w in (fleet.get("workers") or {}).values())  # O(a + w)
    if busy:  # O(1)
        out.append(f"after a crash: sl orchestrator resume --plan {sd}")  # O(1)
    return out  # O(1)


def main(argv: list | None = None) -> int:  # O(overview)
    import orchestrator  # O(1)
    ap = argparse.ArgumentParser(prog="status.py")  # O(1)
    ap.add_argument("--plan", default=None)  # O(1)
    a = ap.parse_args(argv)  # O(len argv)
    sd = orchestrator.sl_dir(a.plan)  # O(d)
    for ln in overview(sd, orchestrator.plan_file(sd, a.plan)):  # O(lines)
        print(ln)  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
