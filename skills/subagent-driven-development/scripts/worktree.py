#!/usr/bin/env python3
"""Find or create the run's own git worktree, so a change never starts in a shared checkout.

    worktree.py ensure TOPIC [--repo DIR]     print the absolute path of the run folder
    worktree.py inplace --reason TEXT         opt the marked inline flow out of the main-checkout write refusal

From a linked worktree the tool returns that worktree. Otherwise it returns (or creates)
`<main root>/.claude/worktrees/superlite-<slug>` on branch `superlite/<slug>`. The main checkout's
branch and files are never changed. No repository, a bare one, or no commit yet: the start folder.
Exit 2 when a plain folder sits at the target path. A new worktree gets a stderr line naming the ignored
top-level entries of the main checkout it lacks (`.env`, `.venv/`; names only, nothing is copied).
`inplace` sets `inplace` to the reason in the marker `<state folder>/inline-flow.json` that hooks/mark-inline-flow wrote
(hooks/inline-worktree-guard then lets edits in the main checkout pass) and appends `Ruling: in place - TEXT` to the
state folder's progress.md; no marker: nothing changes, exit 0 (#148). Stdlib only.
"""
# Complexity notation: n = length of the topic, w = registered worktrees, e = lines of info/exclude, i = ignored entries,
# r = length of the reason, f = size of the marker file
import argparse  # O(1)
import json  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

PARENT = ".claude/worktrees"  # O(1)
INTERNAL = {".git", ".superlite", ".claude", "__pycache__", ".DS_Store"}  # (.DS_Store: OS noise a global gitignore lists) never listed as missing (#141) | O(1)
SHOWN = 10  # names in the "missing here" line | O(1)
MARKER = "inline-flow.json"  # in the state folder: written by hooks/mark-inline-flow, read by hooks/inline-worktree-guard | O(1)


class Taken(Exception):  # O(1)
    """A plain folder (not a worktree) sits at the target path."""


def git(root, *args):  # O(output) + process spawn
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(output)
    return r.returncode, r.stdout.strip(), r.stderr.strip()  # O(1)


def slug(topic):  # O(n)
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40].strip("-")  # O(n)
    return s or "change"  # O(1)


def is_linked(root):  # O(1) file read
    try:  # O(1)
        text = (Path(root) / ".git").read_text(encoding="utf-8", errors="replace")  # O(file)
    except OSError:  # O(1) no .git file (a directory raises too)
        return False  # O(1)
    for line in text.splitlines():  # O(lines)
        if line.startswith("gitdir:"):  # O(1)
            parts = line[7:].strip().replace("\\", "/").rstrip("/").split("/")  # O(len line)
            return len(parts) >= 2 and parts[-2] == "worktrees"  # O(1)
    return False  # O(1)


def no_repo_reason(start):  # O(1) + spawns
    """-> why `start` is not usable as a repository ('' when it is)."""
    if git(start, "rev-parse", "--show-toplevel")[0]:  # O(1) + spawn
        return "no git repository"  # O(1)
    if git(start, "rev-parse", "--verify", "-q", "HEAD")[0]:  # O(1) + spawn
        return "no commit yet"  # O(1)
    return ""  # O(1)


def add_exclude(root, rel, probe):  # O(e) + spawns
    if git(root, "check-ignore", "-q", probe)[0] == 0:  # O(1) + spawn
        return  # O(1) already ignored
    rc, out, _ = git(root, "rev-parse", "--git-common-dir")  # O(1) + spawn
    if rc or not out:  # O(1) no git dir to write to
        return  # O(1)
    common = Path(root) / out  # O(1) absolute out replaces root
    f = common / "info" / "exclude"  # O(1)
    line = rel.rstrip("/") + "/"  # O(1)
    old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""  # O(file)
    if line in old.splitlines():  # O(e)
        return  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    f.write_text(old + ("" if not old or old.endswith("\n") else "\n") + line + "\n", encoding="utf-8")  # O(file)


