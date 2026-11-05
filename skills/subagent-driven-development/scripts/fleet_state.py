#!/usr/bin/env python3
"""The run's fleet state, `<run>/.superlite/fleet.json`: on/off, accounts, workspace and workers."""

# Complexity notation:
# w = workers in the fleet, p = panes of a tab, a = agents herdr lists
import contextlib  # O(1)
import fcntl  # O(1)
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

import history  # O(1)

MAX_PANES = 4  # O(1) a tab holds at most this many worker panes
MIN_ROWS = 20  # O(1) a pane never splits down below this many rows


def default():  # O(1)
    return {"on": False, "workers": {}, "next": 1, "accounts": [], "workspace_id": None, "root_pane": None, "label": ""}  # O(1)


def path(sd):  # O(1)
    return Path(sd) / "fleet.json"  # O(1)


def load(sd):  # O(w)
    p = path(sd)  # O(1)
    if not p.exists():  # O(1)
        return default()  # O(1)
    try:  # O(1)
        data = json.loads(p.read_text(encoding="utf-8"))  # O(w)
    except (OSError, json.JSONDecodeError):  # O(1)
        return default()  # O(1)
    return {**default(), **data} if isinstance(data, dict) else default()  # O(w)


@contextlib.contextmanager  # O(1)
def locked(sd):  # O(1) plus wait for the lock
    p = path(sd)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    with open(p.with_name(p.name + ".lock"), "a") as lf:  # O(1)
        fcntl.flock(lf, fcntl.LOCK_EX)  # O(1) blocks until free
        yield  # O(1)


def save(sd, data):  # O(w), atomic
    p = path(sd)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")  # O(1) unique temp file
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:  # O(1)
            fh.write(json.dumps(data, indent=2) + "\n")  # O(w)
        os.replace(tmp, p)  # O(1) atomic rename
    except BaseException:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


def is_on(sd):  # O(w)
    return bool(load(sd).get("on"))  # O(w)


def set_on(sd, label, accounts):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        data.update({"on": True, "label": label, "accounts": list(accounts)})  # O(a)
        save(sd, data)  # O(w)
        return data  # O(1)


def set_off(sd):  # O(1)
    with locked(sd):  # O(1)
        path(sd).unlink(missing_ok=True)  # O(1)


def next_id(sd):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        n = int(data.get("next") or 1)  # O(1)
        data["next"] = n + 1  # O(1)
        save(sd, data)  # O(w)
        return "W%d" % n  # O(1)


def agent_name(sd, wid):  # O(len of the run folder name)
    """Herdr agent name of a worker: `sl-<run folder>-<hash>-<worker id>`, within herdr's `[a-z][a-z0-9_-]{0,31}`.

    Herdr keeps names unique among the live agents of a server. `<hash>` is the first 4 hex digits of the sha1 of the
    run root's absolute path: it keeps equal folder names and long shared prefixes (worktrees `...-phase-2`, `...-phase-3`) apart.
    The folder name is cut so that `-<hash>-<worker id>` always fits."""
    h = hashlib.sha1(str(Path(sd).resolve().parent).encode()).hexdigest()[:4]  # O(len path)
    tail = "-%s-%s" % (h, wid.lower())  # O(1)
    run = re.sub(r"[^a-z0-9_-]+", "-", Path(sd).resolve().parent.name.lower()).strip("-_")  # O(len)
    return ("sl-" + run)[:32 - len(tail)].rstrip("-_") + tail  # O(1)


def name_of(sd, wid, w):  # O(1)
    """Herdr agent name of the worker record `w`; a record written by 1.5.0 has none stored."""
    return w.get("name") or agent_name(sd, wid)  # O(1)


def worker_name(sd, wid):  # O(w)
    """Herdr agent name of a worker; KeyError for an unknown worker."""
    return name_of(sd, wid, load(sd)["workers"][wid])  # O(w)


def add_worker(sd, wid, pane_id, account, agent, tier):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        w = {"name": agent_name(sd, wid), "pane_id": pane_id, "account": account, "agent": agent, "tier": tier, "state": "starting", "task": None}  # O(1)
        data["workers"][wid] = w  # O(1)
        save(sd, data)  # O(w)
        return w  # O(1)


def set_state(sd, wid, state, task=None):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        if wid not in data["workers"]:  # O(1)
            raise KeyError(wid)  # O(1)
        w = data["workers"][wid]  # O(1)
        w["state"] = state  # O(1)
        w["task"] = task  # O(1)
        save(sd, data)  # O(w)
        return w  # O(1)


def set_workspace(sd, workspace_id, root_pane):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        data.update({"workspace_id": workspace_id, "root_pane": root_pane})  # O(1)
        save(sd, data)  # O(w)
        return data  # O(1)


def workers(sd, state=None):  # O(w)
    ws = load(sd)["workers"]  # O(w)
    return {k: v for k, v in ws.items() if state is None or v.get("state") == state}  # O(w)


def place(panes, max_panes=MAX_PANES, min_rows=MIN_ROWS):  # O(p)
    """Where the next worker pane goes: (direction, pane to split), or ("tab", None) for a new tab.

    One pane splits right; otherwise the tallest pane (the first on a tie) splits down while both halves keep `min_rows`."""
    if not panes or len(panes) >= max_panes:  # O(1)
        return "tab", None  # O(1)
    if len(panes) == 1:  # O(1)
        return "right", panes[0]["pane_id"]  # O(1)
    tallest = max(panes, key=lambda x: x["rows"])  # max returns the first of equal rows | O(p)
    if tallest["rows"] // 2 >= min_rows:  # O(1)
        return "down", tallest["pane_id"]  # O(1)
    return "tab", None  # O(1)


def _registry():  # O(1)
    return history.home() / "fleet" / "agents"  # O(1)


def register_agent(name, account):  # O(1), atomic; overwritten on reuse, never deleted
    """Record which account a worker agent runs on, where every superlite session on the machine can read it."""
    d = _registry()  # O(1)
    d.mkdir(parents=True, exist_ok=True)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=name + ".", suffix=".tmp")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:  # O(1)
            fh.write(account + "\n")  # O(1)
        os.replace(tmp, d / name)  # O(1) atomic rename
    except BaseException:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


def live_by_account(agents, own):  # O(a)
    """Live fleet workers per account over every session: account -> count.

    Counts the agents herdr lists whose name starts with `sl-`, is not in `own` and has a registered account other than `current`."""
    out = {}  # O(1)
    for a in agents:  # O(a)
        name = a.get("name") or ""  # O(1)
        if not name.startswith("sl-") or name in own:  # O(1)
            continue  # O(1)
        try:  # O(1)
            account = (_registry() / name).read_text(encoding="utf-8").strip()  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
        if account and account != "current":  # O(1)
            out[account] = out.get(account, 0) + 1  # O(1)
    return out  # O(1)
