#!/usr/bin/env python3
"""Account choice for fleet workers from `claude-profile usage --json` and `list --json`.

CLI: `sl accounts [--tier MODEL]` prints one headroom line per account of `claude-profile usage --json`."""

# Complexity notation:
# a = accounts in the usage report, l = limits per account, e = entries of the allowed list
import argparse  # O(1)
import fcntl  # O(1)
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
from datetime import datetime  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from history import home  # $SUPERLITE_HOME | O(1)

FIVE_HOUR_MAX = 90  # O(1) 5-hour (`session`) percent at or above this skips the account
WEEKLY_MAX = 100  # O(1) weekly percent at or above this skips the account


def _run(sub, env):  # O(1) plus subprocess time
    e = os.environ if env is None else env  # O(1)
    binary = e.get("SUPERLITE_CLAUDE_PROFILE_BIN") or "claude-profile"  # O(1)
    try:  # O(1)
        r = subprocess.run([binary, sub, "--json"], capture_output=True, text=True, timeout=40, check=False, env=dict(e))  # O(1)
        data = json.loads(r.stdout)  # a failed run (one account errored) still prints a valid report | O(output)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):  # O(1)
        return {}  # O(1)
    return data if isinstance(data, dict) else {}  # O(1)


SIGN_IN_MARKS = ("Select login method:", "Paste code here if prompted", "Browser didn't open? Use the url below to sign in", "Opening browser to sign in")  # O(1) Claude Code sign-in screen lines
_TUI = " \t\u23fa\u25cf\u2022\u25e6\u00b7\u25aa\u2502\u2503\u256d\u256e\u2570\u256f\u2500\u2501\u276f>"  # O(1) the characters fleet._is_ready strips, plus the prompt arrows


def sign_in_screen(screen):  # True when a screen line starts with a sign-in mark; a line quoting one mid-text does not | O(s)
    return any(line.strip(_TUI).startswith(SIGN_IN_MARKS) for line in (screen or "").splitlines())  # O(s)


def read_usage(env=None):  # O(a*l) plus subprocess time
    """`claude-profile usage --json`, where an account whose reading failed is unknown rather than out of headroom (#917)."""
    return with_fallback(_run("usage", env), env)  # O(a*l)


def _store():  # O(1)
    return home() / "usage-last.json"  # O(1)


def _at(a, now):  # epoch seconds of a reading: its ISO `fetched_at`, else now | O(1)
    try:  # O(1)
        return datetime.fromisoformat(str(a.get("fetched_at"))).timestamp()  # O(1)
    except (TypeError, ValueError):  # O(1)
        return now  # O(1)


def _remember(report, now):  # O(a) keep each account's last good reading in <home>/usage-last.json
    good = {a["name"]: a for a in report.get("accounts") or [] if isinstance(a, dict) and a.get("name") and not a.get("error") and a.get("limits")}  # O(a)
    if not good:  # O(1)
        return  # O(1)
    store = _store()  # O(1)
    try:  # O(1)
        store.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        with open(store.with_name(store.name + ".lock"), "a") as lf:  # every session on the machine shares the store | O(1)
            fcntl.flock(lf, fcntl.LOCK_EX)  # O(1) blocks until free; read, merge and replace as one step
            try:  # O(1)
                last = json.loads(store.read_text())  # O(file)
            except (OSError, ValueError):  # O(1)
                last = {}  # O(1)
            last = last if isinstance(last, dict) else {}  # O(1)
            for name, a in good.items():  # O(a)
                last[name] = {"at": _at(a, now), "account": {k: a[k] for k in ("name", "n", "limits") if k in a}}  # no email or plan on disk | O(1)
            fd, tmp = tempfile.mkstemp(dir=str(store.parent), prefix=store.name + ".", suffix=".tmp")  # O(1) unique temp file
            try:  # O(1)
                with os.fdopen(fd, "w") as fh:  # O(1)
                    fh.write(json.dumps(last))  # O(a*l)
                os.replace(tmp, store)  # O(1) atomic rename
            except OSError:  # O(1)
                Path(tmp).unlink(missing_ok=True)  # O(1)
                raise  # O(1)
    except OSError:  # a store that cannot be written only loses the fallback | O(1)
        pass  # O(1)


