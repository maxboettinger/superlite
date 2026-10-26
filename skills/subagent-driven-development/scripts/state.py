#!/usr/bin/env python3
"""Which `.superlite` folder a session uses: one per session, so parallel sessions in worktrees never share a gate.

    state.py where [--plan P]        print the resolved .superlite folder and how it was found

Resolution, the same order as the hooks (hooks/superlite-state.sh):
  1. $SUPERLITE_STATE_DIR (a .superlite path), for hosts without session ids;
  2. the session's binding: $SUPERLITE_HOME/sessions/<session id> (default ~/.superlite/sessions/) holds the absolute
     path of the bound .superlite folder; used while that folder exists and no other session owns it;
  3. ./.superlite, unless another live session owns it; then the session's private folder
     $SUPERLITE_HOME/sessions/<session id>.d/.superlite (state set before any plan, moved to the plan's folder on the
     next bind; the hooks judge paths against the launch directory meanwhile).
A bind refuses a folder another live session owns, except that a session launched in the folder's own project (launch
directory = the .superlite's parent) takes it over when the owner's recorded launch directory (binding line 3) is
elsewhere; an owner launched in the same directory, or an old binding without line 3, still needs `force`.
The session id is $SUPERLITE_SESSION_ID (the SessionStart hook writes the hook's id there, so it follows /clear), else
CLAUDE_CODE_SESSION_ID. A plan (or review plan) given explicitly resolves to the .superlite next to its nearest `docs`
ancestor below the git toplevel, else at the toplevel, so docs/superpowers/plans/x.md in a worktree maps to
<worktree>/.superlite; outside git the old rule holds. `bind` writes the binding and `.superlite/session` (the owning
id), moves a pending gate (orchestrator.json, human-replies.jsonl) from the session's previous folder, and refuses a
folder another live session owns (`force` takes it over). An owner is live while its binding points at the folder.
Paths stay as given (absolute, symlinks not resolved, a relative path joined to $PWD), as the hooks see them. A
binding also records $CLAUDE_PID, so the SessionStart hook moves it to the new id after /clear (same process). Bindings
older than 14 days are pruned on each bind. Library: launch_dir, owner_launch_dir, own_project, git_root, plan_dir, session_id, bound, resolve, bind, unbind, owner, live_owner. Stdlib only.
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
GATE_FILES = ("orchestrator.json", "human-replies.jsonl")  # a pending gate follows its session to the plan's folder | O(1)
PRUNE_S = 14 * 24 * 3600  # O(1)
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")  # a session id is also a file name | O(1)


class Owned(Exception):  # O(1)
    """bind refused: another live session owns the folder."""


def home() -> Path:  # O(1)
    return Path(os.environ.get("SUPERLITE_HOME") or Path.home() / ".superlite")  # O(1)


def session_id():  # O(1)
    """The session id: $SUPERLITE_SESSION_ID (set by the SessionStart hook), else CLAUDE_CODE_SESSION_ID; else None."""
    for var in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):  # O(1) iterations (2)
        sid = os.environ.get(var, "")  # O(1)
        if _SID.match(sid):  # O(1)
            return sid  # O(1)
    return None  # O(1)


def _abs(path) -> Path:  # O(d)
    """Absolute, `..` collapsed, symlinks kept: the form Claude Code and the hooks pass around. A relative path joins
    the logical $PWD (os.getcwd() is the physical one) while both name the same folder."""
    p = os.fspath(path)  # O(1)
    pwd = os.environ.get("PWD", "")  # O(1)
    if not os.path.isabs(p) and pwd and os.path.isabs(pwd):  # O(1)
        try:  # O(1)
            if os.path.samefile(pwd, os.getcwd()):  # O(1)
                return Path(os.path.normpath(os.path.join(pwd, p)))  # O(d)
        except OSError:  # O(1)
            pass  # O(1)
    return Path(os.path.abspath(p))  # O(d)


def git_root(path):  # O(d)
    """The nearest folder at or above path holding `.git` (a directory, or a worktree's file), or None."""
    p = _abs(path)  # O(d)
    if not p.is_dir():  # O(1)
        p = p.parent  # O(1)
    for d in (p, *p.parents):  # O(d) iterations
        if (d / ".git").exists():  # O(1)
            return d  # O(1)
    return None  # O(1)


def plan_dir(plan_or_dir) -> Path:  # O(d)
    """The .superlite folder for an explicit plan, review plan, project folder or .superlite folder."""
    p = _abs(plan_or_dir)  # O(d)
    if p.name == ".superlite":  # O(1)
        return p  # O(1)
    if p.is_dir():  # O(1)
        return p / ".superlite"  # O(1)
    root = p.parent  # O(1)
    if root.name == ".superlite":  # O(1)
        return root  # O(1)
    top = git_root(root)  # O(d)
    if top is not None:  # O(1)
        for d in (root, *root.parents):  # nearest `docs` ancestor below the toplevel: a monorepo's app | O(d)
            if d == top:  # O(1)
                break  # O(1)
            if d.name == "docs":  # O(1)
                return d.parent / ".superlite"  # O(1)
        return top / ".superlite"  # O(1)
    if root.name == "plans" and root.parent.name == "docs":  # O(1)
        return root.parent.parent / ".superlite"  # O(1)
    return root / ".superlite"  # O(1)


def _binding(sid) -> Path:  # O(1)
    return home() / "sessions" / sid  # O(1)


def private_dir(sid) -> Path:  # O(1)
    """The session's own folder, for state set before any plan while ./.superlite belongs to another session."""
    return home() / "sessions" / f"{sid}.d" / ".superlite"  # O(1)


def _target(sid):  # O(1)
    try:  # O(1)
        lines = _binding(sid).read_text(encoding="utf-8").splitlines()  # O(1)
        target = Path(lines[0].strip()) if lines else Path()  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return target if target.is_absolute() else None  # O(1)


def owner(sd):  # O(1)
    """The session id recorded in sd/session, or None."""
    try:  # O(1)
        sid = (Path(sd) / OWNER).read_text(encoding="utf-8").strip()  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return sid or None  # O(1)


def live_owner(sd, sid=None):  # O(d)
    """Another session that owns sd and is still bound to it, or None (no owner, this session, or a stale owner)."""
    o = owner(sd)  # O(1)
    if not o or o == (sid or session_id()) or not _SID.match(o):  # O(1)
        return None  # O(1)
    t = _target(o)  # O(1)
    return o if t is not None and _abs(t) == _abs(sd) else None  # O(d)


def launch_dir() -> Path:  # O(d)
    """Where this session was launched: $CLAUDE_PROJECT_DIR, else the logical $PWD (a stale one gives the real cwd)."""
    env = os.environ.get("CLAUDE_PROJECT_DIR", "")  # O(1)
    if env:  # O(1)
        return _abs(env)  # O(d)
    pwd = os.environ.get("PWD", "")  # O(1)
    if os.path.isabs(pwd):  # O(1)
        try:  # O(1)
            if os.path.samefile(pwd, os.getcwd()):  # O(1)
                return _abs(pwd)  # O(d)
        except OSError:  # O(1)
            return _abs(pwd)  # O(d)
    return _abs(os.getcwd())  # O(d)


def owner_launch_dir(sid):  # O(1)
    """The launch directory recorded on line 3 of the session's binding, or None (old binding, unreadable)."""
    try:  # O(1)
        lines = _binding(sid).read_text(encoding="utf-8").splitlines()  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return Path(lines[2].strip()) if len(lines) > 2 and os.path.isabs(lines[2].strip()) else None  # O(1)


def own_project(sd) -> bool:  # O(d)
    """True when this session was launched in sd's project (the folder's parent)."""
    return launch_dir() == _abs(sd).parent  # O(d)


def _hands_over(sd, other) -> bool:  # O(d)
    """True when this session may take sd from its live owner without force: launched in sd's project, owner elsewhere."""
    if not own_project(sd):  # O(d)
        return False  # O(1)
    ol = owner_launch_dir(other)  # O(1)
    return ol is not None and _abs(ol) != _abs(sd).parent  # O(d)


def bound(sid=None):  # O(d)
    """The .superlite folder bound to the session, while it exists and no other session took it over; else None."""
    sid = sid or session_id()  # O(1)
    if not sid:  # O(1)
        return None  # O(1)
    t = _target(sid)  # O(1)
    if t is None or not t.is_dir() or owner(t) not in (None, sid):  # O(1)
        return None  # O(1)
    return t  # O(1)


def resolve(plan_or_dir=None) -> Path:  # O(d)
    """An explicit plan or folder wins; else $SUPERLITE_STATE_DIR, the session's binding, ./.superlite or the private folder."""
    if plan_or_dir is not None:  # O(1)
        return plan_dir(plan_or_dir)  # O(d)
    env = os.environ.get("SUPERLITE_STATE_DIR", "")  # O(1)
    if env:  # O(1)
        return _abs(env)  # O(d)
    b = bound()  # O(d)
    if b is not None:  # O(1)
        return b  # O(1)
    sid = session_id()  # O(1)
    other = live_owner(".superlite", sid) if sid else None  # O(d)
    if other and not _hands_over(".superlite", other):  # ./.superlite is another session's run | O(d)
        return private_dir(sid)  # O(1)
    return Path(".superlite")  # O(1)


def _prune(now) -> None:  # O(b)
    try:  # O(1)
        entries = list((home() / "sessions").iterdir())  # O(b)
    except OSError:  # O(1)
        return  # O(1)
    for f in entries:  # O(b) iterations
        try:  # O(1)
            if f.is_file() and now - f.stat().st_mtime > PRUNE_S:  # O(1)
                f.unlink()  # O(1)
        except OSError:  # O(1)
            pass  # O(1)


def _move_gate(old: Path, new: Path) -> None:  # O(1)
    """A gate still pending in the session's previous folder moves to the new one (never over an existing gate)."""
    if (new / GATE_FILES[0]).exists() or not (old / GATE_FILES[0]).is_file():  # O(1)
        return  # O(1)
    for f in GATE_FILES:  # O(1) iterations (2)
        if (old / f).is_file():  # O(1)
            (old / f).replace(new / f)  # O(1)


def bind(sd, sid=None, force=False):  # O(b + d)
    """Bind the session to sd (its binding file and sd/session); returns the session id, or None without one or when
    the binding cannot be written (a warning on stderr). Raises Owned when another live session owns sd (unless force)."""
    sid = sid or session_id()  # O(1)
    if not sid:  # O(1)
        return None  # O(1)
    sd = _abs(sd)  # O(d)
    other = live_owner(sd, sid)  # O(d)
    if other and not force and _hands_over(sd, other):  # an owner launched elsewhere hands the folder to its own project | O(d)
        other = None  # O(1)
    if other and not force:  # O(1)
        raise Owned(f"{sd} belongs to session {other}; pass --plan with your own worktree's plan, "  # O(1)
                    "or take it over with `sl orchestrator bind --force`")
    try:  # O(1)
        sd.mkdir(parents=True, exist_ok=True)  # O(1)
        old = bound(sid)  # O(d)
        if old is not None and _abs(old) != sd:  # the session moved: its pending gate comes along | O(d)
            _move_gate(old, sd)  # O(1)
            if owner(old) == sid:  # O(1)
                (old / OWNER).unlink(missing_ok=True)  # O(1)
        (sd / OWNER).write_text(sid + "\n", encoding="utf-8")  # O(1)
        f = _binding(sid)  # O(1)
        f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        _prune(time.time())  # O(b)
        pid = os.environ.get("CLAUDE_PID", "")  # line 2: the Claude process, so /clear can hand the binding on | O(1)
        f.write_text(sd.as_posix() + "\n" + (pid if pid.isdigit() else "") + "\n" + launch_dir().as_posix() + "\n", encoding="utf-8")  # line 3: launch dir; forward slashes for bash | O(d)
    except OSError as e:  # a read-only home must not stop the run | O(1)
        print(f"superlite: session binding not written ({e}); hooks fall back to the launch directory", file=sys.stderr)  # O(1)
        return None  # O(1)
    return sid  # O(1)


def unbind(sd, sid=None) -> None:  # O(d)
    """Release sd: drop sd/session when this session (or nobody) owns it, and the session's binding when it points at sd."""
    sid = sid or session_id()  # O(1)
    sd = _abs(sd)  # O(d)
    if owner(sd) in (None, sid):  # never another session's folder | O(1)
        (sd / OWNER).unlink(missing_ok=True)  # O(1)
    t = _target(sid) if sid else None  # O(1)
    if t is not None and _abs(t) == sd:  # O(d)
        _binding(sid).unlink(missing_ok=True)  # O(1)


def main(argv=None):  # O(d)
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    w = sub.add_parser("where")  # O(1)
    w.add_argument("--plan")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sd = resolve(a.plan)  # O(d)
    if a.plan:  # O(1)
        how = "plan"  # O(1)
    elif os.environ.get("SUPERLITE_STATE_DIR"):  # O(1)
        how = "SUPERLITE_STATE_DIR"  # O(1)
    else:  # O(1)
        how = "session binding" if bound() else "current directory"  # O(d)
    print(f"{_abs(sd)} ({how})")  # O(d)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
