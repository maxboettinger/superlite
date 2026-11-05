#!/usr/bin/env python3
"""Account choice for fleet workers from `claude-profile usage --json` and `list --json`."""

# Complexity notation:
# a = accounts in the usage report, l = limits per account
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)

FIVE_HOUR_MAX = 90  # O(1) five_hour percent at or above this skips the account
WEEKLY_MAX = 100  # O(1) weekly percent at or above this skips the account


def _run(sub, env):  # O(1) plus subprocess time
    e = os.environ if env is None else env  # O(1)
    binary = e.get("SUPERLITE_CLAUDE_PROFILE_BIN") or "claude-profile"  # O(1)
    try:  # O(1)
        r = subprocess.run([binary, sub, "--json"], capture_output=True, text=True, timeout=40, check=False, env=dict(e))  # O(1)
        if r.returncode != 0:  # O(1)
            return {}  # O(1)
        data = json.loads(r.stdout)  # O(output)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):  # O(1)
        return {}  # O(1)
    return data if isinstance(data, dict) else {}  # O(1)


def read_usage(env=None):  # O(1) plus subprocess time
    return _run("usage", env)  # O(1)


def read_listing(env=None):  # O(1) plus subprocess time
    return _run("list", env)  # O(1)


def _pct(a, prefix):  # O(l)
    vals = [float(x.get("percent") or 0) for x in a.get("limits") or [] if str(x.get("kind", "")).startswith(prefix)]  # O(l)
    return max(vals) if vals else 0.0  # O(l)


def _skip(a):  # O(l)
    """Reason this account is unusable, or None."""
    if a.get("error"):  # O(1)
        return "error %s" % a["error"]  # O(1)
    five = _pct(a, "five_hour")  # O(l)
    if five >= FIVE_HOUR_MAX:  # O(1)
        return "five_hour %g%%" % five  # O(1)
    weekly = _pct(a, "weekly_all")  # O(l)
    if weekly >= WEEKLY_MAX:  # O(1)
        return "weekly_all %g%%" % weekly  # O(1)
    return None  # O(1)


def pick_account(usage, allowed):  # O(a*l)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    if not by:  # O(1)
        return allowed[0] if allowed else None  # O(1)
    best = None  # O(1)
    for name in allowed:  # O(a)
        a = by.get(name)  # O(1)
        if a is None or _skip(a):  # O(l)
            continue  # O(1)
        key = (_pct(a, "weekly_all"), a.get("n") if isinstance(a.get("n"), int) else 10 ** 9)  # O(l)
        if best is None or key < best[0]:  # O(1)
            best = (key, name)  # O(1)
    return best[1] if best else None  # O(1)


def reasons(usage, allowed):  # O(a*l)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    out = []  # O(1)
    for name in allowed:  # O(a)
        a = by.get(name)  # O(1)
        if a is None:  # O(1)
            out.append("%s: not in usage" % name)  # O(1)
            continue  # O(1)
        why = _skip(a)  # O(l)
        if why:  # O(1)
            out.append("%s: %s" % (name, why))  # O(1)
    return out  # O(1)


def is_path(entry):  # O(1)
    """True when an account entry is a config dir path (has a slash or starts with ~) rather than a claude-profile name."""
    return "/" in entry or entry.startswith("~")  # O(1)


def entry_name(entry):  # O(1)
    """Account name of an entry: the basename of a config dir path, else the entry itself."""
    return os.path.basename(entry.rstrip("/")) or entry if is_path(entry) else entry  # O(1)


def _default_dir(env):  # O(1)
    return os.path.join((os.environ if env is None else env).get("HOME") or os.path.expanduser("~"), ".claude")  # O(1)


def is_default_dir(path, env=None):  # O(1)
    """True for Claude Code's default config dir `~/.claude`.

    That dir is chosen by leaving CLAUDE_CONFIG_DIR unset: set to it, Claude Code looks for `.claude.json` inside it
    instead of in the home dir and starts first-run onboarding."""
    return os.path.normpath(os.path.expanduser(path)) == os.path.normpath(_default_dir(env))  # O(1)


def account_dir(listing, name, env=None):  # O(a)
    if is_path(name):  # O(1) a config dir path needs no listing
        return os.path.expanduser(name)  # O(1)
    if name == "current":  # O(1)
        return (os.environ if env is None else env).get("CLAUDE_CONFIG_DIR") or _default_dir(env)  # O(1)
    for a in (listing or {}).get("accounts") or []:  # O(a)
        if a.get("name") == name:  # O(1)
            return a.get("dir") or None  # `claude-profile list --json` schema 1 names the config dir `dir` | O(1)
    return None  # O(1)
