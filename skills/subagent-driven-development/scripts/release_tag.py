"""Patch tag at ship: version level and annotated tag (T2)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

VER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _run(cmd: list, cwd=None, timeout=None) -> tuple[int, str]:  # O(output)
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(env)
    try:  # O(1)
        r = subprocess.run(cmd, cwd=None if cwd is None else str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)  # O(output)
    except (OSError, subprocess.TimeoutExpired) as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout or "") + (r.stderr or "")  # O(output)


def level(cur: str, new: str) -> str:  # O(1)
    """Return patch, minor, major, none (equal) or invalid for a version step."""
    a, b = VER.match(str(cur)), VER.match(str(new))  # O(1)
    if not a or not b:  # O(1)
        return "invalid"  # O(1)
    x, y = tuple(map(int, a.groups())), tuple(map(int, b.groups()))  # O(1)
    if x == y:  # O(1)
        return "none"  # O(1)
    if y < x:  # O(1)
        return "invalid"  # O(1)
    return "major" if y[0] > x[0] else "minor" if y[1] > x[1] else "patch"  # O(1)


def _last(out: str) -> str:  # O(output)
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]  # O(output)
    return lines[-1].strip() if lines else "no output"  # O(1)


def tag(root: Path, version: str, sha: str, push: bool = True) -> str:  # O(1)
    """Create and optionally push the annotated tag v<version>; returns one status line, never raises."""
    t = f"v{version}"  # O(1)
    try:  # O(1)
        if push:  # O(1)
            rc, out = _run(["git", "fetch", "origin"], cwd=root)  # O(network)
            if rc != 0:  # O(1)
                return f"tag {t} failed: {_last(out)}"  # O(1)
        rc, out = _run(["git", "tag", "-a", t, "-m", f"Version {version}", sha], cwd=root)  # O(1)
        if rc != 0:  # O(1)
            if _run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{t}"], cwd=root)[0] == 0:  # O(1)
                return f"tag {t} exists"  # O(1)
            return f"tag {t} failed: {_last(out)}"  # O(1)
        if not push:  # O(1)
            return f"tag {t} created"  # O(1)
        rc, out = _run(["git", "push", "origin", f"refs/tags/{t}"], cwd=root)  # O(network)
        return f"tag {t} pushed" if rc == 0 else f"tag {t} failed: {_last(out)}"  # O(1)
    except Exception as e:  # O(1)  never raises: the merge has already happened
        return f"tag {t} failed: {e}"  # O(1)