def missing_ignored(main, wt):  # O(i) + one process spawn
    """-> sorted names (`.env`, `.venv/`) of the ignored top-level entries of the main checkout that `wt` lacks."""
    rc, out, _ = git(main, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")  # O(i) + spawn
    if rc:  # O(1)
        return []  # O(1)
    names = set()  # O(1)
    for entry in out.split("\0"):  # O(i)
        bare = entry.rstrip("/")  # O(1)
        if bare and "/" not in bare and bare not in INTERNAL and not (Path(wt) / bare).exists():  # O(1) stat
            names.add(entry)  # O(1)
    return sorted(names)  # O(i log i)


def missing_line(names):  # O(1)
    """-> the stderr line for `missing_ignored` names, '' when there are none."""
    if not names:  # O(1)
        return ""  # O(1)
    more = f" (+{len(names) - SHOWN} more)" if len(names) > SHOWN else ""  # O(1)
    return "worktree: ignored in the main checkout, missing here: " + ", ".join(names[:SHOWN]) + more  # O(1)


def ensure(topic, start):  # O(w) + spawns
    """-> (run folder, state): created / exists / linked / no-repo."""
    start = Path(start).resolve()  # O(1)
    if no_repo_reason(start):  # O(1) + spawns
        return start, "no-repo"  # O(1)
    top = Path(git(start, "rev-parse", "--show-toplevel")[1])  # O(1) + spawn
    if git(top, "rev-parse", "--is-bare-repository")[1] == "true":  # O(1) + spawn
        return start, "no-repo"  # O(1)
    if is_linked(top):  # O(1)
        return top, "linked"  # O(1)
    s = slug(topic)  # O(n)
    target = top / PARENT / f"superlite-{s}"  # O(1)
    listed = git(top, "worktree", "list", "--porcelain")[1].splitlines()  # O(w)
    if any(ln.startswith("worktree ") and Path(ln[9:]).resolve() == target.resolve() for ln in listed):  # O(w)
        if target.is_dir():  # O(1)
            return target, "exists"  # O(1)
        git(top, "worktree", "prune")  # O(w) + spawn: folder was deleted, drop the stale registration
    if target.exists() or target.is_symlink():  # O(1)
        raise Taken(f"{target} exists and is not a git worktree")  # O(1)
    add_exclude(top, PARENT, f"{PARENT}/superlite-{s}/x")  # O(e) + spawns
    br = f"superlite/{s}"  # O(1)
    if git(top, "show-ref", "--verify", "-q", f"refs/heads/{br}")[0] == 0:  # O(1) + spawn
        rc, _, err = git(top, "worktree", "add", str(target), br)  # O(files) + spawn
    else:  # O(1)
        rc, _, err = git(top, "worktree", "add", "-b", br, str(target), "HEAD")  # O(files) + spawn
    if rc:  # O(1)
        raise RuntimeError(f"git worktree add failed: {err}")  # O(1)
    return target, "created"  # O(1)


def inplace(reason, sd):  # O(f + r)
    """Record the in-place opt-out in the inline-flow marker of state folder `sd` and the ledger -> False when no marker."""
    f = Path(sd) / MARKER  # O(1)
    try:  # O(1)
        data = json.loads(f.read_text(encoding="utf-8"))  # O(f)
    except (OSError, ValueError):  # O(1) absent or unreadable
        return False  # O(1)
    if not isinstance(data, dict):  # O(1)
        return False  # O(1)
    data["inplace"] = reason  # O(1)
    f.write_text(json.dumps(data) + "\n", encoding="utf-8")  # O(f + r)
    with (Path(sd) / "progress.md").open("a", encoding="utf-8") as fh:  # O(1)
        fh.write(f"Ruling: in place - {reason}\n")  # O(r)
    return True  # O(1)


def main(argv=None):  # O(w) + spawns
    ap = argparse.ArgumentParser(prog="worktree")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    e = sub.add_parser("ensure")  # O(1)
    e.add_argument("topic")  # O(1)
    e.add_argument("--repo", default=".")  # O(1)
    i = sub.add_parser("inplace")  # O(1)
    i.add_argument("--reason", required=True)  # O(1)
    a = ap.parse_args(argv)  # O(args)
    if a.cmd == "inplace":  # O(1)
        import state  # noqa: E402  # O(1) module load, only for this subcommand
        reason = " ".join(a.reason.split())  # one ledger line | O(r)
        if not reason:  # O(1)
            print("worktree: inplace needs a non-empty --reason", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not inplace(reason, state.resolve()):  # O(d + f)
            print("worktree: no inline flow is marked here; nothing to opt out of", file=sys.stderr)  # O(1)
            return 0  # O(1)
        print(f"worktree: in place - {reason}; edits in this checkout are no longer refused")  # O(r)
        return 0  # O(1)
    try:  # O(1)
        path, state = ensure(a.topic, Path(a.repo))  # O(w) + spawns
    except Taken as ex:  # O(1)
        print(f"worktree: {ex}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    except RuntimeError as ex:  # O(1)
        print(f"worktree: {ex}", file=sys.stderr)  # O(1)
        return 1  # O(1)
    if state == "no-repo":  # O(1)
        print(f"worktree: {no_repo_reason(path) or 'bare repository'}; using {path.as_posix()} as is", file=sys.stderr)  # O(1)
    elif state == "created":  # O(1)
        line = missing_line(missing_ignored(path.parents[len(PARENT.split("/"))], path))  # the main root above <PARENT>/<name> | O(i) + spawn
        if line:  # O(1)
            print(line, file=sys.stderr)  # O(1)
    print(path.as_posix())  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
