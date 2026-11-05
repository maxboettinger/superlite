#!/usr/bin/env python3
"""Thin wrapper over the herdr CLI: JSON in and out, errors as HerdrError."""

# Complexity notation:
# n = argument count, e = env vars, k = until states, a = agents listed, p = panes of a tab
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)


class HerdrError(Exception):  # O(1)
    def __init__(self, code, message):  # O(1)
        super().__init__(f"{code}: {message}")  # O(1)
        self.code = code  # O(1)
        self.message = message  # O(1)


def _run(args, timeout_ms, env):  # O(n + output)
    exe = os.environ.get("SUPERLITE_HERDR_BIN") or "herdr"  # O(1)
    full = dict(os.environ)  # O(env)
    full.update(env or {})  # O(e)
    try:  # O(1)
        p = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=timeout_ms / 1000 + 5, env=full)  # O(n + output)
    except FileNotFoundError as e:  # O(1)
        raise HerdrError("missing", str(e))  # O(1)
    except subprocess.TimeoutExpired:  # O(1)
        raise HerdrError("timeout", f"herdr {' '.join(args[:2])} timed out")  # O(1)
    if p.returncode != 0:  # O(1)
        for text in (p.stderr, p.stdout):  # herdr 0.9.5 writes its error JSON to stderr | O(1)
            try:  # O(1)
                body = json.loads(text)  # O(output)
            except ValueError:  # O(1)
                continue  # O(1)
            err = body.get("error") if isinstance(body, dict) else None  # O(1)
            if isinstance(err, dict):  # O(1)
                raise HerdrError(str(err.get("code") or "error"), str(err.get("message", "")))  # O(1)
        raise HerdrError("exit", (p.stderr or p.stdout or "").strip())  # O(output)
    return p.stdout  # O(1)


def call(args, timeout_ms=30000, env=None):  # O(n + output)
    out = _run(args, timeout_ms, env)  # O(n + output)
    try:  # O(1)
        payload = json.loads(out)  # O(output)
    except ValueError:  # O(1)
        raise HerdrError("parse", out[:200])  # O(1)
    if not isinstance(payload, dict):  # O(1)
        raise HerdrError("parse", out[:200])  # O(1)
    if payload.get("error"):  # O(1)
        err = payload["error"]  # O(1)
        if not isinstance(err, dict):  # O(1)
            raise HerdrError("error", str(err))  # O(1)
        raise HerdrError(str(err.get("code") or "error"), str(err.get("message", "")))  # O(1)
    return payload.get("result", {})  # O(1)


def read_text(args, timeout_ms=30000, env=None):  # O(n + output)
    return _run(args, timeout_ms, env)  # O(n + output)


def _pick(r, *path):  # O(len path)
    try:  # O(1)
        for k in path:  # O(len path)
            r = r[k]  # O(1)
        return r  # O(1)
    except (KeyError, TypeError, IndexError):  # O(1)
        raise HerdrError("parse", "expected result." + ".".join(str(k) for k in path))  # O(len path)


def _env_flags(env_vars):  # O(e)
    out = []  # O(1)
    for k, v in env_vars.items():  # O(e)
        if v != "" and v is not None:  # O(1)
            out += ["--env", f"{k}={v}"]  # O(1)
    return out  # O(e)


def create_workspace(label, cwd, env_vars):  # O(e)
    r = call(["workspace", "create", "--label", label, "--cwd", cwd] + _env_flags(env_vars) + ["--no-focus"])  # O(e)
    return _pick(r, "workspace", "workspace_id"), _pick(r, "root_pane", "pane_id")  # O(1)


def create_tab(workspace_id, cwd, env_vars):  # O(e)
    r = call(["tab", "create", "--workspace", workspace_id, "--cwd", cwd] + _env_flags(env_vars) + ["--no-focus"])  # O(e)
    return _pick(r, "tab", "tab_id"), _pick(r, "root_pane", "pane_id")  # O(1)


