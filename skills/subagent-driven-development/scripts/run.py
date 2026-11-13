#!/usr/bin/env python3
"""`sl run`: questions about the run itself, for third-party hooks (#671).

    run.py active [--plan P] [--session SID] [--json]

active: is a run active in P's state folder (a plan, a project folder or a `.superlite` folder; default: resolved as the
hooks do)? --session SID resolves the folder through that session's binding (a hook passes its input's `session_id`).
Prints text lines, or with --json one document (active, kind, state_dir, markers, batch, worktrees, checkpoint_files,
edited_after_checkpoint). Exit 0 while a run is active, 1 when none, 2 on usage errors. Stdlib only.
"""
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)


def cmd_active(a) -> int:  # O(a + w + b + files)
    import state  # O(1)
    import status  # O(1)
    if a.session is not None:  # O(1)
        if not state._SID.match(a.session):  # O(1)
            print(f"run: bad session id: {a.session}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        os.environ["SUPERLITE_SESSION_ID"] = a.session  # O(1)
    sd = state.resolve(a.plan, strict=False)  # O(d)
    report = status.active(sd)  # O(a + w + b + files)
    if a.json:  # O(1)
        print(json.dumps(report))  # O(report)
    else:  # O(1)
        for ln in status.active_lines(report):  # O(lines)
            print(ln)  # O(1)
    return 0 if report["active"] else 1  # O(1)


def main(argv: list | None = None) -> int:  # O(report)
    ap = argparse.ArgumentParser(prog="sl run")  # O(1)
    sub = ap.add_subparsers(dest="cmd", metavar="active")  # O(1)
    act = sub.add_parser("active", help="exit 0 while a run is active, 1 when none")  # O(1)
    act.add_argument("--plan", default=None)  # O(1)
    act.add_argument("--session", default=None)  # O(1)
    act.add_argument("--json", action="store_true")  # O(1)
    a = ap.parse_args(argv)  # O(len argv)
    if a.cmd != "active":  # O(1)
        ap.print_usage(sys.stderr)  # O(1)
        print("run: expected a subcommand: active", file=sys.stderr)  # O(1)
        return 2  # O(1)
    return cmd_active(a)  # O(report)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
