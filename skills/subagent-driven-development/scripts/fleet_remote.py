#!/usr/bin/env python3
"""Remote fleet workers: the configured `remote_tree` command (push, read, drop) and the mirror of a remote worker's stop records.

`<home>/machine.json` `{"remote_tree": ["<cmd>", ...]}` names the command; `push --host H --name N [--base REV] [--file PATH]... --timeout S`
prints the remote tree's path, `read --host H PATH --offset N --timeout S` prints bytes, `drop --host H --name N --timeout S` removes the tree
(exit 0 ok, 1 failed, 2 usage, 3 unreachable). Every call gets `timeout_s + 10` s; a failure is a `RemoteError`, never a dead worker.
`sync(sd, wid)` copies the worker's new stop lines of the remote `metrics.jsonl` and the transcripts they name into `<sd>/remote/<wid>/`.
"""
# Complexity notation:
# w = workers, m = bytes of new metrics lines, B = bytes of new transcript, p = path pairs, l = length of a text
import hashlib  # O(1)
import json  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)


class RemoteError(Exception):  # O(1)
    """A remote tree call failed; the message names the machine and the last stderr line."""


def tree_argv():  # O(1)
    try:  # O(1)
        v = json.loads((state.home() / "machine.json").read_text(encoding="utf-8"))["remote_tree"]  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return None  # O(1)
    return list(v) if isinstance(v, list) and v and all(isinstance(x, str) for x in v) else None  # O(1)


def target(label):  # O(machines)
    if not any(m.get("label") == label and m.get("enabled") for m in hc.machines()):  # O(machines)
        raise RemoteError(f"no enabled Herdr machine {label} (herdr machine list)")  # O(1)
    return label  # O(1)


def check(label):  # O(1)
    try:  # O(1)
        st = hc.machine_status(label, 10000)  # O(1)
    except hc.HerdrError as e:  # O(1)
        return f"herdr machine status failed: {getattr(e, 'message', '') or getattr(e, 'code', e)}"  # O(1)
    return "" if st == "reachable" else st  # O(1)


def _run(label, verb, args, cwd, timeout_s):  # O(output)
    argv = tree_argv()  # O(1)
    if argv is None:  # O(1)
        raise RemoteError(f"no remote_tree command in {state.home() / 'machine.json'}")  # O(1)
    limit = timeout_s + 10  # O(1)
    try:  # O(1)
        p = subprocess.run([*argv, verb, "--host", label, *args, "--timeout", str(timeout_s)], cwd=cwd, capture_output=True, timeout=limit)  # O(output)
    except subprocess.TimeoutExpired:  # O(1)
        raise RemoteError(f"{label}: remote_tree {verb} timed out after {limit} s") from None  # O(1)
    except OSError as e:  # O(1)
        raise RemoteError(f"{label}: remote_tree {verb}: {e}") from None  # O(1)
    err = p.stderr.decode("utf-8", "replace").strip().splitlines()  # O(output)
    last = err[-1] if err else f"exit {p.returncode}"  # O(1)
    if p.returncode == 3:  # O(1)
        raise RemoteError(f"{label} unreachable: {last}")  # O(1)
    if p.returncode != 0:  # O(1)
        if verb == "push" or p.returncode == 2:  # O(1)
            raise RemoteError(f"{label}: remote_tree {verb}: {last}")  # O(1)
        raise _Failed(last)  # O(1)
    return p.stdout  # O(output)


class _Failed(Exception):  # exit 1 of read or drop: the caller decides | O(1)
    pass  # O(1)


def push(label, root, name, base, files, timeout_s=120):  # O(files)
    args = ["--name", name, *(["--base", base] if base else []), *[x for f in files for x in ("--file", f)]]  # O(files)
    return _run(label, "push", args, root, timeout_s).decode("utf-8", "replace").strip()  # O(output)


def read(label, path, offset=0, timeout_s=30):  # O(B)
    try:  # O(1)
        return _run(label, "read", [path, "--offset", str(offset)], None, timeout_s)  # O(B)
    except _Failed as e:  # O(1)
        if "no such file" in str(e):  # O(1)
            return b""  # O(1)
        raise RemoteError(f"{label}: remote_tree read: {e}") from None  # O(1)


def drop(label, root, name, timeout_s=60):  # O(1)
    try:  # O(1)
        _run(label, "drop", ["--name", name], root, timeout_s)  # O(1)
    except _Failed as e:  # O(1)
        if "not found" in str(e):  # O(1)
            return False  # O(1)
        raise RemoteError(f"{label}: remote_tree drop: {e}") from None  # O(1)
    return True  # O(1)


