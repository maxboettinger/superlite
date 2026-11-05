#!/usr/bin/env python3
"""The run's fleet state, `<run>/.superlite/fleet.json`: on/off, accounts, workspace and workers."""

# Complexity notation:
# w = workers in the fleet
import contextlib  # O(1)
import fcntl  # O(1)
import json  # O(1)
import os  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)


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


def add_worker(sd, wid, pane_id, account, agent, tier):  # O(w)
    with locked(sd):  # O(1)
        data = load(sd)  # O(w)
        w = {"pane_id": pane_id, "account": account, "agent": agent, "tier": tier, "state": "starting", "task": None}  # O(1)
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
