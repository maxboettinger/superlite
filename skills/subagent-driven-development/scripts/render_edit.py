#!/usr/bin/env python3
"""Record a lead's throwaway render-check edits so the guard allows them until they are restored.

    render_edit.py start F [F ...] [--plan P] | restore [F ...] | status

`start` records each file in `.superlite/render-edits.json` (the guard then allows edits to it); it refuses a file
with uncommitted changes, one a plan task owns, one outside the run root and a protected `.superlite` file.
`restore` puts the files back to HEAD (a file that did not exist is deleted) and drops them from the record.
`status` lists the applied files, exit 1 when any. Errors: `render_edit: <reason>` on stderr, exit 2. Stdlib only.
"""
# Complexity notation:
#   k = files given, a = applied files, n = tasks in the plan
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import plan_tools as pt  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

USAGE = "usage: sl render_edit start F [F ...] [--plan P] | restore [F ...] | status"  # O(1)
FILE = "render-edits.json"  # O(1)


def _fail(msg):  # O(1)
    print(f"render_edit: {msg}", file=sys.stderr)  # O(1)
    return 2  # O(1)


def _read(sd):  # O(file) the record, {} when absent or unreadable
    try:  # O(1)
        data = json.loads((Path(sd) / FILE).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return data if isinstance(data, dict) and isinstance(data.get("files"), dict) else {}  # O(1)


def applied(sd) -> list:  # O(a log a) the root-relative files whose render edit is recorded and not yet restored
    return sorted(_read(sd).get("files", {}))  # O(a log a)


def _write(sd, data):  # O(file)
    (Path(sd) / FILE).write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")  # O(file)


def _git(root, *args):  # O(1) + spawn
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)  # O(1) + spawn


def _rel(root, raw):  # O(d) the root-relative posix path, None when it leaves the root
    p = Path(os.path.normpath(Path(root) / raw))  # O(d)
    try:  # O(1)
        return p.relative_to(root).as_posix()  # O(d)
    except ValueError:  # O(1)
        return None  # O(1)


def _owner(sd, plan, rel):  # O(n*k*s) the id of a task whose Owns names rel, else None
    if not plan:  # O(1)
        try:  # O(1)
            plan = json.loads((Path(sd) / "stable.json").read_text(encoding="utf-8")).get("plan")  # O(file)
        except (OSError, ValueError, AttributeError):  # O(1)
            plan = None  # O(1)
    if not plan:  # O(1)
        return None  # O(1)
    try:  # O(1)
        loaded = pt.Plan.load(str(plan))  # O(L)
    except pt.PlanError:  # O(1)
        return None  # O(1)
    for t in loaded.tasks:  # O(n) iterations
        if rel in [o.split(" (")[0].strip() for o in t.owns]:  # O(k*s*A)
            return t.id  # O(1)
    return None  # O(1)


def _start(root, sd, files, plan):  # O(k*(n + spawn))
    data = _read(sd) or {"files": {}}  # O(file)
    new = {}  # O(1)
    if not data["files"]:  # O(1)
        data.pop("started", None)  # O(1) a fresh run, not the stale one
    for raw in files:  # O(k) iterations
        rel = _rel(root, raw)  # O(d)
        if rel is None:  # O(1)
            return _fail(f"{raw} is outside the run root")  # O(1)
        if rel == ".superlite" or rel.startswith(".superlite/"):  # O(1)
            return _fail(f"{rel} is a protected file")  # O(1)
        if rel in data["files"]:  # O(1)
            continue  # O(1)
        who = _owner(sd, plan, rel)  # O(n*k*s)
        if who:  # O(1)
            return _fail(f"{rel} is owned by {who}; edit it through its task")  # O(1)
        if _git(root, "status", "--porcelain", "--", rel).stdout.strip():  # O(1) + spawn
            return _fail(f"{rel} has uncommitted changes; commit or revert them first")  # O(1)
        new[rel] = {"existed": (Path(root) / rel).exists()}  # O(1)
    if not new:  # O(1)
        return 0  # O(1)
    data["files"].update(new)  # O(k)
    data.setdefault("started", time.time())  # O(1)
    Path(sd).mkdir(parents=True, exist_ok=True)  # O(1)
    _write(sd, data)  # O(file)
    for rel in sorted(new):  # O(k log k)
        print(f"recorded {rel}")  # O(1)
    return 0  # O(1)


def _restore(root, sd, files):  # O(a*spawn)
    data = _read(sd)  # O(file)
    have = data.get("files", {})  # O(1)
    names = [rel for rel in (_rel(root, f) for f in files) if rel in have] if files else sorted(have)  # O(a)
    for rel in names:  # O(a) iterations
        path = Path(root) / rel  # O(1)
        if have[rel].get("existed"):  # O(1)
            r = _git(root, "checkout", "HEAD", "--", rel)  # O(1) + spawn
            if r.returncode:  # O(1)
                _write(sd, data)  # O(file) keep what was already restored
                return _fail(f"cannot restore {rel}: {r.stderr.strip()}")  # O(1)
        elif path.exists():  # O(1)
            path.unlink()  # O(1)
        del have[rel]  # O(1)
        print(f"restored {rel}")  # O(1)
    if names:  # O(1)
        _write(sd, data)  # O(file)
    return 0  # O(1)


def main(argv=None):  # O(k*(n + spawn))
    args = list(sys.argv[1:] if argv is None else argv)  # O(k)
    if not args or args[0] not in ("start", "restore", "status"):  # O(1)
        print(USAGE, file=sys.stderr)  # O(1)
        return 2  # O(1)
    cmd, rest, plan = args[0], args[1:], None  # O(1)
    if "--plan" in rest:  # O(k)
        i = rest.index("--plan")  # O(k)
        plan = rest[i + 1] if i + 1 < len(rest) else None  # O(1)
        rest = rest[:i] + rest[i + 2:]  # O(k)
    root = state.git_root(".")  # O(d)
    if root is None:  # O(1)
        return _fail("not inside a git repository")  # O(1)
    sd = root / ".superlite"  # O(1)
    if cmd == "start":  # O(1)
        if not rest:  # O(1)
            print(USAGE, file=sys.stderr)  # O(1)
            return 2  # O(1)
        return _start(root, sd, rest, plan)  # O(k*(n + spawn))
    if cmd == "restore":  # O(1)
        return _restore(root, sd, rest)  # O(a*spawn)
    files = applied(sd)  # O(a log a)
    for rel in files:  # O(a)
        print(rel)  # O(1)
    return 1 if files else 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
