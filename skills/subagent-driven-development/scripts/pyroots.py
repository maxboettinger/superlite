#!/usr/bin/env python3
"""Python import roots of a project beyond the repository root and `src/`.

Library: import_roots(root, plan=None) -> sorted repository-relative POSIX directories.
Order: `.superlite/test-cmd.json` key "pythonpath" (a list of strings) wins; else derived from the plan's
`**Produces:**` dotted names (`a.b.c(`): D is a root for `a.b.c` when D/a/b.py or D/a/b/__init__.py exists
(two parts: D/a.py or D/a/__init__.py). The root itself and `src/` are never returned; a directory
holding `__init__.py` is a package, never a root, and nothing is searched below it or below a found root. Stdlib only.
"""
# Complexity notation:
#   d = directories walked (depth <= 8), p = Produces names in the plan
import ast  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path, PurePosixPath  # O(1)

CONFIG = ".superlite/test-cmd.json"  # O(1)
SKIP = {"node_modules", "__pycache__", "site-packages", ".superlite", "venv", "env", "dist", "build", "target", "Pods"}  # O(1)
MAX_DEPTH = 8  # O(1)
PRODUCES = re.compile(r"^\*\*Produces:\*\*\s*`?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(", re.M)  # O(1)


def configured(root):  # O(file) | list or None
    try:  # O(1)
        data = json.loads((Path(root) / CONFIG).read_text(encoding="utf-8", errors="replace"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    key = data.get("pythonpath") if isinstance(data, dict) else None  # O(1)
    if isinstance(key, list) and all(isinstance(k, str) for k in key):  # O(len)
        return key  # O(1)
    return None  # O(1)


def produced_names(root, plan):  # O(plan text) | list of dotted names
    if not plan:  # O(1)
        return []  # O(1)
    p = Path(plan)  # O(1)
    p = p if p.is_absolute() else Path(root) / p  # O(1)
    try:  # O(1)
        text = p.read_text(encoding="utf-8", errors="replace")  # O(plan)
    except OSError:  # O(1)
        return []  # O(1)
    return sorted(set(PRODUCES.findall(text)))  # O(p log p)


def candidates(name):  # O(parts) | relative file/dir stems whose existence makes a dir a root
    parts = name.split(".")  # O(parts)
    out = []  # O(1)
    for n in range(len(parts) - 1, 0, -1):  # O(parts) longest module first
        stem = "/".join(parts[:n])  # O(parts)
        out += [stem + ".py", stem + "/__init__.py"]  # O(1)
    return out  # O(parts)


def derive(root, names):  # O(d * p) | set of relative dirs
    root = Path(root)  # O(1)
    found = set()  # O(1)
    cands = [c for n in names for c in candidates(n)]  # O(p * parts)
    for dirpath, dirs, _ in os.walk(root):  # O(d)
        rel = Path(dirpath).relative_to(root)  # O(depth)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP and len(rel.parts) < MAX_DEPTH]  # O(dirs)
        if rel.parts in ((), ("src",)):  # O(1)
            continue  # O(1)
        if (Path(dirpath) / "__init__.py").is_file():  # a package is never a root, nor holds one | O(1)
            dirs[:] = []  # O(1)
            continue  # O(1)
        if any((Path(dirpath) / c).is_file() for c in cands):  # O(cands)
            found.add(rel.as_posix())  # O(depth)
            dirs[:] = []  # O(1)
    return found  # O(d)


def import_roots(root, plan=None):  # O(d * p) | sorted, deduped, repository-relative POSIX
    key = configured(root)  # O(file)
    if key is not None:  # O(1)
        return sorted(set(key))  # O(k log k)
    names = produced_names(root, plan)  # O(plan)
    return sorted(derive(root, names)) if names else []  # O(d * p)


def advice(root, dirs):  # O(k log k) | the config change that makes dirs importable
    names = sorted(set(dirs))  # O(k log k)
    if configured(root) is not None:  # O(file)
        return "add " + ", ".join(json.dumps(n) for n in names) + ' to "pythonpath" in ' + CONFIG  # O(k)
    return 'add "pythonpath": ' + json.dumps(names) + " to " + CONFIG  # O(k)


def _holds(d, name):  # O(entries) | does directory d offer the module `name`
    d = Path(d)  # O(1)
    if (d / (name + ".py")).is_file() or (d / name / "__init__.py").is_file():  # O(1)
        return True  # O(1)
    try:  # O(1)
        return any(e.name.endswith(".py") and e.is_file() for e in os.scandir(d / name))  # O(entries)
    except OSError:  # O(1)
        return False  # O(1)


def _resolves(d, name):  # O(1) | a file or folder `name` in d: a namespace package resolves
    return (Path(d) / (name + ".py")).is_file() or (Path(d) / name).is_dir()  # O(1)


def hint(root, name, roots, near, walk=True):  # O(d) | directory that would make `name` importable, or None
    root = Path(root)  # O(1)
    skip = {".", "src", *roots}  # O(r)
    if any(_resolves(root / r, name) for r in ("", "src", *roots)):  # O(r)
        return None  # O(1)
    for anc in _ancestors(near):  # O(depth)
        if anc not in skip and _holds(root / anc, name):  # O(entries)
            return anc  # O(1)
    if not walk:  # O(1)
        return None  # O(1)
    best = None  # O(1)
    for dirpath, dirs, _ in os.walk(root):  # O(d)
        rel = Path(dirpath).relative_to(root)  # O(depth)
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in SKIP and len(rel.parts) < MAX_DEPTH]  # O(dirs)
        posix = rel.as_posix()  # O(depth)
        if posix in skip or not _holds(dirpath, name):  # O(entries)
            continue  # O(1)
        key = (len(rel.parts), posix)  # O(depth)
        best = key if best is None or key < best else best  # O(1)
    return best[1] if best else None  # O(1)


def _ancestors(near):  # O(depth) | folders of a path, nearest first, never "."
    p = PurePosixPath(near).parent  # O(1)
    return [a.as_posix() for a in [p, *p.parents] if a.as_posix() != "."]  # O(depth)


def _top_names(path):  # O(file) | level-0 imported top names, or None when unreadable
    try:  # O(1)
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))  # O(file)
    except (OSError, SyntaxError, ValueError):  # O(1)
        return None  # O(1)
    out = set()  # O(1)
    for n in ast.walk(tree):  # O(nodes)
        if isinstance(n, ast.Import):  # O(1)
            out.update(a.name.split(".")[0] for a in n.names)  # O(names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:  # O(1)
            out.add(n.module.split(".")[0])  # O(1)
    return sorted(out - set(sys.stdlib_module_names))  # O(n log n)


