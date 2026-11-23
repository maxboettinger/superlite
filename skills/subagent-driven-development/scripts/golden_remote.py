#!/usr/bin/env python3
"""Run one golden attempt on a saved Herdr machine (`golden.py run --machine M`).

This machine pushes its commit as the plugin tree and a start commit at the case base (carrying the case JSON) to the host, starts
`golden.py attempt` there in a Herdr workspace (the host's own herdr, accounts and paths run the whole attempt), polls its output
file, then reads the row and the saved patch back. The host needs python3, git, uv, herdr, signed-in Claude accounts and the
superlite plugin installed. A remote attempt that gives no host row is one NOT RUN row (`started: False`).
"""
# Complexity notation:
# B = bytes read back, p = polls
from __future__ import annotations

import json  # O(1)
import secrets  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import threading  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_remote as fr  # noqa: E402 | O(1)
import fleet_remote_worker as rw  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import remote_apply as ra  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

POLL_S = 30  # seconds between two reads of the host's output file | O(1)
SLACK_S = 2400  # on top of the lead's timeout: clone, the 600 s start, the 900 s hidden tests, cleanup | O(1)
READ_TRIES = 5  # read errors in a row before the attempt gives up | O(1)
PUSH_S = 600  # bound of a push | O(1)
PATCH_CAP = 2 * 1024 * 1024  # bytes read back of a patch | O(1)
ROW_CAP = 1024 * 1024  # bytes read back of the host row | O(1)
SCRIPTS_REL = "skills/subagent-driven-development/scripts"  # O(1)
_PLUGINS: dict = {}  # machine label -> plugin tree on the host | O(1)
_LOCK = threading.Lock()  # O(1)


class _NotRun(RuntimeError):  # the attempt ended with no host row | O(1)
    pass


def _token() -> str:  # O(1)
    return secrets.token_hex(3)  # O(1)


def _drop_ref(src, ref) -> None:  # the local ref of the start commit; an error is ignored | O(1)
    try:  # O(1)
        subprocess.run(["git", "-C", str(src), "update-ref", "-d", ref], capture_output=True, timeout=30)  # O(1)
    except (OSError, subprocess.TimeoutExpired):  # O(1)
        pass  # O(1)


def _plugin_tree(label: str) -> str:  # this checkout's commit on the host, pushed once per machine | O(1)
    with _LOCK:  # O(1)
        if label not in _PLUGINS:  # O(1)
            _PLUGINS[label] = fr.plugin(label, rw.SUPERLITE_ROOT, PUSH_S)  # O(1)
        return _PLUGINS[label]  # O(1)


def _read_all(label: str, path: str, cap: int) -> bytes:  # a host file, read from growing offsets up to cap | O(B)
    parts, offset = [], 0  # O(1)
    while offset <= cap:  # O(B / chunk)
        data = fr.read(label, path, offset)  # O(chunk)
        if not data:  # O(1)
            break  # O(1)
        parts.append(data)  # O(1)
        offset += len(data)  # O(1)
    return b"".join(parts)  # O(B)


def ready(label: str) -> str:  # "" when the machine can run golden attempts, else why not | O(1)
    if fr.tree_argv() is None:  # O(1)
        return f"no remote_tree command in {state.home() / 'machine.json'}"  # O(1)
    try:  # O(1)
        fr.target(label)  # O(machines)
    except fr.RemoteError as e:  # O(1)
        return str(e)  # O(1)
    return fr.check(label)  # O(1)


def _not_run(case: dict, n: int, label: str, why: str, plugin: str) -> dict:  # O(1)
    return {"v": 1, "row": "golden", "case": case["id"], "attempt": n, "passed": False, "why": [f"machine {label}: {why}"], "warn": [],
            "lead_usd": 0.0, "total_usd": 0.0, "lead_turns": 0, "wall_min": 0.0, "started": False, "plugin": plugin, "machine": label}  # O(1)


def _poll(label: str, out: str, timeout_s: int, abort: threading.Event) -> tuple:  # (exit code, output) of the host script | O(p)
    end = time.monotonic() + timeout_s + SLACK_S  # O(1)
    errors = 0  # O(1)
    while True:  # O(p)
        try:  # O(1)
            res = rw.script_result(label, out)  # O(B)
            errors = 0  # O(1)
        except fr.RemoteError as e:  # O(1)
            errors += 1  # O(1)
            res = None  # O(1)
            if errors >= READ_TRIES:  # O(1)
                raise _NotRun(f"cannot read the host result: {e}") from None  # O(1)
        if res is not None:  # O(1)
            return res  # O(1)
        if abort.is_set():  # O(1)
            raise _NotRun("aborted")  # O(1)
        if time.monotonic() >= end:  # O(1)
            raise _NotRun(f"no result within {timeout_s + SLACK_S} s")  # O(1)
        abort.wait(POLL_S)  # O(1)


