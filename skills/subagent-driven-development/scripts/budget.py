#!/usr/bin/env python3
"""One line of run-time control: elapsed, cost so far, projected finish and cost against target and cap.

    budget.py --plan P [--dir .superlite] [--changed] [--json]
    budget.py extend --plan P --ruling TEXT [--dir D]       the AI orchestrator's one +25% extension
    budget.py raise --to USD --ruling TEXT --plan P [--dir D]   the user's raise

Reads `.superlite/metrics.jsonl` (via metrics.py), the ledger's commits and the plan header
(`**Target-min:** 11`, optional `**Budget-usd:** 3.00`). Projection: elapsed + the longest remaining path
through unfinished tasks (predicted minutes from `schedule`, history-backed when stats exist, minus time
already spent on in-flight tasks); cost: spent + mean cost of finished tasks (else the history band mean)
per unfinished task. At 70% of the cap it warns; over the cap the run is paused (`gate` is the line dispatch and
fleet spawn refuse with); the cap is the newest `- Budget cap:` ledger line, else the header. When the projected time
overruns the target it names the late critical-path task. `--changed` prints only when the line differs
from the last printed one (`.superlite/budget.state`), for dispatch and lint. Exit 0; extend/raise refusals exit 2. Stdlib only.
"""
# Complexity notation:
#   n = tasks, e = edges, M = metrics lines
import argparse  # O(1)
import json  # O(1)
import math  # O(1)
import os  # O(1)
import re  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

WARN_AT = 0.70  # O(1)
COORDINATOR_TARGET_USD = 1.00  # the coordinator's own cost per committed task; the report shows it, the hint warns above it (#112) | O(1)
HINT_MIN_TASKS = 3  # fewer committed tasks say nothing yet about a per-task cost | O(1)
SUMMARIES_OFF = ("0", "false")  # the values Claude Code reads as `false` for CLAUDE_CODE_FORK_SUBAGENT | O(1)
SUMMARIES_NOTE = ("SUMMARIES ON: Claude Code asks every background agent's model for a 3-5 word status line every 30 s, "  # O(1)
                  "sending the agent's transcript, or a few hundred characters of notes when the server serves the short mode; "
                  "superlite never reads it and the requests appear in no transcript, so the budget cannot count them; "
                  "set env CLAUDE_CODE_FORK_SUBAGENT=0 in settings, see /superlite:setup")


def summaries_note(env=None) -> str | None:  # O(1)
    """The interactive Claude Code CLI (CLAUDE_CODE_ENTRYPOINT=cli) summarizes every background agent every 30 s with a
    `query_source=agent_summary` request that sends the agent's transcript, or notes in the server-served short mode (anthropics/claude-code#86879). Those
    requests are not written to any transcript, so metrics.py cannot count them. CLAUDE_CODE_FORK_SUBAGENT=0 closes the
    gate (superlite uses no fork agents); headless runs (`-p`, entrypoint sdk-cli) never arm the timer."""
    env = os.environ if env is None else env  # O(1)
    if env.get("CLAUDE_CODE_ENTRYPOINT") != "cli":  # O(1)
        return None  # O(1)
    if env.get("CLAUDE_CODE_FORK_SUBAGENT", "").strip().lower() in SUMMARIES_OFF:  # O(1)
        return None  # O(1)
    return SUMMARIES_NOTE  # O(1)


def header_budget(plan) -> float | None:  # O(C)
    m = re.search(r"^\*\*Budget-usd:\*\*\s*\$?\s*(\d+(?:\.\d+)?)", plan.text, re.M)  # O(C)
    return float(m.group(1)) if m else None  # O(1)


CAP_LINE = re.compile(r"^- Budget cap: (\d+(?:\.\d+)?) \((extend|raise)\) - ", re.M)  # O(1)
EXTEND_FACTOR = 1.25  # the AI orchestrator's one extension (+25%) | O(1)