def owned_hint(root, rel, roots, packages=frozenset()):  # O(d) | directory a task's own python file needs on the path
    root = Path(root)  # O(1)
    if not rel.endswith(".py") or any(rel == r or rel.startswith(r.rstrip("/") + "/") for r in roots):  # O(r)
        return None  # O(r)
    if (root / rel).is_file():  # O(1)
        names = _top_names(root / rel)  # O(file)
        if names is not None:  # O(1)
            return next((h for h in (hint(root, n, roots, rel, walk=False) for n in names) if h), None)  # O(names * depth)
    base = "src" if rel.startswith("src/") and (root / "src").is_dir() else "."  # O(1)
    pure = PurePosixPath(rel)  # O(1)
    below = pure.parts if base == "." else pure.parts[1:]  # O(depth)
    if not all(p.isidentifier() for p in below[:-1]) or not below[-1][:-3].isidentifier():  # O(depth)
        return None  # O(depth)

    def is_pkg(d):  # O(1)
        return (root / d / "__init__.py").exists() or (d + "/__init__.py") in packages  # O(1)

    folder = pure.parent  # O(1)
    b = folder  # O(1)
    while b.as_posix() != base and is_pkg(b.as_posix()):  # O(depth)
        b = b.parent  # O(1)
    if b != folder:  # O(1)
        return None if b.as_posix() == base else b.as_posix()  # O(1)
    if folder.as_posix() == base or folder.parent.as_posix() == base:  # O(1)
        return None  # O(1)
    return folder.parent.as_posix()  # O(1)