def pane_layout(pane_id):  # O(p)
    """Panes of the tab holding `pane_id`, as [{"pane_id", "rows", "cols"}] (herdr's `rect` height and width)."""
    panes = _pick(call(["pane", "layout", "--pane", pane_id]), "layout", "panes")  # O(1)
    if not isinstance(panes, list):  # O(1)
        raise HerdrError("parse", "expected result.layout.panes to be a list")  # O(1)
    out = [{"pane_id": _pick(x, "pane_id"), "rows": _pick(x, "rect", "height"), "cols": _pick(x, "rect", "width")} for x in panes]  # O(p)
    if not all(isinstance(x["rows"], int) and isinstance(x["cols"], int) for x in out):  # a null size would crash the placement with a TypeError | O(p)
        raise HerdrError("parse", "expected integer pane sizes in result.layout.panes")  # O(1)
    return out  # O(p)


def split_pane(pane_id, direction, cwd, env_vars):  # O(e)
    r = call(["pane", "split", pane_id, "--direction", direction, "--cwd", cwd] + _env_flags(env_vars) + ["--no-focus"])  # O(e)
    return _pick(r, "pane", "pane_id")  # O(1)


def start_agent(name, pane_id, argv, timeout_ms=90000):  # O(n)
    r = call(["agent", "start", name, "--kind", "claude", "--pane", pane_id, "--timeout", str(timeout_ms), "--"] + list(argv), timeout_ms)  # O(n)
    return _pick(r, "agent", "agent_status")  # O(1)


def agent_state(name):  # O(1)
    return _pick(call(["agent", "get", name]), "agent", "agent_status")  # O(1)


def agents():  # O(a)
    """Every named agent herdr lists (name, agent_status, pane_id, cwd); an agent nobody named has no `name` and is dropped."""
    return [x for x in _pick(call(["agent", "list"]), "agents") if isinstance(x, dict) and x.get("name")]  # O(a)


def agent_states():  # O(a)
    return {x["name"]: _pick(x, "agent_status") for x in agents()}  # O(a)


def read_screen(name, lines=40, source="visible"):  # O(lines)
    return read_text(["agent", "read", name, "--source", source, "--lines", str(lines)])  # O(lines)


def _untils(until):  # O(k)
    out = []  # O(1)
    for u in until:  # O(k)
        out += ["--until", u]  # O(1)
    return out  # O(k)


def prompt(name, text, until, timeout_ms):  # O(k + len text)
    r = call(["agent", "prompt", name, text, "--wait"] + _untils(until) + ["--timeout", str(timeout_ms)], timeout_ms)  # O(k + len text)
    return _pick(r, "agent", "agent_status")  # O(1)


def send_keys(name, keys):  # O(len keys)
    call(["agent", "send-keys", name] + list(keys))  # O(len keys)


def wait_state(name, until, timeout_ms):  # O(k)
    r = call(["agent", "wait", name] + _untils(until) + ["--timeout", str(timeout_ms)], timeout_ms)  # O(k)
    return _pick(r, "agent", "agent_status")  # O(1)


def exit_agent(name):  # a bare --timeout needs --wait in herdr 0.9.5, so send /exit plain, then wait for the agent to go | O(1)
    call(["agent", "prompt", name, "/exit"])  # only a failed prompt raises | O(1)
    try:  # O(1)
        wait_state(name, ["unknown"], 10000)  # O(1)
    except HerdrError:  # the agent already gone, or never reported unknown: the caller closes the pane next | O(1)
        pass  # O(1)


def run_in_pane(pane_id, command):  # O(len command): types `command` into the pane's shell and runs it; raw stdout, the reply shape is not pinned
    return read_text(["pane", "run", pane_id, command])  # O(len command)


def close_pane(pane_id):  # O(1)
    call(["pane", "close", pane_id])  # O(1)


def close_workspace(workspace_id):  # O(1)
    call(["workspace", "close", workspace_id])  # O(1)
