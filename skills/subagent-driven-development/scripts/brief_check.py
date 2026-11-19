#!/usr/bin/env python3
"""Brief check at send: flag a brief whose ROOT names a missing folder or whose mutation recipe cannot apply.

    brief_check.problems(path) -> up to 5 texts, one per missing absolute ROOT and per `git apply -R` recipe that cannot apply (never raises; reads the brief, runs read-only git)
    brief_check.note(problems) -> "" for none, else "Brief check (sl, before sending): a; b."

A recipe is a backtick span holding `git apply` and `-R`/`--reverse`, else such a whole line. A `|` splits a `git show`/`git diff`
producer from `git apply`; the pair runs as `git apply --check -R` and never writes. Any other `;`, `&`, `>`, `<`, `$`,
backtick or a second `|` skips the recipe, as does a producer option beyond -p, --patch, --binary, --format=, --pretty=.
"""
# Complexity notation:
# s = characters of the brief (capped at 200 KB), r = recipes and ROOT lines in it
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
from pathlib import Path  # O(1)

CAP = 200_000  # O(1)
MAX = 5  # O(1)
ROOT = re.compile(r"^[ \t]*(?:[-*][ \t]+)?((?:ROOT[ \t]*=|Root:)[ \t]*)(/[^\s`]*)", re.M)  # O(1)
SHA = re.compile(r"^[0-9a-f]{7,40}$")  # O(1)
UNSAFE = re.compile(r"[;&><$`]")  # O(1)


def _git(args: list, cwd: str, data: bytes = None) -> "subprocess.CompletedProcess":  # O(1) git call, 10 s cap
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
    return subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True, timeout=10, env=env)  # O(1)


def _recipes(text: str) -> list:  # O(s)
    """The recipe strings in the brief, in order."""
    out = []  # O(1)
    for line in text.split("\n"):  # O(s)
        spans = re.findall(r"`([^`]+)`", line)  # O(len)
        picked = [x.strip() for x in spans if "git apply" in x and re.search(r"(?:^|\s)(?:-R|--reverse)(?:\s|$)", x)]  # O(len)
        if not picked and "git apply" in line and re.search(r"(?:^|\s)(?:-R|--reverse)(?:\s|$)", line) and "`" not in line:  # O(len)
            picked = [line.strip()]  # O(1)
        out.extend(picked)  # O(1)
    return out  # O(1)


def _first_line(data: bytes) -> str:  # O(len)
    lines = data.decode("utf-8", "replace").strip().split("\n")  # O(len)
    return lines[0].strip() if lines and lines[0].strip() else "git apply failed"  # O(1)


def _recipe(rec: str, root: str) -> str:  # O(1) git calls
    """The problem text for one recipe, or "" when it applies or is skipped."""
    parts = rec.split("|")  # O(len)
    if len(parts) > 2 or any(UNSAFE.search(p) for p in parts):  # O(len)
        return ""  # O(1)
    try:  # O(1)
        argvs = [shlex.split(p) for p in parts]  # O(len)
    except ValueError:  # O(1)
        return ""  # O(1)
    apply_argv = argvs[-1]  # O(1)
    if apply_argv[:2] != ["git", "apply"]:  # O(1)
        return ""  # O(1)
    keep = [a for a in apply_argv[2:] if re.match(r"^-p\d+$", a)]  # O(args)
    where = [a for a in apply_argv[2:] if not a.startswith("-")]  # O(args)
    try:  # O(1)
        if len(argvs) == 2:  # O(1)
            prod = argvs[0]  # O(1)
            if len(prod) < 2 or prod[0] != "git" or prod[1] not in ("show", "diff") or where:  # O(1)
                return ""  # O(1)
            if any(a.startswith("-") and a not in ("--", "-p", "--patch", "--binary") and not a.startswith(("--format=", "--pretty=")) for a in prod[2:]):  # only allow-listed options | O(args)
                return ""  # O(1)
            made = _git([prod[1], "--no-ext-diff", "--no-textconv", "--no-color", *prod[2:]], root)  # O(1)
            if made.returncode != 0:  # O(1)
                return ""  # O(1)
            data = made.stdout  # O(1)
        else:  # O(1)
            if len(where) != 1:  # O(1)
                return ""  # O(1)
            target = Path(root) / where[0]  # O(1)
            if not target.is_file():  # O(1)
                if SHA.match(where[0]) and _git(["cat-file", "-t", where[0] + "^{commit}"], root).returncode == 0:  # O(1)
                    return f"recipe `{rec}` names a commit, not a patch file (`git show {where[0]} | git apply -R` applies it)"  # O(1)
                return ""  # O(1)
            data = target.read_bytes()  # O(patch)
        done = _git(["apply", "--check", "-R", *keep], root, data)  # O(1)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return ""  # O(1)
    if done.returncode == 0:  # O(1)
        return ""  # O(1)
    return f"recipe `{rec}` does not apply in {root}: {_first_line(done.stderr)} (a later commit rewrote those lines: build the mutation by hand)"  # O(1)


def problems(path: str) -> list[str]:  # O(s + r)
    """Up to 5 problem texts for the brief at PATH; [] when it cannot be read."""
    try:  # O(1)
        with open(path, "rb") as f:  # O(1)
            text = f.read(CAP).decode("utf-8", "replace")  # O(s)
    except (OSError, ValueError):  # O(1)
        return []  # O(1)
    try:  # O(1)
        out, roots = [], []  # O(1)
        for m in ROOT.finditer(text):  # O(r)
            folder = m.group(2).rstrip(".,;:)'\"")  # O(len)
            if os.path.isdir(folder):  # O(1)
                roots.append(folder)  # O(1)
            else:  # O(1)
                label = m.group(1).strip()  # O(1)
                out.append(f"{label}{'' if label.endswith('=') else ' '}{folder} names a folder that does not exist")  # O(1)
        recipes = _recipes(text)  # O(s)
        root = roots[0] if roots else ""  # O(1)
        if recipes and not root:  # O(1)
            top = _git(["rev-parse", "--show-toplevel"], str(Path(path).resolve().parent))  # O(1)
            root = top.stdout.decode("utf-8", "replace").strip() if top.returncode == 0 else ""  # O(1)
        for rec in recipes if root else []:  # O(r)
            msg = _recipe(rec, root)  # O(1)
            if msg:  # O(1)
                out.append(msg)  # O(1)
        return out[:MAX]  # O(1)
    except Exception:  # never raises | O(1)
        return []  # O(1)


def note(problems: list[str]) -> str:  # O(p)
    """The sentence a brief message appends; "" when there is no problem."""
    return f"Brief check (sl, before sending): {'; '.join(problems)}." if problems else ""  # O(p)