def need_usd(spent: float, projected) -> float:  # O(1)
    """The least cap that lets the run finish: the larger of spend and projected cost, up to a cent."""
    return math.ceil(round(max(spent, projected or 0.0) * 100, 6)) / 100  # O(1)


def ledger_caps(sl_dir) -> list:  # O(ledger)
    """The (usd, kind) of every `- Budget cap:` line of the run ledger, oldest first."""
    f = Path(sl_dir) / "progress.md"  # O(1)
    if not f.is_file():  # O(1)
        return []  # O(1)
    return [(float(m.group(1)), m.group(2)) for m in CAP_LINE.finditer(f.read_text(encoding="utf-8", errors="replace"))]  # O(ledger)


def effective_cap(plan, sl_dir) -> float | None:  # O(ledger + C)
    """The newest ledger cap line, else the plan header cap, else None."""
    if not hasattr(plan, "text"):  # a path | O(1)
        import plan_tools as pt  # O(1)
        plan = pt.Plan.load(str(plan))  # O(L)
    caps = ledger_caps(sl_dir)  # O(ledger)
    return caps[-1][0] if caps else header_budget(plan)  # O(1)


def committed(sl: Path) -> set:  # O(ledger)
    f = sl / "progress.md"  # O(1)
    if not f.is_file():  # O(1)
        return set()  # O(1)
    return set(re.findall(r"^- commit ([A-Z]{1,3}\d+[A-Za-z]?)\b", f.read_text(encoding="utf-8", errors="replace"), re.M))  # O(ledger)


