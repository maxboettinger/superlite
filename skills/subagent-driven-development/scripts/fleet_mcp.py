#!/usr/bin/env python3
"""MCP servers a fleet worker keeps (#576).

A fleet worker starts lean (`--strict-mcp-config`); implementers, fixers and package reviewers get the servers their project names
(test-cmd.json "mcp"), else the stack default (an Xcode project gets `xcode`), through a generated `--mcp-config` file.
Library: servers, write_config, deny, usage_note. Stdlib only.
"""
# Complexity notation:
#   n = server names, f = size of the config files read, k = servers written
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

import testcmd  # O(1)

MCP_ROLES = ("implementer", "fixer", "package-reviewer")  # O(1)
XCODE = {"type": "stdio", "command": "xcrun", "args": ["mcpbridge"]}  # O(1)
BUILTIN = {"xcode": XCODE}  # O(1)
XCODE_DENY = ("mcp__xcode__XcodeOpenWorkspace", "mcp__xcode__XcodeCloseWorkspace")  # O(1)
BAD_MCP = 'test-cmd.json "mcp" must be a list of server names; ignored'  # O(1)
XCODE_NOTE = ("Xcode MCP tools (mcp__xcode__...) are connected. After each edit of a Swift file run XcodeRefreshCodeIssuesInFile on it "
              "and fix what it reports. Render every Preview you add or change with RenderPreview before you report DONE. "
              "Look up Apple APIs with DocumentationSearch. Only the coordinator opens or closes an Xcode workspace; "
              "if none is open for this project, say so in your report instead of opening one.")  # O(1)


def _load(path) -> dict:  # a JSON object from path, {} when missing, unreadable or not an object | O(f)
    try:  # O(1)
        d = json.loads(Path(path).read_text(encoding="utf-8"))  # O(f)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return d if isinstance(d, dict) else {}  # O(1)


def _names(project: Path) -> list:  # server names from test-cmd.json "mcp", else the stack default | O(n + f)
    cfg, _, _ = testcmd.config_source(project)  # O(f)
    if isinstance(cfg, dict) and "mcp" in cfg:  # O(1)
        v = cfg["mcp"]  # O(1)
        if isinstance(v, list) and all(isinstance(x, str) for x in v):  # O(n)
            out = []  # O(1)
            for x in (s.strip() for s in v):  # O(n)
                if x and x not in out:  # O(n)
                    out.append(x)  # O(1)
            return out  # O(1)
        print(BAD_MCP, file=sys.stderr)  # O(1)
    if sys.platform != "darwin":  # O(1)
        return []  # O(1)
    swift = isinstance(cfg, dict) and cfg.get("language") == "swift"  # O(1)
    try:  # O(1)
        xc = any(q.name.endswith((".xcodeproj", ".xcworkspace")) for q in project.iterdir())  # O(entries)
    except OSError:  # O(1)
        xc = False  # O(1)
    return ["xcode"] if swift or xc else []  # O(1)


def _main_key(project: Path):  # the main checkout's path when project is a linked worktree, else None | O(1)
    try:  # O(1)
        out = subprocess.run(["git", "-C", str(project), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                             capture_output=True, text=True, timeout=10)  # O(1)
        common = Path(out.stdout.strip())  # O(1)
        if out.returncode != 0 or not out.stdout.strip() or common.name != ".git":  # O(1)
            return None  # O(1)
        main = common.parent.resolve()  # O(1)
    except (OSError, ValueError, subprocess.SubprocessError):  # O(1)
        return None  # O(1)
    return None if main == project else main  # O(1)


def _scope(cj: dict, key) -> dict:  # the mcpServers of one project entry in .claude.json | O(1)
    projects = cj.get("projects")  # O(1)
    entry = projects.get(str(key)) if isinstance(projects, dict) else None  # O(1)
    ms = entry.get("mcpServers") if isinstance(entry, dict) else None  # O(1)
    return ms if isinstance(ms, dict) else {}  # O(1)


def servers(role: str, project, claude_json) -> tuple[dict, list[str]]:  # (name -> definition kept for role, notes for names left out) | O(n + f)
    if role not in MCP_ROLES:  # O(1)
        return {}, []  # O(1)
    return named(_names(Path(project)), project, claude_json)  # O(n + f)


def named(names: list, project, claude_json) -> tuple:  # (name -> definition for the given names, notes for names left out) | O(n + f)
    project = Path(project)  # O(1)
    resolved = project.resolve()  # O(1)
    cj = _load(claude_json) if claude_json else {}  # O(f)
    main = _main_key(resolved)  # O(1)
    layers = [_scope(cj, resolved)]  # O(1)
    if main is not None:  # O(1)
        layers.append(_scope(cj, main))  # O(1)
    ms = _load(project / ".mcp.json").get("mcpServers")  # O(f)
    layers.append(ms if isinstance(ms, dict) else {})  # O(1)
    us = cj.get("mcpServers")  # O(1)
    layers.append(us if isinstance(us, dict) else {})  # O(1)
    layers.append(BUILTIN)  # O(1)
    kept, notes = {}, []  # O(1)
    for name in names:  # O(n)
        d = next((layer[name] for layer in layers if isinstance(layer.get(name), dict)), None)  # O(1)
        if d is None:  # O(1)
            notes.append(f"mcp: {name} left out: no definition in {project}/.mcp.json, {claude_json} or the built-in list")  # O(1)
        else:  # O(1)
            kept[name] = d  # O(1)
    return kept, notes  # O(1)


def write_config(sd, servers: dict):  # <sd>/fleet/mcp-<hash>.json for the servers, None when there are none | O(k)
    if not servers:  # O(1)
        return None  # O(1)
    body = json.dumps({"mcpServers": servers}, sort_keys=True, indent=2)  # O(k)
    path = Path(sd) / "fleet" / f"mcp-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:10]}.json"  # O(k)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")  # a reader never sees a half-written file while workers spawn together | O(1)
    tmp.write_text(body + "\n", encoding="utf-8")  # O(k)
    os.replace(tmp, path)  # O(1)
    return path  # O(1)


def deny(names: list[str]) -> list[str]:  # tools the worker must not call | O(n)
    return list(XCODE_DENY) if "xcode" in names else []  # O(n)


def usage_note(names: list[str]) -> str:  # the usage rules for --append-system-prompt | O(n)
    return XCODE_NOTE if "xcode" in names else ""  # O(n)