def age_text(seconds):  # "10 min" below two hours, else whole hours | O(1)
    return "%d min" % (seconds // 60) if seconds < 7200 else "%d h" % (seconds // 3600)  # O(1)


def _live(limits, now):  # the limits whose window has not reset yet; an unparsable or missing `resets_at` keeps the limit | O(l)
    out = []  # O(1)
    for x in limits or []:  # O(l)
        try:  # O(1)
            gone = datetime.fromisoformat(str(x.get("resets_at")).replace("Z", "+00:00")).timestamp() <= now  # O(1)
        except (TypeError, ValueError, AttributeError, OSError, OverflowError):  # O(1)
            gone = False  # O(1)
        if not gone:  # O(1)
            out.append(x)  # O(1)
    return out  # O(l)


def _stored(prev, now):  # a stored entry as a usage account (`stale_s` set, expired limits dropped), with its age; None when unusable | O(l)
    if not isinstance(prev, dict) or not isinstance(prev.get("account"), dict) or not isinstance(prev.get("at"), (int, float)):  # O(1)
        return None  # O(1)
    age = max(0, now - prev["at"])  # O(1)
    a = prev["account"]  # O(1)
    return {**a, "limits": _live(a.get("limits"), now), "error": None, "stale_s": int(age)}, age  # O(l)


def _load():  # O(file)
    try:  # O(1)
        last = json.loads(_store().read_text())  # O(file)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return last if isinstance(last, dict) else {}  # O(1)


def with_fallback(report, env=None, now=None):  # O(a*l) plus one `list` call when an account has no recent reading
    """The usage report with each failed reading replaced, one stderr line per replacement (#917).

    A failed account takes its last good reading, whatever its age, minus limits that have reset (`stale_s` set). A report
    that is no usable dict is rebuilt from the whole store. Else the account the
    coordinator's own session runs on (its CLAUDE_CONFIG_DIR, `current`) counts as usable without limits (`unknown` set),
    unless `claude-profile list` says it is signed out; `pick_account` ranks it after every account with a reading.
    Any other failed account keeps its error."""
    now = time.time() if now is None else now  # O(1)
    if not isinstance(report, dict) or not isinstance(report.get("accounts"), list):  # O(1)
        rebuilt = [(n, _stored(v, now)) for n, v in sorted(_load().items())]  # O(a*l)
        rebuilt = [(n, r) for n, r in rebuilt if r]  # O(a)
        if not rebuilt:  # O(1)
            return report if isinstance(report, dict) else {}  # O(1)
        print("usage: claude-profile usage gave no report; using last readings: %s" % ", ".join("%s %s old" % (n, age_text(r[1])) for n, r in rebuilt), file=sys.stderr)  # O(a)
        return {"accounts": [r[0] for _, r in rebuilt]}  # O(a)
    _remember(report, now)  # O(a)
    failed = lambda a: isinstance(a, dict) and a.get("error") and a.get("name")  # O(1)
    if not any(failed(a) for a in report["accounts"]):  # O(a)
        return report  # O(1)
    last = _load()  # O(file)
    own, listing = None, None  # O(1)
    out = []  # O(1)
    for a in report["accounts"]:  # O(a)
        if not failed(a):  # O(1)
            out.append(a)  # O(1)
            continue  # O(1)
        name, err = a["name"], a["error"]  # O(1)
        got = _stored(last.get(name), now)  # O(l)
        if got:  # O(1)
            out.append(got[0])  # O(1)
            print("%s: usage unreadable (%s); using its reading from %s ago" % (name, err, age_text(got[1])), file=sys.stderr)  # O(1)
            continue  # O(1)
        if listing is None:  # O(1) one listing call for the whole report
            listing = read_listing(env)  # O(1) plus subprocess time
            own = aliases(listing, ["current"], env).get("current")  # O(a)
        entry = next((x for x in listing.get("accounts") or [] if x.get("name") == name), {})  # O(a)
        if name == own and entry.get("signed_in") is not False:  # O(1)
            out.append({**a, "error": None, "limits": [], "unknown": True})  # O(1)
            print("%s: usage unreadable (%s), no stored reading; usable as the coordinator's own account" % (name, err), file=sys.stderr)  # O(1)
            continue  # O(1)
        out.append(a)  # O(1)
    return {**report, "accounts": out}  # O(a)


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
    if a.get("error"):  # O(1) a failed reading, not a full account (#917)
        return "usage unreadable: %s" % a["error"]  # O(1)
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


def pick_account(usage, allowed, running=None, tier=None, alias=None):  # O(a*l)
    """Best usable account of `allowed`: one with a reading before an `unknown` one (#917), then fewest live workers
    (`running`: account -> count), then lowest weekly_all, then lowest n.

    `alias` maps an entry that is not a claude-profile name (`current`, a config dir basename) to the account name it uses."""
    running = running or {}  # O(1)
    alias = alias or {}  # O(1)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    if not by:  # no usage data: spread by worker count alone, the first entry wins a tie | O(a)
        return min(allowed, key=lambda n: running.get(n, 0)) if allowed else None  # O(a)
    best = None  # O(1)
    for name in allowed:  # O(a)
        a = by.get(alias.get(name, name))  # O(1)
        if a is None or _skip(a, tier):  # O(l)
            continue  # O(1)
        key = (bool(a.get("unknown")), running.get(name, 0), _pct(a, "weekly_all"), a.get("n") if isinstance(a.get("n"), int) else 10 ** 9)  # O(l)
        if best is None or key < best[0]:  # O(1)
            best = (key, name)  # O(1)
    return best[1] if best else None  # O(1)


def reasons(usage, allowed, tier=None, alias=None):  # O(a*l)
    alias = alias or {}  # O(1)
    by = {a.get("name"): a for a in (usage or {}).get("accounts") or []}  # O(a)
    out = []  # O(1)
    for name in allowed:  # O(a)
        a = by.get(alias.get(name, name))  # O(1)
        if a is None:  # O(1)
            out.append("%s: not in usage" % name)  # O(1)
            continue  # O(1)
        why = _skip(a, tier)  # O(l)
        if why:  # O(1)
            out.append("%s: %s" % (name, why))  # O(1)
    return out  # O(1)


def skip_line(usage, allowed, tier=None, alias=None, signed_out=None):  # "accounts skipped: ..." naming each skipped account and why, or None | O(a*l)
    parts = []  # O(1)
    if isinstance((usage or {}).get("accounts"), list):  # O(1)
        for r in reasons(usage, allowed, tier, alias):  # O(a*l)
            name, _, why = r.partition(": ")  # O(1)
            if why != "not in usage":  # O(1)
                parts.append("%s (%s)" % (name, why))  # O(1)
    parts += ["%s (signed out)" % n for n in signed_out or []]  # O(s)
    return "accounts skipped: " + ", ".join(parts) if parts else None  # O(a)


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


def _norm(path):  # O(len path)
    return os.path.normpath(os.path.expanduser(path))  # O(len path)


def aliases(listing, entries, env=None):  # O(a*e)
    """Entry -> claude-profile account name, for the entries that name a config dir: `current` and path entries.

    Keyed by `entry_name`; an entry whose dir no listed account owns (or a name entry) gets no alias."""
    dirs = {_norm(x["dir"]): x.get("name") for x in (listing or {}).get("accounts") or [] if x.get("dir") and x.get("name")}  # O(a)
    out = {}  # O(1)
    for entry in entries:  # O(e)
        if entry != "current" and not is_path(entry):  # O(1)
            continue  # O(1)
        d = account_dir(listing, entry, env)  # O(a)
        if d and _norm(d) in dirs:  # O(len d)
            out[entry_name(entry)] = dirs[_norm(d)]  # O(1)
    return out  # O(e)


def main(argv=None):  # O(a*l)
    """`sl accounts`: one line per account, `<name> ok 5h=..% weekly=..%` or `<name> skip <reason>`; 3 without usage data."""
    ap = argparse.ArgumentParser(prog="sl accounts")  # O(1)
    ap.add_argument("--tier", metavar="MODEL", default=None)  # O(1) adds that model's scoped weekly cap
    args = ap.parse_args(argv)  # O(a)
    usage = read_usage()  # O(1) plus subprocess time
    accts = usage.get("accounts") if isinstance(usage, dict) else None  # O(1)
    accts = [a for a in accts if isinstance(a, dict)] if isinstance(accts, list) else None  # O(a) an entry that is no object has no headroom to show
    if not accts:  # O(1)
        print("accounts: no usage data from claude-profile usage --json", file=sys.stderr)  # O(1)
        print("usage: sl accounts [--tier MODEL]", file=sys.stderr)  # O(1)
        return 3  # O(1)
    for a in accts:  # O(a)
        name, why = a.get("name") or "?", _skip(a, args.tier)  # O(l) an account without a name prints `?`
        note = " (usage unreadable; coordinator's own account)" if a.get("unknown") else " (reading %d min old)" % (a["stale_s"] // 60) if isinstance(a.get("stale_s"), int) else ""  # O(1)
        print("%s skip %s" % (name, why) if why else "%s ok 5h=%g%% weekly=%g%%%s" % (name, _five(a), _pct(a, "weekly_all"), note))  # O(l)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