def compute(plan_path, sl_dir=".superlite", now=None) -> dict:  # O(M + B + n*(n + e))
    import history  # O(1)
    import metrics  # O(1)
    import plan_tools as pt  # O(1)
    sl = Path(sl_dir)  # O(1)
    plan = pt.Plan.load(str(plan_path))  # O(L)
    rows = metrics.task_records(sl, plan_path)  # O(M + B)
    agents = metrics.agent_records(sl)  # O(M + B)
    starts = [a["first_abs"] if a.get("first_abs") else a["start_ms"] / 1000.0 for a in agents if a.get("first_abs") or a["start_ms"]]  # O(A)
    now = now if now is not None else time.time()  # O(1)
    elapsed = max(0.0, now - min(starts)) if starts else 0.0  # O(1)
    co = metrics.coordinator_record(sl, agents=agents)  # O(B) the main session's own spend, the run alone (#112)
    agents_usd = metrics.agents_cost(sl)  # O(M + B) every agent segment, mapped to a task or not
    co_usd = co["cost_usd"] if co else 0.0  # O(1)
    spent = agents_usd + co_usd  # coordinator + agents | O(1)
    args = pt.build_parser().parse_args(["schedule", "--plan", str(plan_path)])  # O(1)
    rep = pt.schedule_report(plan, args)  # O(n*(n + e))
    graph, pred = rep["graph"], dict(rep["times"])  # O(n)
    stats = history.project_stats(sl)  # O(file)
    done = committed(sl) | {r["task"] for r in rows if r["status"] in ("DONE", "DONE_WITH_CONCERNS") and r["complete"]}  # O(n)
    inflight = {r["task"]: r for r in rows if r["task"] not in done and r["start_s"] is not None}  # O(n)
    flags = history.predicted_flags(plan)  # O(n*(n + e))
    for t, f in flags.items():  # history-backed minutes where a band has enough samples | O(n)
        task = plan.by_id.get(t)  # O(1)
        if not task:  # O(1)
            continue  # O(1)
        ft = task.explicit_features  # O(k*s)
        b = (stats.get("bands") or {}).get(history.band_of(ft.get("kind", "design"), ft.get("loc"), ft.get("tests")))  # O(1)
        if b and b.get("n", 0) >= 5 and b.get("mean_s"):  # O(1)
            pred[t] = b["mean_s"] / 60.0  # O(1)
    first0 = min((r["start_s"] for r in rows if r["start_s"] is not None), default=0.0)  # O(n)
    rem: dict[str, float] = {}  # remaining minutes of each unfinished task | O(1)
    for t in graph:  # O(n)
        if t in done:  # O(1)
            continue  # O(1)
        spent_min = ((elapsed - (inflight[t]["start_s"] - first0)) / 60.0) if t in inflight else 0.0  # O(1)
        rem[t] = max(0.1, pred.get(t, 0.0) - max(0.0, spent_min))  # O(1)
    best: dict[str, tuple] = {}  # longest remaining path ending at t: (minutes, path) | O(1)

    def path(t):  # O(deg) memoized
        if t not in best:  # O(1)
            ds = [path(d) for d in graph.get(t, []) if d in rem]  # O(deg)
            top = max(ds, default=(0.0, []))  # O(deg)
            best[t] = (top[0] + rem[t], top[1] + [t])  # O(len path)
        return best[t]  # O(1)

    crit = max((path(t) for t in rem), default=(0.0, []))  # O(n)
    projected = elapsed / 60.0 + crit[0]  # O(1)
    finished_cost = [r["cost_usd"] for r in rows if r["task"] in done and r["cost_usd"]]  # O(n)
    per_task = (sum(finished_cost) / len(finished_cost)) if finished_cost else (  # O(n)
        (stats.get("tiers") or {}).get("sonnet", {}).get("mean_cost"))
    left = [t for t in rem if t not in inflight]  # O(n)
    proj_cost = spent + (per_task or 0.0) * len(left) if per_task is not None or not left else None  # O(1)
    target, hcap = plan.header_target(), header_budget(plan)  # O(C)
    cap = effective_cap(plan, sl)  # O(ledger)
    need = need_usd(spent, proj_cost)  # O(1)
    out = {"coordinator_usd": round(co_usd, 3), "agents_usd": round(agents_usd, 3), "coordinator": co,  # O(1)
           "elapsed_min": round(elapsed / 60.0, 1), "cost_usd": round(spent, 3), "projected_min": round(projected, 1),
           "projected_usd": None if proj_cost is None else round(proj_cost, 3), "target_min": target, "cap_usd": cap,
           "header_cap_usd": hcap, "extended": any(k == "extend" for _, k in ledger_caps(sl)), "need_usd": need,
           "plan": str(plan_path), "dir": str(sl),
           "late_path": crit[1], "done": len(done), "remaining": len(rem), "stats": f"n={stats.get('rows', 0)}"}  # O(1)
    out["pct_cap"] = round(max(spent, proj_cost or 0.0) / cap, 3) if cap else None  # O(1)
    out["state"] = ("over" if cap and spent > cap else "warn" if cap and (proj_cost or spent) >= WARN_AT * cap else "ok")  # O(1)
    out["hint"] = None  # O(1)
    if co and co["turns"] >= 30 and co["context_median"] >= 60_000 and spent and co_usd / spent >= 0.4:  # O(1)
        out["hint"] = (f"HINT: the coordinator is {100 * co_usd / spent:.0f}% of the cost ({co['turns']} turns, median context "  # O(1)
                       f"{co['context_median'] // 1000}k): fewer, larger turns (batch dispatches, no polling) cut it")
    if co_usd and len(done) >= HINT_MIN_TASKS and co_usd / len(done) > COORDINATOR_TARGET_USD:  # O(1)
        per = (f"HINT: the coordinator costs ${co_usd / len(done):.2f} per committed task ({len(done)} tasks), above the "  # O(1)
               f"${COORDINATOR_TARGET_USD:.2f} target: batch dispatches, do not poll, keep reads out of the main context")
        out["hint"] = f"{out['hint']} {per}" if out["hint"] else per  # O(1)
    out["late"] = bool(target and projected > target + 1e-9)  # O(1)
    out["summaries"] = summaries_note()  # O(1)
    return out  # O(1)


