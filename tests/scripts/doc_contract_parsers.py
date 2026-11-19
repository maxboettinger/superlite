"""Parser trees of every superlite tool, captured in one child Python (doc contract test helper).

parser_trees() -> {"tools": {name: node | None}, "errors": {name: "ExcType: message"}}
A node is {"flags": [option strings, sorted], "choices": {"--flag": [choices]}, "subs": {name: node}}.
Run as a script this module captures every tool and prints that JSON.
"""
from __future__ import annotations

import argparse
import ast
import functools
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1] / "skills" / "subagent-driven-development"
SCRIPT_DIRS = [SKILL / "scripts", SKILL / "probes"]


def _tuple_const(path: Path, name: str) -> tuple:
    """A module-level tuple of strings, read from the source without importing it."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise LookupError(f"{name} not found in {path}")


def _build_routes() -> dict:
    scripts = SKILL / "scripts"
    routes = {}
    for sub in ("send", "keys", "wait"):
        routes[("fleet", sub)] = ("fleet_io", "main")
    routes[("fleet", "run")] = ("fleet_layer", "main")
    routes[("fleet", "restore")] = ("fleet_restore", "main")
    routes[("fleet", "resume")] = ("fleet_resume", "main")
    for sub in _tuple_const(scripts / "backlog.py", "ROUTED"):
        # backlog._start reads the repository state before it parses; its parser is backlog_run's "start" one
        routes[("backlog", sub)] = ("backlog_run", "main")
    routes[("backlog", "ship")] = ("backlog_ship", "main")
    routes[("backlog", "notes")] = ("backlog_ship", "main")
    for sub in _tuple_const(scripts / "plan_tools.py", "REVIEW_COMMANDS"):
        routes[("plan_tools", sub)] = ("pt_review", "main")
    routes[("routing", "miss")] = ("routing", "miss")
    return routes


ROUTES: dict[tuple[str, str], tuple[str, str]] = _build_routes()


# flags a hand-written wrapper strips before argparse runs
HAND_FLAGS = {("backlog", "start"): ["--note"]}  # stripped by backlog._start before argparse


def _tool_files() -> dict:
    tools = {}
    for d in SCRIPT_DIRS:
        for p in sorted(d.glob("*.py")):
            if p.name.startswith("_"):
                continue
            if 'if __name__ == "__main__"' in p.read_text(encoding="utf-8", errors="replace"):
                tools[p.stem] = p
    return tools


def _node(parser) -> dict:
    flags, choices, subs = set(), {}, {}
    for act in parser._actions:
        if isinstance(act, argparse._SubParsersAction):
            for name, sp in act.choices.items():
                subs[name] = _node(sp)
            continue
        flags.update(act.option_strings)
        if act.option_strings and act.choices is not None:
            for opt in act.option_strings:
                choices[opt] = [str(c) for c in act.choices]
    return {"flags": sorted(flags), "choices": choices, "subs": subs}


class _Recorder:
    """Patch ArgumentParser.parse_known_args to record each parser, restore on exit."""

    def __enter__(self):
        self.parsers = []
        self.orig = argparse.ArgumentParser.parse_known_args
        rec = self

        def patched(self, *a, **k):
            rec.parsers.append(self)
            return rec.orig(self, *a, **k)

        argparse.ArgumentParser.parse_known_args = patched
        return self

    def __exit__(self, *exc):
        argparse.ArgumentParser.parse_known_args = self.orig
        return False


def _isolated(fn):
    """Run fn with argv, sys.path, cwd and streams restored afterwards; SystemExit is swallowed."""
    argv, path, cwd = list(sys.argv), list(sys.path), os.getcwd()
    out, err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        try:
            fn()
        except SystemExit:
            pass
    finally:
        sys.stdout, sys.stderr = out, err
        sys.argv[:] = argv
        sys.path[:] = path
        os.chdir(cwd)


def _capture_tool(path: Path):
    with _Recorder() as rec:
        sys.argv = [str(path), "--help"]
        sys.path[:0] = [str(d) for d in SCRIPT_DIRS]
        _isolated(lambda: runpy.run_path(str(path), run_name="__main__"))
    return rec.parsers[-1] if rec.parsers else None


def _capture_route(tool: str, sub: str, module: str, func: str):
    import importlib

    result = {}

    def call():
        mod = importlib.import_module(module)
        sys.argv = [module, "--help"]
        getattr(mod, func)(["--help"])

    with _Recorder() as rec:
        sys.path[:0] = [str(d) for d in SCRIPT_DIRS]
        _isolated(call)
    if not rec.parsers:
        return None
    top = _node(rec.parsers[-1])
    return top["subs"].get(sub, top)


def _capture_all() -> dict:
    tools, errors = {}, {}
    files = _tool_files()
    for name, path in files.items():
        try:
            parser = _capture_tool(path)
            tools[name] = _node(parser) if parser is not None else None
        except Exception as e:  # one tool's failure never stops the others
            tools[name] = None
            errors[name] = f"{type(e).__name__}: {e}"
    tools["version"] = {"flags": [], "choices": {}, "subs": {}}
    for (tool, sub), (module, func) in ROUTES.items():
        node = tools.get(tool)
        if node is None:
            continue
        try:
            routed = _capture_route(tool, sub, module, func)
            if routed is not None:
                routed["flags"] = sorted(set(routed["flags"]) | set(HAND_FLAGS.get((tool, sub), [])))
                node["subs"][sub] = routed
        except Exception as e:
            errors[f"{tool} {sub}"] = f"{type(e).__name__}: {e}"
    return {"tools": tools, "errors": errors}


def capture_uncached() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "HOME": tmp, "XDG_CACHE_HOME": tmp, "SUPERLITE_CACHE_DIR": tmp, "PYTHONUTF8": "1"}
        env.pop("SUPERLITE_SL", None)
        r = subprocess.run([sys.executable, str(Path(__file__).resolve())], cwd=tmp, env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"parser capture failed: {r.stderr[-500:]}")
    return json.loads(r.stdout)


@functools.lru_cache(maxsize=None)
def parser_trees() -> dict:
    return capture_uncached()


if __name__ == "__main__":
    real = sys.stdout
    data = _capture_all()
    real.write(json.dumps(data))
    real.flush()
