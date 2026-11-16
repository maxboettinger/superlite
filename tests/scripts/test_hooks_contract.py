"""One contract for every hook both manifests register (#846): a valid event and matcher, LF endings,
`bash -n`, and fail-open on malformed stdin. A hook that must block on one of those inputs is listed in
`FAIL_CLOSED` with its reason; a hook that talks on stdout in every run is listed in `TALKS`.

The cases come from hooks/hooks.json and hooks/hooks-cursor.json, so a new entry is checked without
editing this file. deny-worker-permission and capture-worker-stop act only with SUPERLITE_FLEET_WORKER
set and final-review-check only inside a git repository; the runs here are outside both."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
needs_bash = pytest.mark.skipif(not BASH, reason="bash not available")

CLAUDE_EVENTS = {"SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                 "PostToolUseFailure", "PermissionRequest", "Notification", "Stop", "SubagentStart",
                 "SubagentStop", "PreCompact"}
TOOLS = {"Bash", "PowerShell", "Monitor", "Edit", "Write", "NotebookEdit", "MultiEdit", "Agent", "Task",
         "Skill", "Read", "Grep", "Glob", "WebFetch", "WebSearch", "TodoWrite", "AskUserQuestion",
         "ExitPlanMode"}
MATCHER_WORDS = {"SessionStart": {"startup", "resume", "clear", "compact"}, "PreCompact": {"manual", "auto"},
                 **{e: TOOLS for e in ("PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest")}}
CURSOR_EVENTS = {"sessionStart", "sessionEnd", "beforeShellExecution", "afterShellExecution",
                 "beforeMCPExecution", "afterMCPExecution", "beforeReadFile", "afterFileEdit",
                 "beforeSubmitPrompt", "afterAgentResponse", "afterAgentThought", "stop", "preToolUse",
                 "postToolUse", "postToolUseFailure", "subagentStart", "subagentStop", "preCompact"}
COMMAND = {"claude": re.compile(r'bash "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/([\w-]+)"'),
           "cursor": re.compile(r"bash \./hooks/([\w-]+)")}
PLUGIN_ROOT_VAR = {"claude": "CLAUDE_PLUGIN_ROOT", "cursor": "CURSOR_PLUGIN_ROOT"}


class Hook(NamedTuple):
    host: str
    event: str
    matcher: str | None
    entry: dict

    @property
    def script(self) -> str | None:
        m = COMMAND[self.host].fullmatch(str(self.entry.get("command")))
        return m.group(1) if m else None


def registered(manifest: Path) -> list[Hook]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    found = []
    if "version" in data:  # Cursor: {event: [{command}]}
        for event, entries in data["hooks"].items():
            found += [Hook("cursor", event, e.get("matcher"), e) for e in entries]
    else:  # Claude: {event: [{matcher?, hooks: [{...}]}]}
        for event, groups in data["hooks"].items():
            for g in groups:
                found += [Hook("claude", event, g.get("matcher"), h) for h in g["hooks"]]
    return found


def entry_problems(hook: Hook, hooks_dir: Path = HOOKS) -> list[str]:
    out = []
    known = CLAUDE_EVENTS if hook.host == "claude" else CURSOR_EVENTS
    if hook.event not in known:
        return [f"unknown {hook.host} event {hook.event}"]
    cmd = hook.entry.get("command")
    if hook.script is None:
        out.append(f"command {cmd!r} does not run a hooks/ script")
    elif not (hooks_dir / hook.script).is_file():
        out.append(f"hooks/{hook.script} missing")
    if hook.matcher is not None:
        words = MATCHER_WORDS.get(hook.event) if hook.host == "claude" else None
        if words is None:
            out.append(f"{hook.event} takes no matcher")
        else:
            bad = [a for a in hook.matcher.split("|") if a not in words]
            if bad:
                out.append(f"{hook.event} matcher {hook.matcher!r}: {', '.join(bad)} not allowed")
    if hook.host == "claude":
        e = hook.entry
        if e.get("type") != "command":
            out.append(f"type {e.get('type')!r} is not command")
        if "shell" in e and e["shell"] != "bash":
            out.append(f"shell {e['shell']!r} is not bash")
        if "async" in e and not isinstance(e["async"], bool):
            out.append(f"async {e['async']!r} is not a boolean")
    return out


def has_cr(path: Path) -> bool:
    return b"\r" in path.read_bytes()


STATES = {
    "gate": {"orchestrator.json": {"mode": "human", "approved": False}},
    "run": {"orchestrator.json": {"mode": "ai", "approved": True}, "stable.json": {}},
}


def project(tmp_path: Path, state: str) -> Path:
    (tmp_path / "home").mkdir(exist_ok=True)
    proj = tmp_path / "proj"
    (proj / ".superlite").mkdir(parents=True, exist_ok=True)
    for name, data in STATES[state].items():
        (proj / ".superlite" / name).write_text(json.dumps(data), encoding="utf-8")
    return proj


def run_hook(script: Path, raw: str, project: Path, host: str = "claude") -> subprocess.CompletedProcess:
    drop = ("SUPERLITE_FLEET_", "CLAUDE_", "CURSOR_", "SUPERLITE_STATE_DIR", "SUPERLITE_FINAL_REVIEW")
    env = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
    env.update({"HOME": str(project.parent / "home"), "CLAUDE_PROJECT_DIR": str(project),
                PLUGIN_ROOT_VAR[host]: str(script.parent.parent)})
    return subprocess.run([BASH, str(script)], input=raw, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=project, env=env, timeout=60)


def _decision(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("decision", "permissionDecision", "behavior") and v in ("block", "deny"):
                return v
            if k == "continue" and v is False:
                return "continue: false"
            found = _decision(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _decision(v)
            if found:
                return found
    return None


def _stdout_decision(r):
    try:
        return _decision(json.loads(r.stdout))
    except ValueError:
        return None


def blocks(r) -> bool:
    return r.returncode == 2 or _stdout_decision(r) is not None


def run_problems(r, talks: bool) -> list[str]:
    out = []
    if r.returncode != 0:
        out.append(f"exit {r.returncode}")
    if (d := _stdout_decision(r)) is not None:
        out.append(f"stdout decision {d}")
    if r.stdout and not talks:
        out.append(f"stdout {r.stdout[:200]!r}")
    if r.stderr:
        out.append(f"stderr {r.stderr[:200]!r}")
    return out


def test_contract_catches_a_crlf_hook_and_a_crash_on_empty_stdin(tmp_path):
    hooks = tmp_path / "plugin" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "good").write_bytes(b"#!/usr/bin/env bash\nIFS= read -r -d '' input\nexit 0\n")
    (hooks / "crlf").write_bytes(b"#!/usr/bin/env bash\r\nexit 0\r\n")
    (hooks / "crash").write_bytes(b"#!/usr/bin/env bash\nset -e\nIFS= read -r -d '' input\nexit 0\n")
    cmd = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/%s"'
    data = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "shell": "bash", "command": cmd % n}
                                                                    for n in ("good", "crlf", "crash")]}]}}
    (hooks / "hooks.json").write_text(json.dumps(data), encoding="utf-8")
    found = registered(hooks / "hooks.json")
    assert [h.script for h in found] == ["good", "crlf", "crash"]
    assert [entry_problems(h, hooks) for h in found] == [[], [], []]
    assert [h.script for h in found if has_cr(hooks / h.script)] == ["crlf"]
    if BASH:
        proj = project(tmp_path, "gate")
        assert run_problems(run_hook(hooks / "good", "", proj), talks=False) == []
        assert run_problems(run_hook(hooks / "crash", "", proj), talks=False) == ["exit 1"]


def test_contract_rejects_a_bad_event_matcher_or_command(tmp_path):
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "ok").write_text("exit 0\n", encoding="utf-8")
    ok = {"type": "command", "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/ok"'}
    data = {"hooks": {
        "PreToolUs": [{"matcher": "Bash", "hooks": [ok]}],
        "PreToolUse": [{"matcher": "Bash|Bsh", "hooks": [ok]},
                       {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 x.py"}]},
                       {"matcher": "Bash", "hooks": [{"type": "command", "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gone"'}]}],
        "Stop": [{"matcher": "x", "hooks": [ok]}],
    }}
    (hooks / "hooks.json").write_text(json.dumps(data), encoding="utf-8")
    got = [entry_problems(h, hooks) for h in registered(hooks / "hooks.json")]
    assert [len(p) for p in got] == [1, 1, 1, 1, 1], got
    for problems, needle in zip(got, ("unknown claude event PreToolUs", "Bsh", "does not run a hooks/ script",
                                      "hooks/gone missing", "Stop takes no matcher")):
        assert needle in problems[0], (needle, problems)
    (hooks / "hooks-cursor.json").write_text(json.dumps({"version": 1, "hooks": {"sesionStart": [{"command": "bash ./hooks/ok"}]}}),
                                              encoding="utf-8")
    [cursor] = registered(hooks / "hooks-cursor.json")
    assert cursor.host == "cursor" and cursor.script == "ok"
    assert entry_problems(cursor, hooks) == ["unknown cursor event sesionStart"]


CLAUDE = registered(HOOKS / "hooks.json")
CURSOR = registered(HOOKS / "hooks-cursor.json")
HOOK_FILES = sorted(p for p in HOOKS.iterdir() if p.is_file() and p.suffix != ".json")


def test_manifests_register_hooks():
    assert CLAUDE
    assert ("cursor", "session-start") in {(h.host, h.script) for h in CURSOR}
    assert json.loads((HOOKS / "hooks-cursor.json").read_text(encoding="utf-8"))["version"] == 1


@pytest.mark.parametrize("hook", CLAUDE + CURSOR, ids=lambda h: f"{h.host}-{h.event}-{h.script}")
def test_manifest_entry_is_valid(hook):
    assert entry_problems(hook) == []


@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda p: p.name)
def test_hook_files_have_lf_endings(path):
    assert not has_cr(path), f"{path.name} has CR bytes"


@needs_bash
@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda p: p.name)
def test_hook_files_parse_under_bash(path):
    r = subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _tool(name, tool_input=None, **extra):
    return json.dumps({"tool_name": name, **({} if tool_input is None else {"tool_input": tool_input}), **extra})


MALFORMED = {
    "empty": "",
    "not-json": "not json",
    "brace-not-json": "{not json",
    "garbage": "garbage {{{",
    "empty-object": "{}",
    "empty-array": "[]",
    "open-brace": "{",
    "truncated": '{"tool_name": "Bash", "tool_input": {"command": "pk',
    "truncated-agent": '{"tool_name":"Agent"',
    "no-tool-name": json.dumps({"tool_input": {"command": "ls"}}),
    "no-tool-input-bash": _tool("Bash"),
    "no-tool-input-agent": _tool("Agent"),
    "edit-empty-input": _tool("Edit", {}),
    "bash-command-int": _tool("Bash", {"command": 5}),
    "agent-id-int": '{"agent_id": 5}',
    "prompt-int": '{"prompt": 5}',
    "prompt-cwd-only": '{"cwd": "x"}',
    "null-fields": json.dumps({"tool_name": None, "tool_input": None, "cwd": None}),
    "unknown-tool": _tool("Frobnicate", {"x": 1}),
    "binary": "\x01\x02\x7f" * 50,
    "big-write": _tool("Write", {"file_path": "docs/a.md", "content": "x" * 1_000_000}),
    "big-prompt": json.dumps({"prompt": "x" * 1_000_000}),
    "session-id-traversal": json.dumps({"session_id": "../../etc", "prompt": "hi"}),
    "stop-fields-wrong-type": json.dumps({"stop_hook_active": "yes", "transcript_path": 5, "agent_type": 5}),
    "permission-no-input": json.dumps({"hook_event_name": "PermissionRequest", "tool_name": "Bash"}),
}

# (script, state, input): must block, with the reason. Asserted, never skipped.
FAIL_CLOSED = {
    ("block-coordinator-edits", "gate", "truncated-agent"):
        "an Agent call with no subagent_type is general-purpose, which the human gate denies by design",
    ("block-coordinator-edits", "gate", "no-tool-input-agent"):
        "an Agent call with no subagent_type is general-purpose, which the human gate denies by design",
    ("block-coordinator-edits", "gate", "big-write"):
        "a well-formed Write outside the review plan while the human gate is unapproved; the human gate "
        "denies it by design (the run state still checks that the 1 MB input fails open)",
}
# script: why it prints on stdout in every run.
TALKS = {
    "session-start": "injects the intro JSON",
    "pre-compact": "prints the plain-text compaction instructions in any run",
}

SESSION_START_INPUTS = ("empty", "garbage", "binary")
SCRIPTS = sorted({(h.host, h.script) for h in CLAUDE + CURSOR if h.script})
CASES = [pytest.param(host, script, state, name, id=f"{host}-{script}-{state}-{name}")
         for host, script in SCRIPTS for state in STATES for name in MALFORMED
         if script != "session-start" or name in SESSION_START_INPUTS]


@needs_bash
@pytest.mark.parametrize("host,script,state,name", CASES)
def test_fails_open(host, script, state, name, tmp_path):
    proj = project(tmp_path, state)
    r = run_hook(HOOKS / script, MALFORMED[name], proj, host)
    if (script, state, name) in FAIL_CLOSED:
        assert blocks(r), (script, state, name, FAIL_CLOSED[(script, state, name)], r.returncode, r.stdout[:200])
    else:
        assert run_problems(r, script in TALKS) == [], (script, state, name, r.stdout[:300], r.stderr[:300])
    for log in (proj / ".superlite").glob("*.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            json.loads(line)


def test_fail_closed_cases_are_real():
    scripts = {s for _h, s in SCRIPTS}
    for script, state, name in FAIL_CLOSED:
        assert script in scripts and state in STATES and name in MALFORMED, (script, state, name)
    assert set(TALKS) <= scripts


# --- telemetry (#933): a hook's telemetry write never changes its exit code, stdout or stderr ---
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import telemetry  # noqa: E402

VALID = {
    "bash": _tool("Bash", {"command": "ls"}, session_id="s1", cwd="/tmp"),
    "edit": _tool("Edit", {"file_path": "docs/a.md"}, session_id="s1", cwd="/tmp"),
    "skill": _tool("Skill", {"skill": "x"}, session_id="s1"),
    "agent": json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "worker", "description": "d"},
                         "session_id": "s1", "cwd": "/tmp"}),
    "stop": json.dumps({"session_id": "s1", "agent_id": "a1", "agent_type": "worker", "cwd": "/tmp"}),
    "prompt": json.dumps({"session_id": "s1", "prompt": "hi", "cwd": "/tmp"}),
    "permission": json.dumps({"hook_event_name": "PermissionRequest", "tool_name": "Bash", "session_id": "s1",
                              "tool_input": {"command": "ls"}}),
    "session": json.dumps({"session_id": "s1", "source": "startup", "reason": "other", "cwd": "/tmp"}),
}
RO_INPUTS = {**MALFORMED, **{f"valid-{k}": v for k, v in VALID.items()}}
HOOK_SCRIPTS = sorted({h.script for h in CLAUDE if h.script})


def run_with_home(script: str, raw: str, proj: Path, sl_home: Path) -> subprocess.CompletedProcess:
    drop = ("SUPERLITE_FLEET_", "CLAUDE_", "CURSOR_", "SUPERLITE_STATE_DIR", "SUPERLITE_FINAL_REVIEW")
    env = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
    env.update({"HOME": str(proj.parent / "home"), "CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(sl_home),
                "CLAUDE_PLUGIN_ROOT": str(ROOT)})
    return subprocess.run([BASH, str(HOOKS / script), ], input=raw, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=proj, env=env, timeout=60)


@needs_bash
@pytest.mark.parametrize("script", HOOK_SCRIPTS)
def test_hooks_fail_open_read_only_home(script, tmp_path):
    proj = project(tmp_path, "run")
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, so no folder can be made under it", encoding="utf-8")
    writable, read_only = tmp_path / "wh", blocker / "home"  # read-only also for a root user
    for name, raw in RO_INPUTS.items():
        if script == "session-start" and name not in (*SESSION_START_INPUTS, "valid-session"):
            continue
        a = run_with_home(script, raw, proj, writable)
        b = run_with_home(script, raw, proj, read_only)
        assert (b.returncode, b.stdout, b.stderr) == (a.returncode, a.stdout, a.stderr), (script, name)
    assert not read_only.exists()


@needs_bash
def test_hook_events_valid(tmp_path):
    sl_home = tmp_path / "events_home"
    for state in STATES:
        (tmp_path / state).mkdir()
        proj = project(tmp_path / state, state)
        for script in HOOK_SCRIPTS:
            for name, raw in RO_INPUTS.items():
                if script == "session-start" and name not in (*SESSION_START_INPUTS, "valid-session"):
                    continue
                run_with_home(script, raw, proj, sl_home)
    events = telemetry.read_events(sl_home / "events.jsonl")
    assert {e.get("kind") for e in events} >= {"gate", "session_start"}, "the hooks wrote no lines"
    bad = [(e.get("kind"), p) for e in events if (p := telemetry.validate(e))]
    assert bad == []
    raw_lines = (sl_home / "events.jsonl").read_text(encoding="utf-8").splitlines() if events else []
    assert len(raw_lines) == len(events)
    assert all(len(line.encode("utf-8")) <= 4096 for line in raw_lines)
