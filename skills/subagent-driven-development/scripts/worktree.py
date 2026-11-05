#!/usr/bin/env python3
"""Find or create the run's own git worktree, so a change never starts in a shared checkout.

    worktree.py ensure TOPIC [--repo DIR]     print the absolute path of the run folder

From a linked worktree the tool returns that worktree. Otherwise it returns (or creates)
`<main root>/.claude/worktrees/superlite-<slug>` on branch `superlite/<slug>`. The main checkout's
branch and files are never changed. No repository, a bare one, or no commit yet: the start folder.
Exit 2 when a plain folder sits at the target path. Stdlib only.
"""
# Complexity notation: n = length of the topic, w = registered worktrees, e = lines of info/exclude
import argparse  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

PARENT = ".claude/worktrees"  # O(1)


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


def main(argv=None):  # O(w) + spawns
    ap = argparse.ArgumentParser(prog="worktree")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    e = sub.add_parser("ensure")  # O(1)
    e.add_argument("topic")  # O(1)
    e.add_argument("--repo", default=".")  # O(1)
    a = ap.parse_args(argv)  # O(args)
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
        print("worktree: fresh worktree has no installed dependencies or ignored local files; install them there", file=sys.stderr)  # O(1)
    print(path.as_posix())  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
