#!/usr/bin/env python3
"""Automatic placement of fleet workers (#919): which machine, this one or a saved Herdr machine, a new worker starts on.

`room(sd)` runs the `remote_room` command of `<home>/machine.json` (cached in `<sd>/room.json` for 60 s) and maps its machines to
`{"local": {...}, "<label>": {"state", "room"}}`; any failure means `{"local": unknown}`. `choose(sd, role, project)` returns a machine label or None (local):
a remote scores its room minus its live workers minus a margin (`remote_margin` of machine.json, an int, default 2), local scores its room minus its live workers, ties go local.
`skip(sd, label, why)` keeps a machine out of placement for some minutes; `set_mode(sd, "local"|"spread")` is the `placement` key of fleet.json.
A failure here never raises: it means local.
A research worker whose brief names a path from the lead brief's research line (`backlog_brief.research_reads`) stays local; without the brief, every research worker of such a lead does (#1111).
A project keeps machines out of its fleet with `.superlite/placement.json` `{"exclude": ["<label>", ...]}` (the project's and, from a linked worktree, the main checkout's; a malformed file keeps every worker local) (#1096).
"""
# Complexity notation:
# w = workers, m = machines, k = keys of a json file
import contextlib  # O(1)
import fcntl  # O(1)
import json  # O(1)
import os  # O(1)
import socket  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

MARGIN = 2  # O(1) a remote must beat local by this much: the push and the pull cost something
TIMEOUT = 20  # O(1) seconds for the room command
LIVE = ("ready", "busy", "starting")  # O(1)
ROLES = ("implementer", "fixer", "package-reviewer", "final-reviewer", "research")  # O(1) roles that may run remote
PAIR_MINUTES = 15.0  # O(1) a signed-out (machine, account) pair stays out this long
MODES = ("spread", "local")  # O(1)
UNKNOWN = {"local": {"state": "unknown", "room": None}}  # O(1)


def _machine_cfg(key):  # O(k): an argv list of machine.json or None
    try:  # O(1)
        v = json.loads((state.home() / "machine.json").read_text(encoding="utf-8"))[key]  # O(k)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return None  # O(1)
    return list(v) if isinstance(v, list) and v and all(isinstance(x, str) for x in v) else None  # O(1)


def _margin():  # O(k): remote_margin of machine.json, an int (negative allowed); anything else means MARGIN
    try:  # O(1)
        v = json.loads((state.home() / "machine.json").read_text(encoding="utf-8"))["remote_margin"]  # O(k)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return MARGIN  # O(1)
    return v if isinstance(v, int) and not isinstance(v, bool) else MARGIN  # O(1)


def _json(p):  # O(k): the object in a file, {} when unreadable
    try:  # O(1)
        v = json.loads(Path(p).read_text(encoding="utf-8"))  # O(k)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return v if isinstance(v, dict) else {}  # O(1)


def _local_names():  # O(1)
    try:  # O(1)
        h = socket.gethostname().strip().lower()  # O(1)
    except OSError:  # O(1)
        return set()  # O(1)
    return {h, h.split(".")[0]} - {""}  # O(1)


def _write(p, data):  # O(k): replace a json file whole through a temp file in its folder, so a reader sees the old or the new content
    p = Path(p)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:  # O(1)
            fh.write(json.dumps(data))  # O(k)
        os.replace(tmp, p)  # O(1) atomic rename
    except BaseException:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            os.unlink(tmp)  # O(1)
        raise  # O(1)


@contextlib.contextmanager
def _lock(sd):  # O(1) plus wait: its own lock file, so a caller holding fs.locked(sd) cannot deadlock here
    with open(Path(sd) / "room-skip.json.lock", "a") as lf:  # O(1)
        fcntl.flock(lf, fcntl.LOCK_EX)  # O(1) blocks until free
        yield  # O(1)


def _fetch():  # O(m): the mapped room of one command run, or None
    argv = _machine_cfg("remote_room")  # O(k)
    if not argv:  # O(1)
        return None  # O(1)
    try:  # O(1)
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT)  # O(1) bounded
        if r.returncode != 0:  # O(1)
            return None  # O(1)
        rows = json.loads(r.stdout)["machines"]  # O(m)
        names, out = _local_names(), {}  # O(1)
        for row in rows:  # O(m)
            name = str(row["name"])  # O(1)
            room = row.get("room")  # O(1)
            out["local" if name.lower() in names else name] = {"state": str(row.get("state", "unknown")), "room": room if isinstance(room, (int, float)) else None}  # O(1)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):  # O(1)
        return None  # O(1)
    out.setdefault("local", dict(UNKNOWN["local"]))  # O(1)
    return out  # O(1)


