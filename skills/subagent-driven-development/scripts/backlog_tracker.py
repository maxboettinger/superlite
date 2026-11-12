#!/usr/bin/env python3
"""Batched tracker reads for backlog: which issues are still open (one GraphQL call per 100 numbers, one Jira search), and Jira issues read by key."""
import json
import re
import subprocess
from pathlib import Path

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")  # O(1)
CHUNK = 100  # O(1)


def _num(i) -> bool:
    return isinstance(i, int) and not isinstance(i, bool) and i > 0  # O(1)


def _gh_closed(repo: str, nums: list, root: Path) -> set:
    """Numbers GitHub reports CLOSED or MERGED; a failed or unreadable call reports none."""
    owner, name = repo.split("/")  # O(1)
    closed: set = set()  # O(1)
    for k in range(0, len(nums), CHUNK):  # O(n / 100 * network)
        part = nums[k:k + CHUNK]  # O(100)
        body = " ".join(f"i{n}:issue(number:{n}){{state}}" for n in part)  # O(100)
        q = f'query{{repository(owner:"{owner}",name:"{name}"){{{body}}}}}'  # O(100)
        try:  # O(1)
            r = subprocess.run(["gh", "api", "graphql", "-f", "query=" + q], capture_output=True, text=True, timeout=60, cwd=root)  # O(network)
            repo_d = json.loads(r.stdout)["data"]["repository"]  # O(size)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):  # O(1)
            continue  # O(1)
        if not isinstance(repo_d, dict):  # O(1)
            continue  # O(1)
        for n in part:  # O(100)
            a = repo_d.get(f"i{n}")  # O(1)
            if isinstance(a, dict) and a.get("state") in ("CLOSED", "MERGED"):  # O(1)
                closed.add(n)  # O(1)
    return closed  # O(n)


def _jira_done(keys: list) -> set:
    """Keys whose status category is done, from one search; a failed search reports none."""
    import backlog  # O(1)
    jql = "key in (" + ", ".join(keys) + ") AND statusCategory = Done"  # O(keys)
    try:  # O(1)
        res = backlog._acli(["jira", "workitem", "search", "--jql", jql, "--fields", "key", "--paginate", "--json"])  # O(network)
    except RuntimeError:  # O(1)
        return set()  # O(1)
    if not isinstance(res, list):  # O(1)
        return set()  # O(1)
    return {it["key"] for it in res if isinstance(it, dict) and it.get("key") in keys}  # O(res)


def open_now(repo: str, issues: list, root: Path) -> list:
    """The issues still open, in input order. Anything unreadable, malformed or unknown stays in the list."""
    import backlog  # O(1)
    nums = [i for i in issues if _num(i)]  # O(n)
    keys = [i for i in issues if isinstance(i, str) and backlog.KEY_RE.fullmatch(i)]  # O(n)
    closed = _gh_closed(repo, nums, root) if nums and isinstance(repo, str) and REPO_RE.fullmatch(repo) else set()  # O(n * network)
    done = _jira_done(keys) if keys else set()  # O(network)
    return [i for i in issues if not ((_num(i) and i in closed) or (isinstance(i, str) and i in done))]  # O(n)


def jira_by_key(keys: list) -> tuple[list[dict], list[str]]:
    """(issues read, keys not read) for Jira keys, each through `acli jira workitem view`; a failed or mismatching view leaves the key unread."""
    import backlog  # O(1)
    found: list = []  # O(1)
    unread: list = []  # O(1)
    for k in keys:  # O(keys * network)
        item = None  # O(1)
        if isinstance(k, str) and backlog.KEY_RE.fullmatch(k):  # O(1)
            try:  # O(1)
                res = backlog._acli(["jira", "workitem", "view", k, "--fields", "key,summary,description", "--json"])  # O(network)
            except RuntimeError:  # O(1)
                res = None  # O(1)
            for c in res if isinstance(res, list) else [res]:  # O(res)
                if isinstance(c, dict) and (c.get("key") == k or ("key" not in c and isinstance(c.get("fields"), dict))):  # O(1)
                    item = c  # O(1)
                    break  # O(1)
        if item is None:  # O(1)
            unread.append(k)  # O(1)
            continue  # O(1)
        f = item.get("fields") if isinstance(item.get("fields"), dict) else {}  # O(1)
        found.append({"number": k, "title": str(f.get("summary") or ""), "body": backlog._body(backlog.adf_text(f.get("description")))})  # O(body)
    return found, unread  # O(keys)
