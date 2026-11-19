#!/usr/bin/env python3
"""Which backlog issues another session already builds (#813): Jira status in the In Progress category, a worktree, or a local or origin branch that names the issue."""
import os
import re
import subprocess
from pathlib import Path

LIVE_ENV = "SUPERLITE_IN_PROGRESS_LIVE"  # O(1)
GIT_TIMEOUT = 30  # O(1)
PART_MAX = 80  # O(1)
STATUS_MAX = 40  # O(1)
ERR_MAX = 120  # O(1)
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-[1-9][0-9]*$")  # O(1)
CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")  # O(1)


def _names_key(key: str, name: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(key) + r"(?![0-9])", name, re.I) is not None  # O(len)


def _names_number(num: int, name: str) -> bool:
    last = name.rstrip("/").rsplit("/", 1)[-1]  # O(len)
    return re.match(r"(?:(?:issues?|gh)[-_]?)?" + str(num) + r"(?:$|[-_])", last, re.I) is not None  # O(len)


def _named(ref, name: str) -> bool:
    if isinstance(ref, int) and not isinstance(ref, bool):  # O(1)
        return _names_number(ref, name)  # O(len)
    return isinstance(ref, str) and _names_key(ref, name)  # O(len)


def match(ref, names: list) -> list:
    """The names that name the issue `ref` (a number or a Jira key), in input order; a worktree hit hides the hit of its own branch."""
    found: list = []  # O(1)
    for n in names:  # O(names)
        if n.get("kind") == "worktree":  # O(1)
            if _named(ref, os.path.basename(n["name"].rstrip("/"))) or _named(ref, n.get("branch") or ""):  # O(len)
                found.append(n)  # O(1)
        elif _named(ref, n["name"]):  # O(len)
            found.append(n)  # O(1)
    hidden = {n["branch"] for n in found if n.get("kind") == "worktree" and n.get("branch")}  # O(found)
    return [n for n in found if not (n.get("kind") == "branch" and n["name"] in hidden)]  # O(found)


def _git(root: Path, args: list, what: str) -> tuple[str, str | None]:
    try:  # O(1)
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=GIT_TIMEOUT, stdin=subprocess.DEVNULL)  # O(repo)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:  # O(1)
        return "", f"{what} failed: {e}"[:len(what) + 9 + ERR_MAX]  # O(1)
    if r.returncode:  # O(1)
        return "", f"{what} failed: {(r.stderr or '').strip()[:ERR_MAX]}"  # O(1)
    return r.stdout, None  # O(1)


def git_names(root: Path) -> tuple[list, str | None]:
    """(worktrees other than the main checkout, then local and origin branches; error text or None). Never raises."""
    out, err = _git(root, ["worktree", "list", "--porcelain"], "git worktree list")  # O(repo)
    if err:  # O(1)
        return [], err  # O(1)
    me = os.path.realpath(root)  # O(1)
    names: list = []  # O(1)
    for block in out.split("\n\n"):  # O(blocks)
        path, branch = None, ""  # O(1)
        for line in block.splitlines():  # O(lines)
            if line.startswith("worktree "):  # O(1)
                path = os.path.realpath(line[9:])  # O(1)
            elif line.startswith("branch refs/heads/"):  # O(1)
                branch = line[len("branch refs/heads/"):]  # O(1)
        if path and path != me:  # O(1)
            names.append({"kind": "worktree", "name": path, "branch": branch})  # O(1)
    out, err = _git(root, ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes/origin"], "git for-each-ref")  # O(refs)
    seen: set = set()  # O(1)
    for ref in out.splitlines():  # O(refs)
        name = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref[len("refs/remotes/origin/"):] if ref.startswith("refs/remotes/origin/") else ""  # O(len)
        if name and name != "HEAD" and name not in seen:  # O(1)
            seen.add(name)  # O(1)
            names.append({"kind": "branch", "name": name})  # O(1)
    return names, err  # O(1)


def jira_in_progress(keys: list) -> tuple[dict, str | None]:
    """({key: status name} for keys whose status category is In Progress, from one search; error text or None)."""
    if not keys:  # O(1)
        return {}, None  # O(1)
    import backlog  # O(1)
    jql = "key in (" + ", ".join(keys) + ') AND statusCategory = "In Progress"'  # O(keys)
    try:  # O(1)
        res = backlog._acli(["jira", "workitem", "search", "--jql", jql, "--fields", "key,status", "--paginate", "--json"])  # O(network)
    except RuntimeError as e:  # O(1)
        return {}, str(e)  # O(1)
    if not isinstance(res, list):  # O(1)
        return {}, "acli search gave no issue list"  # O(1)
    found: dict = {}  # O(1)
    for it in res:  # O(res)
        if not isinstance(it, dict) or it.get("key") not in keys:  # O(keys)
            continue  # O(1)
        f = it.get("fields") if isinstance(it.get("fields"), dict) else {}  # O(1)
        st = f.get("status") if isinstance(f.get("status"), dict) else {}  # O(1)
        found[it["key"]] = str(st.get("name") or "In Progress")[:STATUS_MAX]  # O(1)
    return found, None  # O(res)


def _clean(text: str) -> str:
    return " ".join(CTRL_RE.sub(" ", str(text)).split())[:PART_MAX]  # O(len)


def _part(h: dict) -> str:
    if h.get("kind") == "status":  # O(1)
        return "Jira status " + _clean(h["name"])  # O(len)
    if h.get("kind") == "worktree":  # O(1)
        return "worktree " + _clean(os.path.basename(h["name"].rstrip("/")))  # O(len)
    return "branch " + _clean(h["name"])  # O(len)


def label(hits: list) -> str:
    """A one-line, control-free description of the hits: the first two, then how many more."""
    out = "; ".join(_part(h) for h in hits[:2])  # O(1)
    return out + (f" (+{len(hits) - 2} more)" if len(hits) > 2 else "")  # O(1)


def hits(items: list, jira: bool, root: Path) -> tuple[dict, list]:
    """({number: [hit, ...]} for the items another session builds, [report lines for reads that failed]). Reads nothing when the gate is off or there are no items."""
    if os.environ.get(LIVE_ENV) == "0" or not items:  # O(1)
        return {}, []  # O(1)
    lines: list = []  # O(1)
    keys = [i["number"] for i in items if isinstance(i.get("number"), str) and KEY_RE.fullmatch(i["number"])]  # O(items)
    status: dict = {}  # O(1)
    if jira and keys:  # O(1)
        status, err = jira_in_progress(keys)  # O(network)
        if err:  # O(1)
            lines.append(f"in progress: Jira status not read ({err[:ERR_MAX]}); worktrees and branches still checked")  # O(1)
    names, err = git_names(root)  # O(repo)
    if err:  # O(1)
        lines.append(f"in progress: worktrees and branches not read ({err[:ERR_MAX]})")  # O(1)
    found: dict = {}  # O(1)
    for i in items:  # O(items * names)
        ref = i["number"]  # O(1)
        hit = ([{"kind": "status", "name": status[ref]}] if ref in status else []) + match(ref, names)  # O(names)
        if hit:  # O(1)
            found[ref] = hit  # O(1)
    return found, lines  # O(1)
