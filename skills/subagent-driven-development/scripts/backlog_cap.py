#!/usr/bin/env python3
"""Lead cap of `sl backlog start` without `--cap` (#748).

The cap is the minimum of: the room the machine's room command reports (room // lead_units per lead), leads_per_repo,
leads_per_machine (live herdr leads) and an account gate (no usable account: no new lead). One `cap:` line names the
limit that decided it. The keys live in <home>/machine.json; no room command means the fixed cap 2."""

# Complexity notation:
# b = batches, a = accounts, l = limits per account, k = keys of machine.json, g = herdr agents
import json  # O(1)
import os  # O(1)
import re  # O(1)
import subprocess  # O(1)
from pathlib import Path  # O(1)

import accounts as ac  # O(1)
import fleet_state  # O(1)
import herdr_client  # O(1)
import history  # O(1)

DEFAULTS = {"lead_units": 2, "leads_per_repo": 6, "leads_per_machine": 12, "lead_weekly_max": None}  # O(1)
FIXED_CAP = 2  # O(1) cap without a room command
ROOM_TIMEOUT = 20  # O(1) seconds the room command may run
ACTIVE = ("running", "needs_decision")  # O(1) as backlog_state.ACTIVE


def _text(s, n):  # O(len s)
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(s))[:n]  # O(len s)


def _pos_int(v):  # O(1)
    return isinstance(v, int) and not isinstance(v, bool) and v > 0  # O(1)


def _pct_ok(v):  # O(1)
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 100  # O(1)


def _read_json(home):  # O(k): (object, why) of <home>/machine.json; why "" when read, "missing" when absent
    try:  # O(1)
        data = json.loads((Path(home) / "machine.json").read_text(encoding="utf-8"))  # O(k)
    except FileNotFoundError:  # O(1)
        return None, "missing"  # O(1)
    except (OSError, ValueError, RecursionError):  # O(1)
        return None, "machine.json unreadable"  # O(1)
    return (data, "") if isinstance(data, dict) else (None, "machine.json unreadable")  # O(1)


def machine_cfg(home):  # O(k)
    """The limits of machine.json with defaults; keys present but invalid are listed in cfg["_invalid"] as notes."""
    cfg, bad = dict(DEFAULTS), []  # O(1)
    data, _ = _read_json(home)  # O(k)
    for key, default in DEFAULTS.items():  # O(1)
        if not data or key not in data:  # O(1)
            continue  # O(1)
        v = data[key]  # O(1)
        if (_pct_ok(v) if key == "lead_weekly_max" else _pos_int(v)):  # O(1)
            cfg[key] = v  # O(1)
        else:  # O(1)
            bad.append("machine.json %s invalid, default %s" % (key, "none" if default is None else default))  # O(1)
    if bad:  # O(1)
        cfg["_invalid"] = bad  # O(1)
    return cfg  # O(1)


def read_room(home, timeout=None):  # O(1) plus the room command
    """(room, why): room is {"room": int, "unit": str[, "reason": str]} from the room command, else None and the why text."""
    timeout = ROOM_TIMEOUT if timeout is None else timeout  # O(1)
    data, why = _read_json(home)  # O(k)
    if data is None:  # O(1)
        return None, "machine.json names no room command" if why == "missing" else why  # O(1)
    if "room" not in data:  # O(1)
        return None, "machine.json names no room command"  # O(1)
    argv = data["room"]  # O(1)
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):  # O(len argv)
        return None, "machine.json room is not an argv list"  # O(1)
    try:  # O(1)
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, check=False)  # O(1)
    except subprocess.TimeoutExpired:  # O(1)
        return None, "room command timed out after %g s" % timeout  # O(1)
    except (OSError, ValueError) as e:  # O(1)
        return None, "room command did not run: %s" % e  # O(1)
    if r.returncode != 0:  # O(1)
        return None, "room command exited %s" % r.returncode  # O(1)
    try:  # O(1)
        out = json.loads(r.stdout)  # O(output)
    except (ValueError, RecursionError):  # O(1)
        out = None  # O(1)
    if not isinstance(out, dict):  # O(1)
        return None, "room command printed no JSON object"  # O(1)
    n, unit = out.get("room"), out.get("unit")  # O(1)
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:  # O(1)
        return None, "room output: room must be an integer >= 0"  # O(1)
    if not isinstance(unit, str) or not unit:  # O(1)
        return None, "room output: unit must be a text"  # O(1)
    room = {"room": n, "unit": _text(unit, 40)}  # O(1)
    if isinstance(out.get("reason"), str) and out["reason"]:  # O(1)
        room["reason"] = _text(out["reason"], 80)  # O(1)
    return room, ""  # O(1)


