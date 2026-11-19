"""#987: hooks/researcher-bash holds the in-process researcher's Bash calls to the read-only allowlist."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "researcher-bash"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
HEAD = "Blocked: the researcher runs only read-only commands (hooks/researcher-bash, #987): "


def run(home, command, agent="superlite:researcher", tool="Bash", env=None):
    p = {"session_id": "s1", "cwd": str(ROOT), "hook_event_name": "PreToolUse", "tool_name": tool,
         "tool_input": {"command": command}}
    if agent is not None:
        p["agent_type"] = agent
        p["agent_id"] = "a1"
    e = dict(os.environ)
    e["SUPERLITE_HOME"] = str(home)
    e.update(env or {})
    r = subprocess.run([BASH, str(HOOK)], input=json.dumps(p), capture_output=True, text=True, env=e, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


def test_allowed_command_passes_silently(tmp_path):
    assert run(tmp_path, "git log --oneline -5") == (0, "", "")


@pytest.mark.parametrize("command,reason", [
    ("touch probe.txt", "not on the allowlist: touch probe.txt"),
    ("git status && rm -rf src", "not on the allowlist: rm -rf src"),
    ("git diff --output=x.patch", "writes a file (--output): git diff --output=x.patch"),
])
def test_off_list_and_compound_commands_block(tmp_path, command, reason):
    code, out, err = run(tmp_path, command)
    assert (code, out) == (2, "")
    assert err.splitlines()[0] == HEAD + reason + "."
    assert err.splitlines()[2].startswith("A refused command is an answer")


@pytest.mark.parametrize("agent", ["superlite:implementer", "researcher", None])
def test_other_agents_pass(tmp_path, agent):
    assert run(tmp_path, "rm -rf src", agent=agent) == (0, "", "")


def test_researcher_read_tool_passes(tmp_path):
    assert run(tmp_path, "rm -rf src", tool="Read") == (0, "", "")


def test_block_appends_a_gate_line(tmp_path):
    run(tmp_path, "touch probe.txt")
    lines = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    gates = [x for x in lines if x["kind"] == "gate"]
    assert [(g["hook"], g["decision"], g["rule"], g["tool"]) for g in gates] == [
        ("researcher-bash", "block", "research-bash", "Bash")]


@pytest.mark.skipif(os.name == "nt", reason="the fake interpreter is a sh script")
@pytest.mark.parametrize("body", ["echo oops >&2; exit 2", "echo 'Blocked: x' >&2; exit 2", "exit 3", "exit 1"])
def test_helper_failure_fails_open(tmp_path, body):
    fake = tmp_path / "fakepy"
    fake.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    fake.chmod(0o755)
    assert run(tmp_path, "touch probe.txt", env={"SUPERLITE_PYTHON": str(fake)}) == (0, "", "")


def test_hooks_json_appends_the_entry():
    pre = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    assert pre[-1] == {"matcher": "Bash", "hooks": [{"type": "command", "shell": "bash",
                       "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/researcher-bash"'}]}
    assert [e["matcher"] for e in pre[:3]] == ["Bash|PowerShell|Monitor",
                                              "Edit|Write|NotebookEdit|Bash|PowerShell|Monitor|Agent", "Bash|Monitor"]
    assert len(pre) == 6


def test_docs_name_the_hook():
    hooks = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    assert "- `researcher-bash`: " in hooks and "`fleet_roles.RESEARCH_BASH`" in hooks
    assert "`block-unsafe-kill`, `researcher-bash`, `rewrite-test-runs`" in hooks
    assert "`researcher-bash` hook |" in (ROOT / "docs" / "gates.md").read_text(encoding="utf-8")