def tree_name(sd, wid):  # O(l)
    project = Path(sd).resolve().parent  # O(l)
    return re.sub(r"[^A-Za-z0-9._-]+", "-", project.name).strip("-") + "-" + hashlib.sha256(str(project).encode()).hexdigest()[:6] + "/" + wid  # O(l)


def plugin(label, superlite_root, timeout_s=120):  # O(1)
    try:  # O(1)
        sha = subprocess.run(["git", "-C", superlite_root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()  # O(1)
    except subprocess.TimeoutExpired:  # O(1)
        raise RemoteError(f"git rev-parse HEAD in {superlite_root} timed out after 30 s") from None  # O(1)
    except OSError as e:  # O(1)
        raise RemoteError(f"git rev-parse HEAD in {superlite_root}: {e}") from None  # O(1)
    if not sha:  # O(1)
        raise RemoteError(f"{superlite_root} has no git HEAD")  # O(1)
    return push(label, superlite_root, f"plugin/{sha[:12]}", sha, [], timeout_s)  # O(1)


def mapper(pairs):  # O(p log p)
    pairs = sorted(pairs, key=lambda p: -len(p[0]))  # O(p log p)
    table = dict(pairs)  # O(p)
    if not table:  # O(1)
        return lambda text: text  # O(1)
    rx = re.compile(r"(?<![A-Za-z0-9_.\-/])(?:" + "|".join(re.escape(a) for a, _ in pairs) + r")(?![A-Za-z0-9_\-]|\.[A-Za-z0-9_])")  # O(p)
    return lambda text: rx.sub(lambda m: table[m.group(0)], text)  # O(l)


def sync(sd, wid):  # O(m + B)
    """Mirror the worker's new stop lines and transcripts; the number of lines mirrored, -1 when the host is unreachable."""
    sd = Path(sd)  # O(1)
    out = sd / "remote" / wid  # O(1)
    n = 0  # O(1)
    with fs.locked(sd):  # the lock covers only the record, never a remote call | O(1)
        live = ((fs.load(sd).get("workers") or {}).get(wid) or {}).get("remote")  # O(w)
        if not live:  # O(1)
            return 0  # O(1)
        rec = {**live, "tr": dict(live.get("tr") or {})}  # a private copy the remote reads advance | O(1)
    start = rec.get("offset", 0)  # O(1)
    lines, chunks = [], []  # stop entries and (local file, new transcript bytes) to write once the lock is taken again | O(1)
    try:  # O(1)
        new = read(rec["label"], rec["sd"].rstrip("/") + "/metrics.jsonl", start)  # O(m)
        end = new.rfind(b"\n") + 1  # O(m)
        for raw in new[:end].splitlines(keepends=True):  # O(lines)
            try:  # O(1)
                e = json.loads(raw)  # O(l)
            except ValueError:  # O(1)
                e = None  # O(1)
            if isinstance(e, dict) and e.get("ev") == "stop" and e.get("agent_id") == wid:  # O(1)
                if e.get("transcript"):  # O(1)
                    e["transcript"] = _mirror(rec, e["transcript"], out, chunks)  # O(B)
                lines.append(e)  # O(1)
                n += 1  # O(1)
            rec["offset"] = rec.get("offset", 0) + len(raw)  # O(1)
    except RemoteError:  # O(1)
        n = -1  # O(1)
    with fs.locked(sd):  # O(1)
        data = fs.load(sd)  # O(w)
        live = ((data.get("workers") or {}).get(wid) or {}).get("remote")  # O(1)
        if not live:  # O(1)
            return 0  # O(1)
        if live.get("offset", 0) != start:  # a concurrent sync already appended these lines; offsets only move forward | O(1)
            return -1 if n < 0 else 0  # O(1)
        if rec["offset"] != start:  # O(1)
            out.mkdir(parents=True, exist_ok=True)  # O(1)
            for local, chunk in chunks:  # O(chunks)
                with open(local, "ab") as fh:  # O(1)
                    fh.write(chunk)  # O(B)
            with open(out / "metrics.jsonl", "a", encoding="utf-8") as fh:  # O(1)
                fh.write("".join(json.dumps(e) + "\n" for e in lines))  # O(m)
            live["offset"], live["tr"] = rec["offset"], rec["tr"]  # O(1)
            fs.save(sd, data)  # O(w)
    return n  # O(1)


def _mirror(rec, remote_path, out, chunks):  # O(B)
    local = out / Path(remote_path).name  # O(1)
    tr = rec["tr"]  # O(1)
    chunk = read(rec["label"], remote_path, tr.get(remote_path, 0))  # O(B)
    if chunk:  # O(1)
        chunks.append((local, chunk))  # O(1)
        tr[remote_path] = tr.get(remote_path, 0) + len(chunk)  # O(1)
    return str(local)  # O(1)