def pause_text(b: dict, plan_path=None, sl_dir=None) -> str:  # O(file)
    """The gate line after `budget: paused: `."""
    import orchestrator  # O(1)
    plan_path = plan_path or b.get("plan") or "<plan>"  # O(1)
    st = orchestrator.read_state(sl_dir or b.get("dir") or ".superlite")  # O(file)
    ai = bool(st and st.get("mode") == "ai")  # O(1)
    head = f"spent ${b['cost_usd']:.2f} of ${b['cap_usd']:.2f} cap; least cap to finish ${b['need_usd']:.2f}; "  # O(1)
    if ai and not b.get("extended"):  # O(1)
        return head + f'once: sl budget extend --plan {plan_path} --ruling "<why>" (+25%)'  # O(1)
    return head + f'stop the run; the user raises it: sl budget raise --to {b["need_usd"]:.2f} --ruling "<their words>" --plan {plan_path}'  # O(1)


def gate(plan_path, sl_dir=".superlite") -> str | None:  # O(compute)
    """None while the run may spend; else the one `budget: paused: ...` line. Never raises."""
    try:  # fail open | O(1)
        b = compute(plan_path, sl_dir)  # O(compute)
        if b.get("state") != "over" or not b.get("cap_usd"):  # O(1)
            return None  # O(1)
        return "budget: paused: " + pause_text(b, plan_path, sl_dir)  # O(file)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def line(b: dict) -> str:  # O(1)
    cap_txt = " of $%g cap" % b["cap_usd"] if b["cap_usd"] else ""  # O(1)
    s = (f"budget: coordinator ${b['coordinator_usd']:.2f} | agents ${b['agents_usd']:.2f} | total ${b['cost_usd']:.2f}{cap_txt}, "  # O(1)
         f"elapsed {b['elapsed_min']} min, projected finish {b['projected_min']} min")
    if b["target_min"] is not None:  # O(1)
        s += f" (target {b['target_min']:g}, {b['projected_min'] - b['target_min']:+.1f})"  # O(1)
    if b["projected_usd"] is not None:  # O(1)
        s += f", projected cost ${b['projected_usd']:.2f}"  # O(1)
    if b["cap_usd"]:  # O(1)
        s += f" ({100 * (b['pct_cap'] or 0):.0f}% of cap)"  # O(1)
    s += f" [stats {b['stats']}]"  # O(1)
    if b.get("hint"):  # O(1)
        s += " " + b["hint"]  # O(1)
    if b["state"] == "warn":  # O(1)
        proj = b["projected_usd"] if b["projected_usd"] is not None else b["cost_usd"]  # O(1)
        s += f" WARN: 70% of the cap reached; projected ${proj:.2f} against the ${b['cap_usd']:.2f} cap"  # O(1)
    if b["state"] == "over":  # O(1)
        try:  # O(file)
            s += " OVER CAP: paused: " + pause_text(b)  # O(file)
        except Exception:  # noqa: BLE001 | O(1)
            s += " OVER CAP: paused"  # O(1)
    if b["late"] and b["late_path"]:  # O(1)
        s += f" LATE: critical path {' -> '.join(b['late_path'])}"  # O(1)
    if b.get("summaries"):  # O(1)
        s += " " + b["summaries"]  # O(1)
    return s  # O(1)


def maybe_print(plan_path, sl_dir=".superlite") -> None:  # O(compute)
    """For dispatch and lint: print the line only when it changed since the last time."""
    if not (Path(sl_dir) / "metrics.jsonl").is_file():  # nothing measured yet: nothing to say | O(1)
        return  # O(1)
    try:  # a missing metrics file or plan never breaks the caller | O(1)
        text = line(compute(plan_path, sl_dir))  # O(compute)
    except Exception:  # noqa: BLE001 | O(1)
        return  # O(1)
    st = Path(sl_dir) / "budget.state"  # O(1)
    key = re.sub(r"elapsed [\d.]+ min|projected finish [\d.]+ min|, [+-][\d.]+\)", "", text)  # clock drift alone is not a change | O(len)
    try:  # O(1)
        if st.is_file() and st.read_text(encoding="utf-8") == key:  # O(1)
            return  # O(1)
        st.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        st.write_text(key, encoding="utf-8")  # O(1)
    except OSError:  # O(1)
        pass  # O(1)
    print(text)  # O(1)


