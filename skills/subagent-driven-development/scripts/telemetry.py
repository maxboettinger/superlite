#!/usr/bin/env python3
"""Superlite's local event log: one JSON line per event in `$SUPERLITE_HOME/events.jsonl` (default `~/.superlite/`).

    telemetry.py agent-stop --transcript P --agent-type T [--agent-id ID] [--cwd D] [--sd D]
    telemetry.py export --since YYYY-MM-DD [--root DIR]... [--out FILE]

Library: `emit(kind, sd=None, cwd=None, session=None, **fields) -> bool` appends one line and never raises (a failed
write, an unknown kind, or the off switch gives False). Lines hold no prompt, response or file content. At most 4096
bytes per line. Off with `SUPERLITE_TELEMETRY=0` or the file `<home>/telemetry-off`. Stdlib only.
"""
# Complexity notation:
#   s = size of the line, n = events in the log, d = depth of the working folder, k = fields of the line
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import secrets  # O(1)
import sys  # O(1)
from datetime import datetime, timezone  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

MAX_BYTES = 20 * 1024 * 1024  # rotation threshold | O(1)
KEEP = 5  # rotated files kept | O(1)
MAX_LINE = 4096  # bytes of one line, newline included | O(1)
MAX_TARGET = 200  # characters of a gate target | O(1)
SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")  # O(1)
KEY_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}\Z")  # a pending key; never a path | O(1)
T_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\Z")  # O(1)
COMMON = ("v", "t", "kind", "session", "run", "repo_root", "harness", "version", "worker", "role", "config_dir")  # O(1)
KINDS = {  # O(1)
    "invoke": ("name", "via"),
    "mode": ("mode",),
    "orchestrator": ("mode", "by"),
    "fleet": ("on", "accounts"),
    "session_start": ("source", "duration_s"),
    "session_end": ("reason", "duration_s"),
    "run_start": ("plan", "tasks", "detail", "branch", "mode", "orchestrator", "fleet"),
    "dispatch": ("task", "role", "agent_type", "model", "effort", "tier", "account", "machine", "label",
                 "writer_role"),
    "agent_stop": ("task", "role", "model", "effort", "account", "machine", "duration_s", "tokens", "cost_usd",
                   "tool_calls", "status", "writer_role"),
    "tests": ("mode", "passed", "failed", "skipped", "seconds", "task"),
    "gate": ("hook", "decision", "rule", "tool", "target"),
    "review": ("review_kind", "verdict", "findings", "round"),
    "batch": ("batch", "state", "lead_model", "pr", "reason"),
    "feedback": ("fkind", "reason"),
    "run_end": ("outcome", "wall_s", "cost_usd", "tasks", "first_time_pass", "fix_rounds", "final_verdict", "agents",
                "tests_passed", "tests_failed", "ci_red", "questions", "projected_min", "critical_path_min", "reason", "mode", "orchestrator", "fleet"),
}
WRITER_ROLE_KINDS = ("dispatch", "agent_stop")  # O(1)


def _home() -> Path:  # O(1)
    return Path(os.environ.get("SUPERLITE_HOME") or Path.home() / ".superlite")  # O(1)


def events_path():  # the log file, or None when telemetry is off | O(1)
    if os.environ.get("SUPERLITE_TELEMETRY") == "0":  # O(1)
        return None  # O(1)
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("SUPERLITE_HOME"):  # a test never writes the real home | O(1)
        return None  # O(1)
    home = _home()  # O(1)
    if (home / "telemetry-off").exists():  # O(1)
        return None  # O(1)
    return home / "events.jsonl"  # O(1)


def _sid(session):  # a session id usable in a path, else None | O(1)
    return session if isinstance(session, str) and SID_RE.match(session) else None  # O(1)


def _stable_run(sd):  # O(size of stable.json)
    try:  # O(1)
        data = json.loads((Path(sd) / "stable.json").read_text(encoding="utf-8"))  # O(size)
        rid = data.get("run_id") if isinstance(data, dict) else None  # O(1)
        return rid if isinstance(rid, str) and rid else None  # O(1)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)


def run_id(sd):  # the run id of a `.superlite` folder's stable.json | O(size)
    return _stable_run(sd) if sd else None  # O(size)


def new_run_id(now=None) -> str:  # O(1)
    now = now or datetime.now(timezone.utc)  # O(1)
    return now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)  # O(1)


def session_mode(session=None):  # the mode a session chose, else None | O(1)
    sid = _sid(session or os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("SUPERLITE_SESSION_ID"))  # O(1)
    if not sid:  # O(1)
        return None  # O(1)
    try:  # O(1)
        word = (_home() / "telemetry" / "sessions" / (sid + ".mode")).read_text(encoding="utf-8").strip()  # O(1)
    except OSError:  # O(1)
        return None  # O(1)
    return word or None  # O(1)


