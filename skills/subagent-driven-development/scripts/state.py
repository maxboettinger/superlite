#!/usr/bin/env python3
"""Which `.superlite` folder a session uses: one per session, so parallel sessions in worktrees never share a gate.

    state.py where [--plan P]        print the resolved .superlite folder and how it was found

Resolution, the same order as the hooks (hooks/block-coordinator-edits and the others):
  1. $SUPERLITE_STATE_DIR (an absolute .superlite path), for hosts without session ids;
  2. the session's binding: $SUPERLITE_HOME/sessions/<CLAUDE_CODE_SESSION_ID> (default ~/.superlite/sessions/)
     holds the absolute path of the bound .superlite folder; used while that folder exists;
  3. ./.superlite.
A plan (or review plan) given explicitly resolves to the .superlite at its git toplevel, so a plan under
docs/superpowers/plans/ in a worktree maps to <worktree>/.superlite; outside git the old rule holds (next to the
plan, docs/plans/ -> the repo root). `bind` writes the binding and `.superlite/session` (the owning session id);
hooks skip a legacy folder whose `session` names another session. Bindings older than 14 days are pruned on
each bind. Library: git_root, plan_dir, session_id, bound, resolve, bind, unbind, owner. Stdlib only.
"""
# Complexity notation:
#   d = depth of a path (parents walked), b = bindings in $SUPERLITE_HOME/sessions
import argparse  # O(1)
import os  # O(1)
import re  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

OWNER = "session"  # .superlite/session: the id of the session bound to this folder | O(1)
PRUNE_S = 14 * 24 * 3600  # O(1)
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")  # a session id is also a file name | O(1)


def home() -> Path:  # O(1)
    return Path(os.environ.get("SUPERLITE_HOME") or Path.home() / ".superlite")  # O(1)


def session_id():  # O(1)
    """The current Claude Code session id (Bash gets it as CLAUDE_CODE_SESSION_ID), or None."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")  # O(1)
    return sid if _SID.match(sid) else None  # O(1)


def git_root(path):  # O(d)
    """The nearest folder at or above path holding `.git` (a directory, or a worktree's file), or None."""
    p = Path(path).resolve()  # O(d)
    if not p.is_dir():  # O(1)
        p = p.parent  # O(1)
    for d in (p, *p.parents):  # O(d) iterations
        if (d / ".git").exists():  # O(1)
            return d  # O(1)
    return None  # O(1)


def plan_dir(plan_or_dir) -> Path:  # O(d)
    """The .superlite folder for an explicit plan, review plan, project folder or .superlite folder."""
    p = Path(plan_or_dir).resolve()  # O(d)
    if p.name == ".superlite":  # O(1)
        return p  # O(1)
    if p.is_dir():  # O(1)
        return p / ".superlite"  # O(1)
    root = p.parent  # O(1)
    if root.name == ".superlite":  # O(1)
        return root  # O(1)
    top = git_root(root)  # O(d)
    if top is not None:  # O(1)
        return top / ".superlite"  # O(1)
    if root.name == "plans" and root.parent.name == "docs":  # O(1)
        return root.parent.parent / ".superlite"  # O(1)
    return root / ".superlite"  # O(1)


def _binding(sid) -> Path:  # O(1)
    return home() / "sessions" / sid  # O(1)


def bound(sid=None):  # O(1)
    """The .superlite folder bound to the session, while it exists; else None."""
    sid = sid or session_id()  # O(1)
    if not sid:  # O(1)
        return None  # O(1)
    try:  # O(1)
        target = Path(_binding(sid).read_text(encoding="utf-8").strip())  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return target if target.is_absolute() and target.is_dir() else None  # O(1)


def resolve(plan_or_dir=None) -> Path:  # O(d)
    """An explicit plan or folder wins; else $SUPERLITE_STATE_DIR, the session's binding, ./.superlite."""
    if plan_or_dir is not None:  # O(1)
        return plan_dir(plan_or_dir)  # O(d)
    env = os.environ.get("SUPERLITE_STATE_DIR", "")  # O(1)
    if env:  # O(1)
        return Path(env)  # O(1)
    return bound() or Path(".superlite")  # O(1)


def owner(sd):  # O(1)
    """The session id recorded in sd/session, or None."""
    try:  # O(1)
        sid = (Path(sd) / OWNER).read_text(encoding="utf-8").strip()  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return sid or None  # O(1)


def _prune(now) -> None:  # O(b)
    try:  # O(1)
        entries = list((home() / "sessions").iterdir())  # O(b)
    except OSError:  # O(1)
        return  # O(1)
    for f in entries:  # O(b) iterations
        try:  # O(1)
            if now - f.stat().st_mtime > PRUNE_S:  # O(1)
                f.unlink()  # O(1)
        except OSError:  # O(1)
            pass  # O(1)


def bind(sd, sid=None):  # O(b)
    """Bind the session to sd (its binding file and sd/session); returns the session id, or None without one."""
    sid = sid or session_id()  # O(1)
    if not sid:  # O(1)
        return None  # O(1)
    sd = Path(sd).resolve()  # O(d)
    old = bound(sid)  # O(1)
    if old is not None and old != sd and owner(old) == sid:  # the session moved: release its old folder | O(1)
        (old / OWNER).unlink(missing_ok=True)  # O(1)
    sd.mkdir(parents=True, exist_ok=True)  # O(1)
    (sd / OWNER).write_text(sid + "\n", encoding="utf-8")  # O(1)
    f = _binding(sid)  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    _prune(time.time())  # O(b)
    f.write_text(sd.as_posix() + "\n", encoding="utf-8")  # forward slashes: the hooks read it in bash | O(1)
    return sid  # O(1)


def unbind(sd, sid=None) -> None:  # O(1)
    """Release sd: drop sd/session and the session's binding when it points at sd."""
    sid = sid or session_id() or owner(sd)  # O(1)
    sd = Path(sd).resolve()  # O(d)
    if sid is None or owner(sd) in (None, sid):  # never take another session's folder | O(1)
        (sd / OWNER).unlink(missing_ok=True)  # O(1)
    if sid and bound(sid) == sd:  # O(1)
        _binding(sid).unlink(missing_ok=True)  # O(1)


def main(argv=None):  # O(d)
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    w = sub.add_parser("where")  # O(1)
    w.add_argument("--plan")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sd = resolve(a.plan)  # O(d)
    how = ("plan" if a.plan else "SUPERLITE_STATE_DIR" if os.environ.get("SUPERLITE_STATE_DIR")  # O(1)
           else "session binding" if bound() else "current directory")
    print(f"{Path(sd).resolve()} ({how})")  # O(d)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