def room(sd, ttl=60.0, now=None):  # O(m)
    now = time.time() if now is None else now  # O(1)
    cache = Path(sd) / "room.json"  # O(1)
    c = _json(cache)  # O(k)
    if isinstance(c.get("room"), dict) and isinstance(c.get("at"), (int, float)) and 0 <= now - c["at"] < ttl:  # O(1)
        return c["room"]  # O(1)
    got = _fetch()  # O(m)
    if got is None:  # O(1)
        return {"local": dict(UNKNOWN["local"])}  # O(1)
    try:  # O(1)
        _write(cache, {"at": now, "room": got})  # O(m)
    except OSError:  # O(1)
        pass  # O(1)
    return got  # O(1)


def enabled(sd):  # O(w)
    mode = fs.load(sd).get("placement")  # O(w)
    return bool(_machine_cfg("remote_room") and _machine_cfg("remote_tree")) and mode != "local"  # O(k)


def set_mode(sd, mode):  # O(w)
    if mode not in MODES:  # O(1)
        raise ValueError("placement mode must be one of %s, not %r" % (", ".join(MODES), mode))  # O(1)
    with fs.locked(sd):  # O(1)
        data = fs.load(sd)  # O(w)
        data["placement"] = mode  # O(1)
        fs.save(sd, data)  # O(w)


def _skips(sd):  # O(k)
    return _json(Path(sd) / "room-skip.json")  # O(k)


def signed_out_pairs(sd, label, now=None):  # O(k): accounts recorded signed out on a machine and not yet expired
    now = time.time() if now is None else now  # O(1)
    accs = (_skips(sd).get(label) or {}).get("accounts")  # O(k)
    return {a for a, t in accs.items() if isinstance(t, (int, float)) and t > now} if isinstance(accs, dict) else set()  # O(a)


def skip(sd, label, why, minutes=10.0, now=None):  # O(k): a sign-in reason skips the (machine, account) pair, any other reason the machine
    import fleet_remote_account as fra  # noqa: PLC0415 | O(1)
    now = time.time() if now is None else now  # O(1)
    name, named = fra.signed_out_account(why), False  # O(len)
    try:  # O(1)
        with _lock(sd):  # the read-modify-write of two parallel rounds must not drop an entry | O(1) plus wait
            d = _skips(sd)  # O(k)
            old = d.get(label) if isinstance(d.get(label), dict) else {}  # O(1)
            if name:  # O(1)
                accs = old.get("accounts") if isinstance(old.get("accounts"), dict) else {}  # O(1)
                named = name not in accs  # O(1)
                d[label] = {**old, "accounts": {**accs, name: now + PAIR_MINUTES * 60}}  # O(a)
            else:  # O(1)
                d[label] = {**old, "until": now + minutes * 60, "why": why}  # O(1)
            _write(Path(sd) / "room-skip.json", d)  # O(k)
    except OSError:  # O(1)
        return  # O(1)
    if named:  # O(1)
        print(f"placement: account {name} is signed out on {label}; {label} stays in placement with its other accounts; "
              f"sign {name} in there once (claude, then /login)", file=sys.stderr)  # O(1)


def _swift(project):  # O(entries)
    p = Path(project)  # O(1)
    try:  # O(1)
        if (p / "Package.swift").exists() or any(c.suffix in (".xcodeproj", ".xcworkspace") for c in p.iterdir()):  # O(entries)
            return True  # O(1)
    except OSError:  # O(1)
        return False  # O(1)
    return _json(p / ".superlite" / "test-cmd.json").get("language") == "swift"  # O(k)