def _logical_cwd(cwd):  # the cwd argument, else $PWD when it names the working folder, else os.getcwd(); never resolved | O(d)
    if cwd:  # O(1)
        return os.path.abspath(str(cwd))  # O(d)
    real = os.getcwd()  # O(1)
    pwd = os.environ.get("PWD")  # O(1)
    try:  # O(1)
        if pwd and os.path.isabs(pwd) and os.path.samefile(pwd, real):  # O(d)
            return os.path.abspath(pwd)  # O(d)
    except OSError:  # O(1)
        pass  # O(1)
    return real  # O(1)


def _repo_root(cwd):  # nearest folder above the logical cwd holding .git (file or folder), as the bash writer walks it | O(d)
    try:  # O(1)
        start = Path(_logical_cwd(cwd))  # O(d)
    except OSError:  # O(1)
        return None  # O(1)
    for d in (start, *start.parents):  # O(d)
        if (d / ".git").exists():  # O(1)
            return str(d)  # O(1)
    return None  # O(1)


def _harness():  # O(1)
    from feedback import harness  # lazy: feedback may import this module | O(1)
    h = harness()  # O(1)
    return None if h == "unknown" else h  # O(1)


def _version():  # O(size of package.json)
    from feedback import version  # O(1)
    v = version()  # O(size)
    return None if v == "unknown" else v  # O(1)


def _now() -> str:  # O(1)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"  # O(1)


def _encode(line):  # one line within MAX_LINE bytes, or None | O(s * k)
    def dump():  # O(s)
        return json.dumps(line, ensure_ascii=False, separators=(",", ":")).encode("utf-8")  # O(s)
    if isinstance(line.get("target"), str):  # O(1)
        line["target"] = line["target"][:MAX_TARGET]  # O(1)
    data = dump()  # O(s)
    while len(data) + 1 > MAX_LINE:  # O(k) rounds: each cuts a string or drops target
        over = len(data) + 1 - MAX_LINE  # O(1)
        strs = [k for k, v in line.items() if isinstance(v, str) and len(v) > 1]  # O(k)
        if strs:  # O(1)
            k = max(strs, key=lambda x: len(line[x]))  # O(k)
            keep = max(len(line[k]) - over - 1, 0)  # a character is at least one byte | O(1)
            line[k] = line[k][:keep] + "…"  # O(1)
        elif line.get("target") is not None:  # O(1)
            line["target"] = None  # O(1)
        else:  # O(1)
            return None  # O(1)
        data = dump()  # O(s)
    return data + b"\n"  # O(s)


def _rotate(path):  # O(KEEP)
    if os.stat(path).st_size < MAX_BYTES:  # O(1)
        return  # O(1)
    lock = None  # O(1)
    try:  # O(1)
        d = path.parent / "telemetry"  # O(1)
        d.mkdir(parents=True, exist_ok=True)  # O(1)
        try:  # O(1)
            import fcntl  # POSIX only; Windows renames without a lock | O(1)
            lock = open(d / "rotate.lock", "a")  # O(1)
            fcntl.flock(lock, fcntl.LOCK_EX)  # O(1)
        except (ImportError, OSError):  # O(1)
            pass  # O(1)
        if os.stat(path).st_size < MAX_BYTES:  # another writer rotated first | O(1)
            return  # O(1)
        for i in range(KEEP - 1, 0, -1):  # O(KEEP)
            src = path.with_name(f"{path.name}.{i}")  # O(1)
            if src.exists():  # O(1)
                os.replace(src, path.with_name(f"{path.name}.{i + 1}"))  # O(1)
        os.replace(path, path.with_name(path.name + ".1"))  # O(1)
    finally:  # O(1)
        if lock:  # O(1)
            lock.close()  # releases the flock | O(1)


OPTIONAL = {"agent_stop": ("agent_session",)}  # keys a line may carry beyond KINDS; left out when unknown | O(1)