def account_state(root, tier, weekly_max, env=None):  # O(a*l) plus the usage command
    """("ok", []), ("unknown", []) (no usage data) or ("none", reasons) when no account of the run is usable.

    Mirrors fleet.choose_account: the run's fleet.json accounts, else every usage account; `current` or a path entry the
    usage report does not know counts as usable. `weekly_max` adds the lead_weekly_max gate on weekly_all."""
    usage = ac.read_usage(env)  # O(1) plus subprocess time
    if not usage.get("accounts"):  # O(1)
        return "unknown", []  # O(1)
    listing = ac.read_listing(env)  # O(1) plus subprocess time
    entries = fleet_state.load(Path(root) / ".superlite").get("accounts") or [a.get("name") for a in usage["accounts"]]  # O(a)
    allowed = [ac.entry_name(e) for e in entries]  # O(a)
    alias = ac.aliases(listing, entries, env)  # O(a*e)
    by = {a.get("name"): a for a in usage["accounts"]}  # O(a)
    bad = []  # O(1)
    for e, name in zip(entries, allowed):  # O(a)
        a = by.get(alias.get(name, name))  # O(1)
        if a is None:  # O(1)
            if (ac.is_path(e) or e == "current") and name not in alias:  # no usage data for it, not a verdict | O(1)
                return "ok", []  # O(1)
            bad.append("%s: not in usage" % name)  # O(1)
            continue  # O(1)
        why = ac._skip(a, tier)  # O(l)
        if not why and weekly_max is not None and ac._pct(a, "weekly_all") >= weekly_max:  # O(l)
            why = "weekly_all %g%% >= lead_weekly_max %g%%" % (ac._pct(a, "weekly_all"), weekly_max)  # O(l)
        if not why:  # O(1)
            return "ok", []  # O(1)
        bad.append("%s: %s" % (name, why))  # O(1)
    return "none", bad  # O(1)


def live_leads():  # O(g)
    """Count of live herdr agents named sl-*-lead, or None when herdr cannot be asked."""
    try:  # O(1)
        return sum(1 for x in herdr_client.agents() if re.fullmatch(r"sl-.*-lead", str(x.get("name"))))  # O(g)
    except herdr_client.HerdrError:  # O(1)
        return None  # O(1)


def decide(active, room, room_why, cfg, live, accounts, held):  # O(1)
    """(cap, line) from the readings; pure. Each limit is a total lead count, as `--cap`."""
    limits = []  # (name, cap, part) in tie order: accounts, room, repo, machine | O(1)
    state, why = accounts  # O(1)
    acc_part = "accounts ok"  # O(1)
    if state == "none":  # O(1)
        shown = ", ".join(why[:3]) + (" (+%d more)" % (len(why) - 3) if len(why) > 3 else "")  # O(1)
        limits.append(("accounts", active, "no account usable: " + shown))  # O(1)
    elif state == "unknown":  # O(1)
        acc_part = "accounts unknown (no usage data)"  # O(1)
    units = cfg["lead_units"]  # O(1)
    if room is not None:  # O(1)
        part = "room %d %s" % (room["room"], room["unit"])  # O(1)
        part += ": " + room["reason"] if room["room"] == 0 and room.get("reason") else ", %d per lead" % units  # O(1)
        limits.append(("room", active + room["room"] // units, part))  # O(1)
    else:  # O(1)
        limits.append(("room", FIXED_CAP, "fixed cap %d: %s" % (FIXED_CAP, room_why)))  # O(1)
    limits.append(("repo", cfg["leads_per_repo"], "%d per repository" % cfg["leads_per_repo"]))  # O(1)
    if live is not None:  # O(1)
        limits.append(("machine", active + max(0, cfg["leads_per_machine"] - live), "%d of %d leads on the machine" % (live, cfg["leads_per_machine"])))  # O(1)
    cap = max(0, min(c for _, c, _ in limits))  # O(1)
    name, _, first = next(x for x in limits if max(0, x[1]) == cap)  # O(1)
    parts = [first]  # O(1)
    room_part = next(p for n, _, p in limits if n == "room")  # O(1)
    if name != "room":  # O(1)
        parts.append(room_part)  # O(1)
    if name != "accounts":  # O(1)
        parts.append(acc_part)  # O(1)
    if held > 0:  # O(1)
        parts.append("%d held by overlap" % held)  # O(1)
    parts += cfg.get("_invalid", [])  # O(1)
    return cap, "cap: %d (%s)" % (cap, "; ".join(parts))  # O(1)


def lead_cap(data, root, held=0, tier=None, env=None):  # O(b + a*l) plus the room, usage and herdr calls
    """Gather the readings (home = history.home()) and decide."""
    home = history.home()  # O(1)
    cfg = machine_cfg(home)  # O(k)
    room, room_why = read_room(home)  # O(1) plus the room command
    active = sum(1 for b in data.get("batches", []) if b.get("state") in ACTIVE)  # O(b)
    live = os.environ.get("SUPERLITE_LEAD_CAP_LIVE") != "0"  # O(1)
    accounts = account_state(root, tier, cfg["lead_weekly_max"], env) if live else ("unknown", [])  # O(a*l)
    return decide(active, room, room_why, cfg, live_leads() if live else None, accounts, held)  # O(1)
