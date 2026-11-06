#!/usr/bin/env python3
"""Hold a task that waits for a human step, release it, or list the held tasks.

    hold.py Tn [Tm ...] --reason TEXT | --release Tn [Tm ...] | (no ids: list)  [--plan P] [--ledger L]

Appends `- Hold Tn: reason` / `- Release Tn` to the run ledger (`progress.md`); next_tasks.held_tasks reads them
and the dispatch skips held tasks. Ledger defaults to the run folder of `--plan`, else the session's run.
Errors: `hold: <reason>` on stderr, exit 2. Stdlib only.
"""
# Complexity notation:
#   R = lines in the ledger, k = ids given, n = tasks in the plan
import argparse  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import commit_task  # noqa: E402 | O(1)
import next_tasks  # noqa: E402 | O(1)
import plan_tools  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

TASK_ID = re.compile(r"^[A-Z]{1,3}\d+[A-Za-z]?$")  # O(1)


def _fail(msg):  # O(1)
    print(f"hold: {msg}", file=sys.stderr)  # O(1)
    return 2  # O(1)


def main(argv=None):  # O(R + k + n)
    ap = argparse.ArgumentParser(prog="hold.py", description=__doc__)  # O(1)
    ap.add_argument("ids", nargs="*")  # O(1)
    ap.add_argument("--reason")  # O(1)
    ap.add_argument("--release", nargs="+", metavar="Tn")  # O(1)
    ap.add_argument("--plan")  # O(1)
    ap.add_argument("--ledger")  # O(1)
    a = ap.parse_args(argv)  # O(k)
    if a.ledger:  # O(1)
        ledger = Path(a.ledger)  # O(1)
    else:  # O(1)
        ledger = (state.for_plan(a.plan) if a.plan else state.resolve()) / "progress.md"  # O(d)
    held = next_tasks.held_tasks(ledger)  # O(R)
    done = commit_task.committed_tasks(ledger)  # O(R)
    if not a.ids and not a.release:  # O(1)
        shown = [(t, r) for t, r in held.items() if t not in done]  # O(h)
        for t, r in shown:  # O(h)
            print(f"held {t}: {r}")  # O(1)
        if not shown:  # O(1)
            print("held: none")  # O(1)
        return 0  # O(1)
    if a.release and (a.ids or a.reason is not None):  # O(1)
        return _fail("--release takes its ids and no --reason")  # O(1)
    ids = a.release or a.ids  # O(1)
    for t in ids:  # O(k)
        if not TASK_ID.match(t):  # O(1)
            return _fail(f"bad task id {t!r}")  # O(1)
    lines = []  # O(1)
    if a.release:  # O(1)
        for t in ids:  # O(k)
            if t not in held:  # O(1)
                return _fail(f"{t} is not held")  # O(1)
            lines.append(f"- Release {t}")  # O(1)
        out = [f"released {t}" for t in ids]  # O(k)
    else:  # O(1)
        reason = " ".join((a.reason or "").split())  # O(len)
        if not reason:  # O(1)
            return _fail("--reason is required")  # O(1)
        if a.plan:  # O(1)
            known = plan_tools.Plan.load(a.plan).by_id  # O(file)
            for t in ids:  # O(k)
                if t not in known:  # O(1)
                    return _fail(f"{t} is not in the plan (tasks: {' '.join(known)})")  # O(n)
        for t in ids:  # O(k)
            if t in done:  # O(1)
                return _fail(f"{t} is already committed")  # O(1)
            lines.append(f"- Hold {t}: {reason}")  # O(1)
        out = [f"held {t}: {reason}" for t in ids]  # O(k)
    ledger.parent.mkdir(parents=True, exist_ok=True)  # O(d)
    prev = ledger.read_text(encoding="utf-8", errors="replace") if ledger.exists() else ""  # O(R)
    lead = "\n" if prev and not prev.endswith("\n") else ""  # O(1)
    with ledger.open("a", encoding="utf-8", newline="\n") as f:  # O(1)
        f.write(lead + "\n".join(lines) + "\n")  # O(k)
    print("\n".join(out))  # O(k)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(R + k + n)