def _build(kind, sd, cwd, session, fields):  # the line dict | O(k)
    fields = dict(fields)  # O(k)
    if kind in WRITER_ROLE_KINDS and fields.get("writer_role") is None:  # O(1)
        fields["writer_role"] = os.environ.get("SUPERLITE_FLEET_ROLE") or None  # O(1)
    sess = session or os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("SUPERLITE_SESSION_ID") or None  # O(1)
    state = sd or os.environ.get("SUPERLITE_STATE_DIR")  # without sd only $SUPERLITE_STATE_DIR | O(1)
    common = {"v": 1, "t": _now(), "kind": kind, "session": sess, "run": run_id(state), "repo_root": _repo_root(cwd),  # O(size)
              "harness": _harness(), "version": _version(), "worker": os.environ.get("SUPERLITE_FLEET_WORKER") or None,
              "role": os.environ.get("SUPERLITE_FLEET_ROLE") or None,
              "config_dir": os.environ.get("CLAUDE_CONFIG_DIR") or None}
    for k in ("t", "run", "repo_root", "session"):  # a caller may set these (backfill, deferred run end) | O(1)
        if fields.get(k) is not None:  # O(1)
            common[k] = fields[k]  # O(1)
    line = dict(common)  # O(1)
    for k in KINDS[kind]:  # O(k)
        line[k] = fields.get(k)  # O(1)
    for k in OPTIONAL.get(kind, ()):  # an optional key is left out when it has no value | O(1)
        if fields.get(k):  # O(1)
            line[k] = fields[k]  # O(1)
    if fields.get("backfill"):  # O(1)
        line["backfill"] = True  # O(1)
    return line  # O(1)


def emit(kind, sd=None, cwd=None, session=None, **fields) -> bool:  # append one line; never raises | O(s)
    try:  # O(1)
        if kind not in KINDS:  # O(1)
            return False  # O(1)
        path = events_path()  # O(1)
        if path is None:  # O(1)
            return False  # O(1)
        data = _encode(_build(kind, sd, cwd, session, fields))  # O(s)
        if data is None:  # O(1)
            return False  # O(1)
        path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        if path.exists():  # O(1)
            _rotate(path)  # O(KEEP)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)  # O(1)
        try:  # O(1)
            os.write(fd, data)  # one write per line | O(s)
        finally:  # O(1)
            os.close(fd)  # O(1)
        return True  # O(1)
    except BaseException:  # SystemExit too: a telemetry write never changes the caller's exit | O(1)
        return False  # O(1)


def _read(path):  # O(file)
    out = []  # O(1)
    try:  # O(1)
        text = Path(path).read_text(encoding="utf-8", errors="replace")  # O(file)
    except OSError:  # O(1)
        return out  # O(1)
    for raw in text.splitlines():  # O(lines)
        try:  # O(1)
            obj = json.loads(raw)  # O(line)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(obj, dict):  # O(1)
            out.append(obj)  # O(1)
    return out  # O(lines)


def read_events(path=None) -> list[dict]:  # parsed lines of the log, bad lines skipped | O(n)
    return _read(path or _home() / "events.jsonl")  # O(n)