def _bring_patch(label: str, tree: str, row: dict, out_dir) -> None:  # the host's patch into out_dir/golden; a gap is a warning | O(B)
    name = row.get("patch")  # O(1)
    if not name:  # O(1)
        return  # O(1)
    row["patch"] = ""  # O(1)
    def warn(msg): row["warn"] = [*(row.get("warn") or []), f"no patch saved: {msg}"]  # noqa: E704 | O(1)
    if not isinstance(name, str) or name != Path(name).name or "\\" in name or not name.endswith(".patch"):  # O(1)
        warn(f"bad name {name}")  # O(1)
        return  # O(1)
    if out_dir is None:  # O(1)
        return  # O(1)
    try:  # O(1)
        data = _read_all(label, f"{tree}/.superlite/golden/{name}", PATCH_CAP)  # O(B)
    except fr.RemoteError as e:  # O(1)
        warn(f"cannot read it from {label}: {e}")  # O(1)
        return  # O(1)
    if not data:  # O(1)
        warn("it is empty or missing on the host")  # O(1)
        return  # O(1)
    d = Path(out_dir) / "golden"  # O(1)
    d.mkdir(parents=True, exist_ok=True)  # O(1)
    (d / name).write_bytes(data)  # O(B)
    row["patch"] = name  # O(1)


def attempt(label: str, case: dict, src: Path, timeout_s: int, n: int, plugin: str, out_dir, earlier: list, abort: threading.Event) -> dict:  # O(p + B)
    name = f"golden/{case['id']}-{n}-{_token()}"  # O(1)
    ref = f"refs/superlite/{name}"  # O(1)
    made = pushed = False  # O(1)
    ws = tree = None  # O(1)
    try:  # O(1)
        try:  # O(1)
            plugin_tree = _plugin_tree(label)  # O(1)
            blobs = {".superlite/golden/case.json": json.dumps(case).encode("utf-8")}  # O(1)
            tc = Path(src) / ".superlite" / "test-cmd.json"  # O(1)
            if tc.is_file():  # O(1)
                blobs[".superlite/test-cmd.json"] = tc.read_bytes()  # O(1)
            start = ra.start_commit(str(src), case.get("base", ""), [], blobs, ref)  # O(b)
            made = True  # O(1)
            tree = fr.push(label, str(src), name, start, [], PUSH_S)  # O(1)
            pushed = True  # O(1)
            g = f"{tree}/.superlite/golden"  # O(1)
            q = shlex.quote  # O(1)
            script = (f"python3 {q(f'{plugin_tree}/{SCRIPTS_REL}/golden.py')} attempt --case {q(g + '/case.json')} --n {n} --timeout {timeout_s} "
                      f"--out-dir {q(tree + '/.superlite')} --row {q(g + '/row.json')}")  # O(1)
            if earlier:  # O(1)
                script += f" --earlier {q(','.join(str(float(x)) for x in earlier))}"  # O(e)
            ws = rw.run_script(label, tree, script, f"{g}/attempt.out", f"sl:golden {case['id']}-{n}")  # O(1)
            code, text = _poll(label, f"{g}/attempt.out", timeout_s, abort)  # O(p)
            if code != 0:  # O(1)
                last = (text.strip().splitlines() or [""])[-1]  # O(1)
                raise _NotRun(f"host attempt exit {code}: {last}")  # O(1)
            try:  # O(1)
                row = json.loads(_read_all(label, f"{g}/row.json", ROW_CAP).decode("utf-8", errors="replace"))  # O(B)
                if not isinstance(row, dict):  # O(1)
                    raise ValueError("not an object")  # O(1)
            except ValueError as e:  # O(1)
                raise _NotRun(f"host row unreadable: {e}") from None  # O(1)
            row["plugin"], row["machine"] = plugin, label  # O(1)
            _bring_patch(label, tree, row, out_dir)  # O(B)
            return row  # O(1)
        except (fr.RemoteError, hc.HerdrError, RuntimeError, OSError, ValueError, KeyError) as e:  # O(1)
            return _not_run(case, n, label, str(e), plugin)  # O(1)
    finally:  # O(1)
        if ws is not None:  # O(1)
            rw.close_script(label, ws)  # O(1)
        if pushed:  # O(1)
            try:  # O(1)
                fr.drop(label, str(src), name)  # O(1)
            except fr.RemoteError as e:  # O(1)
                print(f"golden: tree {name} kept on {label}: {e}", file=sys.stderr)  # O(1)
        if made:  # O(1)
            _drop_ref(src, ref)  # O(1)