def config_files(project):  # O(1): the project's placement.json, then the main checkout's when project is a linked worktree
    p = Path(project)  # O(1)
    out = [p / ".superlite" / "placement.json"]  # O(1)
    try:  # O(1)
        r = subprocess.run(["git", "-C", str(p), "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True, timeout=10)  # O(1) bounded
    except (OSError, subprocess.SubprocessError):  # O(1)
        return out  # O(1)
    if r.returncode != 0 or not r.stdout.strip():  # O(1)
        return out  # O(1)
    main = Path(r.stdout.strip()).parent  # O(1)
    if main.resolve() != p.resolve():  # O(1)
        out.append(main / ".superlite" / "placement.json")  # O(1)
    return out  # O(1)


def excluded(project):  # O(f * k): (excluded names, config files that exist, first error or None)
    names, files, err = set(), [], None  # O(1)
    for path in config_files(project):  # O(f)
        if not path.exists():  # O(1)
            continue  # O(1)
        files.append(path)  # O(1)
        try:  # O(1)
            data = json.loads(path.read_text(encoding="utf-8"))  # O(k)
        except OSError:  # O(1)
            err = err or f"{path}: unreadable"  # O(1)
            continue  # O(1)
        except ValueError:  # O(1)
            err = err or f"{path}: not valid JSON"  # O(1)
            continue  # O(1)
        if not isinstance(data, dict):  # O(1)
            err = err or f"{path}: not a JSON object"  # O(1)
            continue  # O(1)
        items = data.get("exclude", [])  # O(1)
        if not isinstance(items, list) or not all(isinstance(i, str) and i.strip() for i in items):  # O(k)
            err = err or f"{path}: exclude must be a list of machine names"  # O(1)
            continue  # O(1)
        names |= {i.strip().lower() for i in items}  # O(k)
    return names, files, err  # O(1)


def is_excluded(label, names):  # O(n)
    return label.strip().lower().split(".")[0] in {n.split(".")[0] for n in names}  # O(n)


def machine_refusal(project, machine):  # O(f * k): why an explicit --machine is refused, or None
    if not machine or machine == "local":  # O(1)
        return None  # O(1)
    names, files, err = excluded(project)  # O(f * k)
    if err:  # O(1)
        return f"error: {err}; fix it before a remote spawn (#1096)"  # O(1)
    if is_excluded(machine, names):  # O(n)
        return f"error: machine {machine} is excluded from this project's fleet by {', '.join(str(f) for f in files)}; drop --machine or pass --machine local (#1096)"  # O(f)
    return None  # O(1)


def _live(sd):  # O(w): live workers per machine, None key = local
    out = {}  # O(1)
    for w in fs.load(sd).get("workers", {}).values():  # O(w)
        if isinstance(w, dict) and w.get("state") in LIVE:  # O(1)
            out[w.get("machine") or None] = out.get(w.get("machine") or None, 0) + 1  # O(1)
    return out  # O(1)


def research_local(sd, project, brief=None):  # O(len + t * r): True when a research worker may need a read-only reference path only this machine has (#1111)
    try:  # O(1)
        import backlog_brief as bb  # noqa: PLC0415 | O(1)
        reads = [Path(x).resolve() for x in getattr(bb, "research_reads", lambda _sd: [])(Path(sd))]  # O(r)
    except Exception:  # O(1) a failing reader means no reads
        reads = []  # O(1)
    if not reads:  # O(1)
        return False  # O(1)
    if brief is None:  # O(1)
        return True  # O(1)
    try:  # O(1)
        import fleet_io  # noqa: PLC0415 | O(1)
        text = Path(brief).read_text(encoding="utf-8", errors="replace")  # O(len)
        for t in fleet_io.brief_outside(text, project, sd):  # O(t)
            p = Path(fleet_io.local_path(t, project)).resolve()  # O(len)
            if any(p == r or r in p.parents for r in reads):  # O(r)
                return True  # O(1)
    except Exception:  # O(1) an unreadable brief or a failing helper means local
        return True  # O(1)
    return False  # O(1)


def choose(sd, role, project, now=None, brief=None):  # O(w + m)
    try:  # O(1)
        if role not in ROLES or not enabled(sd) or _swift(project):  # O(entries)
            return None  # O(1)
        names, _files, err = excluded(project)  # O(f * k)
        if err:  # O(1)
            print(f"placement: {err}; every worker of this project stays local (#1096)", file=sys.stderr)  # O(1)
            return None  # O(1)
        if role == "research" and research_local(sd, project, brief):  # O(len + t * r)
            print("placement: research worker stays local: its brief may name a read-only reference path from the lead brief's research line, which only this machine has (#1111)", file=sys.stderr)  # O(1)
            return None  # O(1)
        now = time.time() if now is None else now  # O(1)
        rm, live, skips = room(sd, now=now), _live(sd), _skips(sd)  # O(w + m)
        saved = {m.get("label") for m in hc.machines() if m.get("enabled")} if len(rm) > 1 else set()  # O(m)
        loc = rm.get("local", {}).get("room")  # O(1)
        best, best_score = None, (loc if isinstance(loc, (int, float)) else 0) - live.get(None, 0)  # local's score; a tie keeps local | O(1)
        margin = _margin()  # O(k)
        for label, info in rm.items():  # O(m)
            if label == "local" or label not in saved or info.get("state") != "ready" or not isinstance(info.get("room"), (int, float)):  # O(1)
                continue  # O(1)
            if is_excluded(label, names):  # O(n)
                continue  # O(1)
            until = (skips.get(label) or {}).get("until")  # O(1)
            if isinstance(until, (int, float)) and until > now:  # O(1)
                continue  # O(1)
            score = info["room"] - live.get(label, 0) - margin  # O(1)
            if score > 0 and score > best_score:  # O(1)
                best, best_score = label, score  # O(1)
        return best  # O(1)
    except Exception:  # O(1) placement never blocks a spawn
        return None  # O(1)