def validate(line) -> list[str]:  # problems of one line, [] when it is well formed | O(k)
    if not isinstance(line, dict):  # O(1)
        return ["not an object"]  # O(1)
    kind = line.get("kind")  # O(1)
    if kind not in KINDS:  # O(1)
        return [f"unknown kind {kind!r}"]  # O(1)
    errs = []  # O(1)
    for k in COMMON:  # O(1)
        if k not in line:  # O(1)
            errs.append(f"{kind}: missing {k}")  # O(1)
    for k in KINDS[kind]:  # O(k)
        if k not in line:  # O(1)
            errs.append(f"{kind}: missing {k}")  # O(1)
    for k in line:  # O(k)
        if k not in COMMON and k not in KINDS[kind] and k != "backfill" and k not in OPTIONAL.get(kind, ()):  # O(1)
            errs.append(f"{kind}: unexpected {k}")  # O(1)
    if line.get("v") != 1:  # O(1)
        errs.append(f"{kind}: v must be 1")  # O(1)
    if "t" in line and not (isinstance(line["t"], str) and T_RE.match(line["t"])):  # O(1)
        errs.append(f"{kind}: bad t")  # O(1)
    if len(json.dumps(line, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1 > MAX_LINE:  # O(s)
        errs.append(f"{kind}: line over {MAX_LINE} bytes")  # O(s)
    return errs  # O(k)


def count(kind, run, **eq) -> int:  # lines of a kind (and run, and equal fields) in events.jsonl and .1 | O(n)
    base = _home() / "events.jsonl"  # O(1)
    n = 0  # O(1)
    for p in (base, base.with_name(base.name + ".1")):  # O(1)
        for e in _read(p):  # O(n)
            if e.get("kind") == kind and e.get("run") == run and all(e.get(k) == v for k, v in eq.items()):  # O(k)
                n += 1  # O(1)
    return n  # O(n)


def batch_key(root, batch) -> str:  # `<main repository folder name>-<batch>` | O(d)
    from feedback import project  # O(1)
    return f"{project(root)}-{batch}"  # O(d)


def _pending(key, ext):  # O(1)
    return _home() / "telemetry" / "pending" / (key + ext) if KEY_RE.match(key or "") else None  # O(1)


def _write_text(path, text):  # O(size)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    path.write_text(text, encoding="utf-8")  # O(size)


def _load(path):  # a JSON object or None | O(size)
    try:  # O(1)
        data = json.loads(path.read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    return data if isinstance(data, dict) else None  # O(1)


def _unlink(path):  # O(1)
    try:  # O(1)
        path.unlink()  # O(1)
    except OSError:  # O(1)
        pass  # O(1)


def defer_run_end(key, fields) -> bool:  # store a lead run's end until its batch finishes | O(size)
    try:  # O(1)
        if events_path() is None:  # O(1)
            return False  # O(1)
        pj, po = _pending(key, ".json"), _pending(key, ".outcome")  # O(1)
        if pj is None:  # O(1)
            return False  # O(1)
        fields = dict(fields)  # O(k)
        if fields.get("run") is None:  # the run id of the moment, since the writer of the line may be another process | O(size)
            fields["run"] = run_id(os.environ.get("SUPERLITE_STATE_DIR")) if os.environ.get("SUPERLITE_STATE_DIR") else None  # O(size)
        for k, v in (("session", os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("SUPERLITE_SESSION_ID")),  # O(1)
                     ("repo_root", _repo_root(None))):
            if fields.get(k) is None and v:  # O(1)
                fields[k] = v  # O(1)
        verdict = _load(po)  # O(size)
        if verdict:  # the batch finished first | O(1)
            _unlink(po)  # O(1)
            fields["outcome"] = verdict.get("outcome") or fields.get("outcome")  # O(1)
            if verdict.get("reason"):  # O(1)
                fields["reason"] = verdict["reason"]  # O(1)
            return emit("run_end", **fields)  # O(s)
        _write_text(pj, json.dumps(fields))  # O(size)
        return True  # O(1)
    except BaseException:  # O(1)
        return False  # O(1)


def finish_deferred(key, outcome, reason=None) -> bool:  # the batch finished: write the stored run end, or remember the outcome | O(size)
    try:  # O(1)
        if events_path() is None:  # O(1)
            return False  # O(1)
        pj, po = _pending(key, ".json"), _pending(key, ".outcome")  # O(1)
        if pj is None:  # O(1)
            return False  # O(1)
        fields = _load(pj)  # O(size)
        if fields is not None:  # O(1)
            _unlink(pj)  # claimed before the write, so a second finish finds nothing | O(1)
            fields["outcome"] = outcome  # O(1)
            if reason is not None:  # O(1)
                fields["reason"] = reason  # O(1)
            return emit("run_end", **fields)  # O(s)
        if po.exists():  # an earlier finish is already waiting | O(1)
            return False  # O(1)
        _write_text(po, json.dumps({"outcome": outcome, "reason": reason}))  # O(1)
        return True  # O(1)
    except BaseException:  # O(1)
        return False  # O(1)


def _date(text):  # argparse type: YYYY-MM-DD | O(1)
    try:  # O(1)
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")  # O(1)
    except ValueError:  # O(1)
        raise argparse.ArgumentTypeError(f"bad date {text!r}, want YYYY-MM-DD")  # O(1)


def main(argv=None) -> int:  # O(1) plus the subcommand
    ap = argparse.ArgumentParser(prog="telemetry")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    st = sub.add_parser("agent-stop")  # O(1)
    st.add_argument("--transcript", required=True)  # O(1)
    st.add_argument("--agent-type", required=True)  # O(1)
    st.add_argument("--agent-id")  # O(1)
    st.add_argument("--cwd")  # O(1)
    st.add_argument("--sd")  # O(1)
    ex = sub.add_parser("export")  # O(1)
    ex.add_argument("--since", required=True, type=_date)  # O(1)
    ex.add_argument("--root", action="append", default=[])  # O(1)
    ex.add_argument("--out")  # O(1)
    if argv is None:  # O(1)
        argv = sys.argv[1:]  # O(1)
    if argv and argv[0] == "agent-stop":  # a hook's call: even a bad argument exits 0, silently | O(1)
        try:  # O(1)
            import io  # O(1)
            from contextlib import redirect_stderr  # O(1)
            with redirect_stderr(io.StringIO()):  # O(1)
                a = ap.parse_args(argv)  # O(1)
            import telemetry_agents  # T5 | O(1)
            return int(telemetry_agents.main(a) or 0)  # O(tool)
        except BaseException:  # O(1)
            return 0  # O(1)
    a = ap.parse_args(argv)  # a bad date exits 2 | O(1)
    import telemetry_export  # T10 | O(1)
    return int(telemetry_export.main(a) or 0)  # O(export)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
