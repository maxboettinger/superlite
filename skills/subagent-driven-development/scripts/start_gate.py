#!/usr/bin/env python3
"""Start gate for `plan_tools lint --stable`: no build starts in a shared checkout by accident.

Modes, checked in this order: resumed (the root's .superlite/stable.json exists), no-repo, linked
(a linked git worktree), in-place (plan header `**Worktree:** none`), shared (blocked).
An in-place run records the files already dirty at the first lint, so commit_task can tell them
from changes made during the run. Stdlib only.
"""
# Complexity notation: h = plan header lines, f = dirty files, p = lines of progress.md
import re  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)
from typing import NamedTuple  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import worktree  # noqa: E402  # O(1) module load

RULING = "- Ruling: in-place run - plan header **Worktree:** none - cost if wrong: collisions with other sessions in this checkout"  # O(1)


class Gate(NamedTuple):  # O(1)
    ok: bool  # O(1)
    mode: str  # O(1)
    messages: list  # O(1)
    baseline: list  # O(1)


def opt_out(plan_text):  # O(h)
    head = re.split(r"^## ", plan_text, maxsplit=1, flags=re.M)[0]  # O(len head)
    return re.search(r"^\s*\*\*Worktree:\*\*\s*none\b", head, re.I | re.M) is not None  # O(len head)


def topic(plan):  # O(1)
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(plan).name.removesuffix(".md"))  # O(1)


def dirty(root, plan):  # O(f) + two spawns
    """-> sorted project-relative POSIX paths git reports dirty, without the plan's folder and .superlite/."""
    root = Path(root)  # O(1)
    pre = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()  # O(1) + spawn
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z", "--untracked-files=all"], capture_output=True, text=True, encoding="utf-8", errors="replace")  # O(f) + spawn
    parts = r.stdout.split("\0")  # O(f)
    paths = []  # O(1)
    i = 0  # O(1)
    while i < len(parts):  # O(f)
        e = parts[i]  # O(1)
        i += 1  # O(1)
        if len(e) < 4:  # O(1)
            continue  # O(1)
        paths.append(e[3:])  # O(1)
        if e[0] in "RC" or e[1] in "RC":  # the next entry is the old name, dirty too | O(1)
            if i < len(parts) and parts[i]:  # O(1)
                paths.append(parts[i])  # O(1)
            i += 1  # O(1)
    try:  # O(1)
        folder = Path(plan).resolve().parent.relative_to(root.resolve()).as_posix()  # O(1)
    except ValueError:  # O(1)
        folder = "."  # O(1)
    out = set()  # O(1)
    for p in paths:  # O(f)
        if pre:  # O(1)
            if not p.startswith(pre):  # O(1)
                continue  # O(1)
            p = p[len(pre):]  # O(1)
        if p.startswith(".superlite/") or (folder != "." and p.startswith(folder + "/")):  # O(1)
            continue  # O(1)
        out.add(p)  # O(1)
    return sorted(out)  # O(f log f)


def check(root, plan, cwd, sl):  # O(f + h) + spawns
    root = Path(root)  # O(1)
    if (root / ".superlite" / "stable.json").exists():  # O(1)
        return Gate(True, "resumed", [], [])  # O(1)
    if worktree.no_repo_reason(root):  # O(1) + spawns
        return Gate(True, "no-repo", [], [])  # O(1)
    msgs = []  # O(1)
    try:  # O(1)
        inside = Path(cwd).resolve().is_relative_to(root.resolve())  # O(1)
    except (OSError, ValueError):  # O(1)
        inside = True  # O(1)
    if not inside:  # O(1)
        msgs.append(f"WARN: this session's directory {Path(cwd).resolve().as_posix()} is outside the run root {root.as_posix()}. "  # O(1)
                    f"Claude Code: EnterWorktree path={root.as_posix()}; other harnesses: cd {root.as_posix()}")
    if worktree.is_linked(root):  # O(1)
        return Gate(True, "linked", msgs, [])  # O(1)
    try:  # O(1)
        text = Path(plan).read_text(encoding="utf-8", errors="replace")  # O(file)
    except OSError:  # O(1)
        text = ""  # O(1)
    if opt_out(text):  # O(h)
        base = dirty(root, plan)  # O(f) + spawns
        return Gate(True, "in-place", [f"IN-PLACE: dirty before start: {', '.join(base) or 'none'}"] + msgs, base)  # O(f)
    return Gate(False, "shared", [  # O(1)
        f"lint --stable: BLOCKED: {root.as_posix()} is the shared checkout, not a worktree",
        f"run: {shlex.quote(str(sl))} worktree ensure {shlex.quote(topic(plan))}",
        "or add **Worktree:** none to the plan header"] + msgs, [])


def report(gate, root):  # O(p) file
    """Print the gate's messages (stdout for IN-PLACE, stderr otherwise); log an in-place run once."""
    for m in gate.messages:  # O(m)
        print(m, file=sys.stdout if gate.ok and m.startswith("IN-PLACE") else sys.stderr)  # O(1)
    if gate.ok and gate.mode == "in-place":  # O(1)
        f = Path(root) / ".superlite" / "progress.md"  # O(1)
        old = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""  # O(p)
        if RULING not in old.splitlines():  # O(p)
            f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
            f.write_text(old + ("" if not old or old.endswith("\n") else "\n") + RULING + "\n", encoding="utf-8")  # O(p)