def append_cap(sl_dir, usd: float, kind: str, ruling: str) -> None:  # O(1)
    f = Path(sl_dir) / "progress.md"  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    num = f"{usd:.2f}".rstrip("0").rstrip(".")  # O(1)
    with f.open("a", encoding="utf-8") as fh:  # O(1)
        fh.write(f"- Budget cap: {num} ({kind}) - {' '.join(ruling.split())}\n")  # O(1)


def change_cap(a) -> int:  # O(compute)
    """`extend` and `raise`: refusals exit 2 with one stderr line."""
    import orchestrator  # O(1)
    import plan_tools as pt  # O(1)

    def refuse(msg):  # O(1)
        print(f"budget: {a.cmd}: {msg}", file=sys.stderr)  # O(1)
        return 2  # O(1)

    cap = effective_cap(pt.Plan.load(a.plan), a.dir)  # O(ledger + L)
    if cap is None:  # O(1)
        return refuse("no cap (set **Budget-usd:** in the plan header)")  # O(1)
    if not (a.ruling or "").strip():  # O(1)
        return refuse("--ruling TEXT is required")  # O(1)
    if a.cmd == "extend":  # O(1)
        st = orchestrator.read_state(a.dir)  # O(file)
        if not (st and st.get("mode") == "ai"):  # O(1)
            return refuse("only the AI orchestrator may extend; the user raises the cap with `sl budget raise`")  # O(1)
        if any(k == "extend" for _, k in ledger_caps(a.dir)):  # O(ledger)
            return refuse("already extended once; the user raises it: sl budget raise --to USD --ruling TEXT")  # O(1)
        new = round(cap * EXTEND_FACTOR, 2)  # O(1)
        append_cap(a.dir, new, "extend", a.ruling)  # O(1)
        print(f"budget: cap ${cap:.2f} -> ${new:.2f} (extended once, +25%)")  # O(1)
        return 0  # O(1)
    if a.to is None:  # O(1)
        return refuse("--to USD is required")  # O(1)
    spent = compute(a.plan, a.dir)["cost_usd"]  # O(compute)
    if a.to <= spent:  # O(1)
        return refuse(f"--to {a.to:g} is not above the ${spent:.2f} spent so far")  # O(1)
    append_cap(a.dir, a.to, "raise", a.ruling)  # O(1)
    print(f"budget: cap ${cap:.2f} -> ${a.to:.2f} (raised)")  # O(1)
    return 0  # O(1)


def main(argv=None):  # O(compute)
    argv = list(sys.argv[1:] if argv is None else argv)  # O(1)
    cmd = argv.pop(0) if argv and argv[0] in ("extend", "raise") else None  # O(1)
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])  # O(1)
    ap.add_argument("--plan", required=True)  # O(1)
    ap.add_argument("--dir", default=".superlite")  # O(1)
    ap.add_argument("--changed", action="store_true")  # O(1)
    ap.add_argument("--json", action="store_true")  # O(1)
    ap.add_argument("--ruling", default="")  # O(1)
    ap.add_argument("--to", type=float, default=None)  # O(1)
    a = ap.parse_args(argv)  # O(1)
    a.cmd = cmd  # O(1)
    sys.stdout.reconfigure(encoding="utf-8")  # O(1)
    if cmd:  # O(1)
        return change_cap(a)  # O(compute)
    if a.changed:  # O(1)
        maybe_print(a.plan, a.dir)  # O(compute)
        return 0  # O(1)
    b = compute(a.plan, a.dir)  # O(compute)
    print(json.dumps(b) if a.json else line(b))  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
