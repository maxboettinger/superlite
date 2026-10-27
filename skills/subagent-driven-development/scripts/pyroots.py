#!/usr/bin/env python3
"""Python import roots of a project beyond the repository root and `src/`.

Library: import_roots(root, plan=None) -> sorted repository-relative POSIX directories.
Order: `.superlite/test-cmd.json` key "pythonpath" (a list of strings) wins; else derived from the plan's
`**Produces:**` dotted names (`a.b.c(`): D is a root for `a.b.c` when D/a/b.py or D/a/b/__init__.py exists
(two parts: D/a.py or D/a/__init__.py). The root itself and `src/` are never returned. Stdlib only.
"""
# Complexity notation:
#   d = directories walked (depth <= 8), p = Produces names in the plan
import json  # O(1)
import os  # O(1)
import re  # O(1)
from pathlib import Path  # O(1)

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
        if any((Path(dirpath) / c).is_file() for c in cands):  # O(cands)
            found.add(rel.as_posix())  # O(depth)
    return found  # O(d)


def import_roots(root, plan=None):  # O(d * p) | sorted, deduped, repository-relative POSIX
    key = configured(root)  # O(file)
    if key is not None:  # O(1)
        return sorted(set(key))  # O(k log k)
    names = produced_names(root, plan)  # O(plan)
    return sorted(derive(root, names)) if names else []  # O(d * p)
