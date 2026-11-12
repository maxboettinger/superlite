#!/usr/bin/env python3
"""suite_stamp: reads the green-test stamp a `maxapp test` run leaves in the git common dir (`maxapp/test/<tree id>.<platform>`, lines tree=, platform=, commit=, tests=; counts only when tree= and platform= match and tests is an integer above 0; superlite reads it and never writes it), finds the commit whose tree a stamp covers (green_base: HEAD first, else the first stamped first-parent ancestor when every path changed since is not code), tells for the ship sync whether the tree changed in code or only in not-code paths (sync_change), and matches paths against the not_code globs (#627, #639)."""
# Complexity notation: n = changed paths, d = ancestor depth, g = globs
import re  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
from pathlib import Path  # O(1)


def maxapp_platforms(command: str) -> "list[str] | None":
    try:  # O(1)
        words = shlex.split(command)  # O(len)
    except ValueError:  # O(1)
        return None  # O(1)
    if not words or Path(words[0]).name != "maxapp" or words[1:2] != ["test"]:  # O(1)
        return None  # O(1)
    if words[2:] == []:  # O(1)
        return ["macOS"]  # O(1)
    if words[2:] == ["--ios"]:  # O(1)
        return ["macOS", "iOS"]  # O(1)
    return None  # O(1)


def _glob_re(g: str) -> "re.Pattern":
    out = ""  # O(1)
    i = 0  # O(1)
    while i < len(g):  # O(len)
        if g.startswith("**/", i):  # O(1)
            out += "(?:.*/)?"  # O(1)
            i += 3  # O(1)
        elif g.startswith("**", i):  # O(1)
            out += ".*"  # O(1)
            i += 2  # O(1)
        elif g[i] == "*":  # O(1)
            out += "[^/]*"  # O(1)
            i += 1  # O(1)
        elif g[i] == "?":  # O(1)
            out += "[^/]"  # O(1)
            i += 1  # O(1)
        else:  # O(1)
            out += re.escape(g[i])  # O(1)
            i += 1  # O(1)
    return re.compile(out)  # O(len)


def is_not_code(path: str, globs: "list[str]") -> bool:
    return any(_glob_re(g).fullmatch(path) for g in globs)  # O(g * len)


def _git(root, *args) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)  # O(repo)
    return r.stdout  # O(1)


def _changed(root, base: str) -> "list[str]":
    tracked = _git(root, "diff", "--name-only", "--no-renames", "-z", base).split("\0")  # O(n)
    other = _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")  # O(n)
    paths = sorted({p for p in tracked + other if p and not p.startswith(".build/")})  # O(n log n)
    return paths  # O(1)


def _read_stamp(f: Path, tree: str, platform: str) -> "int | None":
    try:  # O(1)
        text = f.read_text()  # O(size)
    except OSError:  # O(1)
        return None  # O(1)
    kv = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)  # O(lines)
    if kv.get("tree") != tree or kv.get("platform") != platform:  # O(1)
        return None  # O(1)
    try:  # O(1)
        n = int(kv.get("tests", ""))  # O(1)
    except ValueError:  # O(1)
        return None  # O(1)
    return n if n > 0 else None  # O(1)


def green_base(root, command: str, not_code: "list[str]", depth: int = 50) -> "dict | None":
    platforms = maxapp_platforms(command)  # O(1)
    if platforms is None:  # O(1)
        return None  # O(1)
    try:  # O(1)
        common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())  # O(repo)
        commits = _git(root, "rev-list", "--first-parent", f"--max-count={depth}", "HEAD").split()  # O(d)
        for c in commits:  # O(d)
            tree = _git(root, "rev-parse", f"{c}^{{tree}}").strip()  # O(1)
            files = [common / "maxapp" / "test" / f"{tree}.{p}" for p in platforms]  # O(1)
            if not any(f.exists() for f in files):  # O(1) not stamped: try the next ancestor
                continue  # O(1)
            counts = [_read_stamp(f, tree, p) for f, p in zip(files, platforms)]  # O(1)
            if any(n is None for n in counts):  # O(1) the first stamped commit is the base
                return None  # O(1)
            changed = _changed(root, c)  # O(n)
            if not all(is_not_code(p, not_code) for p in changed):  # O(n * g)
                return None  # O(1)
            return {"commit": c, "tree": tree, "tests": sum(counts), "platforms": platforms,
                    "stamps": [str(f) for f in files], "changed": changed}  # O(1)
    except (subprocess.CalledProcessError, OSError):  # O(1)
        return None  # O(1)
    return None  # O(1)


def sync_change(root, before: str, after: str, not_code: "list[str]") -> "tuple[str, list[str]]":
    try:  # O(1)
        if _git(root, "rev-parse", f"{before}^{{tree}}") == _git(root, "rev-parse", f"{after}^{{tree}}"):  # O(1)
            return "unchanged", []  # O(1)
        paths = sorted(p for p in _git(root, "diff", "--name-only", "--no-renames", "-z", before, after).split("\0") if p)  # O(n)
    except (subprocess.CalledProcessError, OSError):  # O(1)
        return "code", []  # O(1)
    return ("not_code" if all(is_not_code(p, not_code) for p in paths) else "code"), paths  # O(n * g)
