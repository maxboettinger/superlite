#!/usr/bin/env python3
"""Named run configs (#681): lead model, effort, autocompact window, cache TTL, denied tools, MCP servers, worker models.

    run_config.py show [--config NAME] [--project P]
    run_config.py list [--project P]

Three layers, later wins per key: built-in config/run-configs.json, machine $SUPERLITE_HOME/run-configs.json,
project <P>/.superlite/run-configs.json. A run's active config is the snapshot <state dir>/run-config.json.
Library: ConfigError, load_text, resolve, write_active, active. Stdlib only.
"""
# Complexity notation:
#   k = keys in a config, c = configs in a file, L = file size
import argparse  # O(1)
import copy  # O(1)
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

BUILTIN = Path(__file__).resolve().parent.parent / "config" / "run-configs.json"  # O(1)
EFFORTS = ("low", "medium", "high", "xhigh", "max")  # O(1)
VARIANTS = ("default",)  # lead brief text ids | O(1)
TTLS = (None, "5m", "1h")  # O(1)
ROLES = ("implementer", "fixer", "package-reviewer", "final-reviewer", "research", "checker", "writer")  # O(1)
SECTIONS = ("lead", "cache_ttl", "workers")  # O(1)
LEAD_KEYS = ("model", "effort", "autocompact", "deny", "mcp", "text")  # O(1)


class ConfigError(ValueError):  # O(1)
    pass  # O(1)


def _bad(src, name, where, why):  # O(1)
    raise ConfigError(f"{src}: {name}: {where}: {why}")  # O(1)


def _strs(v) -> bool:  # O(k)
    return isinstance(v, list) and all(isinstance(s, str) and s for s in v)  # O(k)


def _lead(src, name, lead):  # O(k)
    for k, v in lead.items():  # O(k)
        w = f"lead.{k}"  # O(1)
        if k not in LEAD_KEYS:  # O(1)
            _bad(src, name, "lead", f"unknown key {k}")  # O(1)
        if k == "model" and not (isinstance(v, str) and v and not any(ch.isspace() for ch in v)):  # O(len)
            _bad(src, name, w, "must be a non-empty string without whitespace")  # O(1)
        elif k == "effort" and v not in EFFORTS:  # O(1)
            _bad(src, name, w, f"{v} is not one of {', '.join(EFFORTS)}")  # O(1)
        elif k == "autocompact" and v is not None and (isinstance(v, bool) or not isinstance(v, int) or not 100000 <= v <= 1000000):  # O(1)
            _bad(src, name, w, f"{v} must be null or an integer from 100000 to 1000000")  # O(1)
        elif k == "deny" and not _strs(v):  # O(k)
            _bad(src, name, w, "must be a list of non-empty strings")  # O(k)
        elif k == "mcp" and v != "project" and not _strs(v):  # O(k)
            _bad(src, name, w, 'must be "project" or a list of non-empty strings')  # O(k)
        elif k == "text" and v not in VARIANTS:  # O(1)
            _bad(src, name, w, f"{v} is not one of {', '.join(VARIANTS)}")  # O(1)


def _check(src, name, cfg):  # O(k)
    if not isinstance(cfg, dict):  # O(1)
        _bad(src, name, "config", "not an object")  # O(1)
    for sec, val in cfg.items():  # O(k)
        if sec not in SECTIONS:  # O(1)
            _bad(src, name, "config", f"unknown key {sec}")  # O(1)
        if not isinstance(val, dict):  # O(1)
            _bad(src, name, sec, "not an object")  # O(1)
    _lead(src, name, cfg.get("lead", {}))  # O(k)
    for k, v in cfg.get("cache_ttl", {}).items():  # O(k)
        if k not in ("lead", "workers"):  # O(1)
            _bad(src, name, "cache_ttl", f"unknown key {k}")  # O(1)
        if v not in TTLS:  # O(1)
            _bad(src, name, f"cache_ttl.{k}", f"{v} is not one of null, 5m, 1h")  # O(1)
    for k, v in cfg.get("workers", {}).items():  # O(k)
        if k not in ROLES:  # O(1)
            _bad(src, name, "workers", f"unknown key {k}")  # O(1)
        if v is not None and not (isinstance(v, str) and v and not any(ch.isspace() for ch in v)):  # O(len)
            _bad(src, name, f"workers.{k}", "must be null or a model string")  # O(1)


def load_text(text: str, source: str = "<text>") -> dict:  # O(L)
    try:  # O(1)
        data = json.loads(text)  # O(L)
    except ValueError as e:  # O(1)
        raise ConfigError(f"{source}: invalid JSON: {e}") from None  # O(1)
    if not isinstance(data, dict):  # O(1)
        raise ConfigError(f"{source}: not a JSON object")  # O(1)
    d = data.get("default")  # O(1)
    if d is not None and not isinstance(d, str):  # O(1)
        raise ConfigError(f"{source}: default: must be a string or null")  # O(1)
    cfgs = data.get("configs", {})  # O(1)
    if not isinstance(cfgs, dict):  # O(1)
        raise ConfigError(f"{source}: configs: not an object")  # O(1)
    for name, cfg in cfgs.items():  # O(c*k)
        _check(source, name, cfg)  # O(k)
    return {"default": d, "configs": cfgs}  # O(1)


