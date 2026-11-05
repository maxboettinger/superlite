#!/usr/bin/env python3
"""Account choice for fleet workers from `claude-profile usage --json` and `list --json`."""

# Complexity notation:
# a = accounts in the usage report, l = limits per account
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)

FIVE_HOUR_MAX = 90  # O(1) 5-hour (`session`) percent at or above this skips the account
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


def _limits(a, match):  # O(l)
    return [x for x in a.get("limits") or [] if match(str(x.get("kind", "")))]  # O(l)


def _pct(a, prefix):  # O(l)
    vals = [float(x.get("percent") or 0) for x in _limits(a, lambda k: k.startswith(prefix))]  # O(l)
    return max(vals) if vals else 0.0  # O(l)


def _five(a):  # O(l)
    """5-hour window percent: kind `session`, and the older `five_hour*` kinds."""
    vals = [float(x.get("percent") or 0) for x in _limits(a, lambda k: k == "session" or k.startswith("five_hour"))]  # O(l)
    return max(vals) if vals else 0.0  # O(l)


def _scoped(a, tier):  # O(l)
    """First `weekly_scoped` limit that names the worker's tier model and is at its cap (100 when the cap is null), as (label, percent), or None."""
    if not tier:  # O(1) a scoped limit belongs to a model; without one it blocks nothing
        return None  # O(1)
    for x in _limits(a, lambda k: k == "weekly_scoped"):  # O(l)
        label, pct = str(x.get("label") or ""), float(x.get("percent") or 0)  # O(1)
        cap = x.get("cap_percent")  # O(1)
        cap = float(cap) if isinstance(cap, (int, float)) and not isinstance(cap, bool) else 100.0  # O(1)
        if tier.lower() in label.lower() and pct >= cap:  # O(1)
            return label, pct  # O(1)
    return None  # O(1)


def _skip(a, tier=None):  # O(l)
    """Reason this account is unusable, or None."""
    if a.get("error"):  # O(1)
        return "error %s" % a["error"]  # O(1)
    five = _five(a)  # O(l)
    if five >= FIVE_HOUR_MAX:  # O(1)
        return "5-hour %g%%" % five  # O(1)
    weekly = _pct(a, "weekly_all")  # O(l)
    if weekly >= WEEKLY_MAX:  # O(1)
        return "weekly_all %g%%" % weekly  # O(1)
    hit = _scoped(a, tier)  # O(l)
    if hit:  # O(1)
        return "weekly_scoped %s %g%%" % hit  # O(1)
    return None  # O(1)


def pick_account(usage, allowed, running=None, tier=None):  # O(a*l)
    """Best usable account of `allowed`: fewest live workers (`running`: account -> count), then lowest weekly_all, then lowest n."""
    running = running or {}  # O(1)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    if not by:  # no usage data: spread by worker count alone, the first entry wins a tie | O(a)
        return min(allowed, key=lambda n: running.get(n, 0)) if allowed else None  # O(a)
    best = None  # O(1)
    for name in allowed:  # O(a)
        a = by.get(name)  # O(1)
        if a is None or _skip(a, tier):  # O(l)
            continue  # O(1)
        key = (running.get(name, 0), _pct(a, "weekly_all"), a.get("n") if isinstance(a.get("n"), int) else 10 ** 9)  # O(l)
        if best is None or key < best[0]:  # O(1)
            best = (key, name)  # O(1)
    return best[1] if best else None  # O(1)


def reasons(usage, allowed, tier=None):  # O(a*l)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    out = []  # O(1)
    for name in allowed:  # O(a)
        a = by.get(name)  # O(1)
        if a is None:  # O(1)
            out.append("%s: not in usage" % name)  # O(1)
            continue  # O(1)
        why = _skip(a, tier)  # O(l)
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