def _read(path, source) -> dict:  # O(L)
    try:  # O(1)
        text = Path(path).read_text(encoding="utf-8")  # O(L)
    except FileNotFoundError:  # O(1)
        return {"default": None, "configs": {}}  # O(1)
    except OSError as e:  # O(1)
        raise ConfigError(f"{source}: unreadable: {e}") from None  # O(1)
    return load_text(text, str(path))  # O(L)


def _layers(project, only_builtin=False) -> list:  # O(L)
    out = [("builtin", _read(BUILTIN, "builtin"))]  # O(L)
    if only_builtin:  # O(1)
        return out  # O(1)
    home = Path(os.environ.get("SUPERLITE_HOME") or Path.home() / ".superlite")  # O(1)
    out.append(("machine", _read(home / "run-configs.json", "machine")))  # O(L)
    if project:  # O(1)
        out.append(("project", _read(Path(project) / ".superlite" / "run-configs.json", "project")))  # O(L)
    return out  # O(1)


def _id(name, cfg) -> str:  # O(k)
    body = json.dumps({s: cfg[s] for s in SECTIONS}, sort_keys=True, separators=(",", ":"))  # O(k)
    return f"{name}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:8]}"  # O(k)


def _resolve(layers, name, overrides) -> dict:  # O(L)
    known = sorted({n for _, d in layers for n in d["configs"]})  # O(c)
    if name is None:  # O(1)
        name = next((d["default"] for _, d in reversed(layers) if d["default"]), "default")  # O(1)
    if name not in known:  # O(1)
        raise ConfigError(f"run config {name}: not defined; known: {', '.join(known)}")  # O(c)
    cfg = copy.deepcopy(layers[0][1]["configs"].get("default", {}))  # O(k)
    for sec in SECTIONS:  # O(1)
        cfg.setdefault(sec, {})  # O(1)
    sources = []  # O(1)
    for src, d in layers:  # O(1)
        if name in d["configs"]:  # O(1)
            sources.append(src)  # O(1)
            for sec, val in copy.deepcopy(d["configs"][name]).items():  # O(k)
                cfg[sec].update(val)  # O(k)
    for sec, val in copy.deepcopy(overrides or {}).items():  # O(k)
        if sec not in SECTIONS or not isinstance(val, dict):  # O(1)
            raise ConfigError(f"run config {name}: bad override {sec}")  # O(1)
        cfg[sec].update(val)  # O(k)
    _check("merged", name, cfg)  # O(k)
    return {"name": name, "id": _id(name, cfg), "sources": sources, **cfg}  # O(k)


def resolve(name: str | None = None, project: str | Path | None = None, overrides: dict | None = None) -> dict:  # O(L)
    return _resolve(_layers(project), name, overrides)  # O(L)


def write_active(sd: str | Path, cfg: dict) -> Path:  # O(k)
    dest = Path(sd) / "run-config.json"  # O(1)
    dest.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = dest.with_name(f"run-config.json.{os.getpid()}.tmp")  # O(1)
    tmp.write_text(json.dumps(cfg, indent=1, sort_keys=True), encoding="utf-8")  # O(k)
    os.replace(tmp, dest)  # O(1)
    return dest  # O(1)


def active(sd: str | Path, project: str | Path | None = None) -> dict:  # O(L)
    snap = Path(sd) / "run-config.json"  # O(1)
    if snap.exists():  # O(1)
        try:  # O(1)
            cfg = json.loads(snap.read_text(encoding="utf-8"))  # O(k)
            if isinstance(cfg, dict) and all(isinstance(cfg.get(s), dict) for s in SECTIONS) and cfg.get("id"):  # O(1)
                return cfg  # O(1)
            raise ValueError("not a run config snapshot")  # O(1)
        except (OSError, ValueError) as e:  # O(1)
            print(f"run config: {snap}: {e}; using the default", file=sys.stderr)  # O(1)
            return _resolve(_layers(None, True), None, None)  # O(L)
    try:  # O(1)
        return resolve(None, project)  # O(L)
    except ConfigError as e:  # O(1)
        print(f"run config: {e}; using the built-in default", file=sys.stderr)  # O(1)
        return _resolve(_layers(None, True), None, None)  # O(L)


def main(argv=None) -> int:  # O(L)
    ap = argparse.ArgumentParser(prog="run_config.py")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("show")  # O(1)
    s.add_argument("--config")  # O(1)
    s.add_argument("--project")  # O(1)
    ls = sub.add_parser("list")  # O(1)
    ls.add_argument("--project")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    try:  # O(1)
        if a.cmd == "show":  # O(1)
            print(json.dumps(resolve(a.config, a.project), indent=1, sort_keys=True))  # O(k)
            return 0  # O(1)
        layers = _layers(a.project)  # O(L)
        names = sorted({n for _, d in layers for n in d["configs"]})  # O(c)
        for n in names:  # O(c)
            print(n, ",".join(src for src, d in layers if n in d["configs"]))  # O(1)
        print("default:", _resolve(layers, None, None)["name"])  # O(L)
        return 0  # O(1)
    except ConfigError as e:  # O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
