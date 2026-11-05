"""hooks/mark-inline-flow: marks an inline superlite flow (a /superlite:small or /superlite:debug prompt, the
test-driven-development or systematic-debugging skill) in <state folder>/inline-flow.json; never from a subagent or a
fleet worker; always exits 0 (#148)."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "mark-inline-flow"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    return tmp_path


def marker(proj):
    return proj / ".superlite" / "inline-flow.json"


def run(proj, payload, **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj / "home"), **env})
    return subprocess.run([BASH, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=e)


def prompt(proj, text, **extra):
    return run(proj, {"hook_event_name": "UserPromptSubmit", "prompt": text, "cwd": str(proj), **extra})


def skill(proj, name, **extra):
    return run(proj, {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": name},
                      "cwd": str(proj), **extra})


def test_prompt_marks_small(proj):
    before = int(time.time())
    r = prompt(proj, "/superlite:small fix the typo")
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    data = json.loads(marker(proj).read_text(encoding="utf-8"))
    assert data["flow"] == "small" and data["inplace"] is None
    assert before <= data["at"] <= int(time.time()) + 1


def test_prompt_not_at_start_does_not_mark(proj):
    for text in ("please /superlite:small", "fix it via /superlite:debug x", "/superlite:smaller x", "/superlite:",
                 "", "no command here"):
        assert prompt(proj, text).returncode == 0
        assert not marker(proj).exists(), text


def test_prompt_marks_debug_and_bare_command(proj):
    assert prompt(proj, "/superlite:debug x").returncode == 0
    assert json.loads(marker(proj).read_text(encoding="utf-8"))["flow"] == "debug"
    marker(proj).unlink()
    assert prompt(proj, "  /superlite:small").returncode == 0
    assert json.loads(marker(proj).read_text(encoding="utf-8"))["flow"] == "small"


def test_prompt_restarts_the_flow_and_clears_inplace(proj):
    marker(proj).write_text('{"flow": "tdd", "at": 1, "inplace": "typo"}', encoding="utf-8")
    assert prompt(proj, "/superlite:debug again").returncode == 0
    data = json.loads(marker(proj).read_text(encoding="utf-8"))
    assert data["flow"] == "debug" and data["inplace"] is None and data["at"] > 1


def test_skill_marks_tdd(proj):
    assert skill(proj, "superlite:test-driven-development").returncode == 0
    assert json.loads(marker(proj).read_text(encoding="utf-8"))["flow"] == "tdd"
    marker(proj).unlink()
    assert skill(proj, "superlite:systematic-debugging").returncode == 0
    data = json.loads(marker(proj).read_text(encoding="utf-8"))
    assert data["flow"] == "debugging" and data["inplace"] is None


def test_other_skills_and_tools_do_not_mark(proj):
    for name in ("superlite:brainstorming", "superlite:writing-plans", "test-driven-development", "other:x"):
        assert skill(proj, name).returncode == 0
        assert not marker(proj).exists(), name
    r = run(proj, {"tool_name": "Edit", "tool_input": {"file_path": "a.py", "skill": "superlite:test-driven-development"}})
    assert r.returncode == 0 and not marker(proj).exists()


def test_skill_keeps_an_existing_marker_and_its_opt_out(proj):
    marker(proj).write_text('{"flow": "small", "at": 5, "inplace": "typo"}', encoding="utf-8")
    assert skill(proj, "superlite:test-driven-development").returncode == 0
    assert json.loads(marker(proj).read_text(encoding="utf-8")) == {"flow": "small", "at": 5, "inplace": "typo"}


def test_subagent_and_worker_never_mark(proj):
    assert prompt(proj, "/superlite:small x", agent_id="a1").returncode == 0
    assert skill(proj, "superlite:test-driven-development", agent_id="a1", agent_type="implementer").returncode == 0
    assert not marker(proj).exists()
    assert run(proj, {"prompt": "/superlite:small x"}, SUPERLITE_FLEET_WORKER="W1").returncode == 0
    assert not marker(proj).exists()
    r = run(proj, {"tool_name": "Skill", "tool_input": {"skill": "superlite:systematic-debugging"}},
            SUPERLITE_FLEET_WORKER="W1")
    assert r.returncode == 0 and not marker(proj).exists()


def test_creates_the_state_folder_when_missing(tmp_path):
    assert prompt(tmp_path, "/superlite:small x").returncode == 0
    assert json.loads((tmp_path / ".superlite" / "inline-flow.json").read_text(encoding="utf-8"))["flow"] == "small"


def test_state_dir_env_names_the_folder(tmp_path):
    sd = tmp_path / "elsewhere" / ".superlite"
    r = run(tmp_path, {"prompt": "/superlite:debug x"}, SUPERLITE_STATE_DIR=str(sd))
    assert r.returncode == 0
    assert json.loads((sd / "inline-flow.json").read_text(encoding="utf-8"))["flow"] == "debug"


def test_malformed_input_fails_open(proj):
    for raw in ("", "not json", '{"prompt": "/superlite:small', '{"tool_name": 5}'):
        e = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
        r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e)
        assert r.returncode == 0, raw
    assert not marker(proj).exists()


def test_hooks_json_registers():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    mark = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/mark-inline-flow"'
    guard = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/inline-worktree-guard"'
    prompt_cmds = [h["command"] for e in data["UserPromptSubmit"] for h in e["hooks"]]
    assert mark in prompt_cmds
    for old in ('bash "${CLAUDE_PLUGIN_ROOT}/hooks/record-human-reply"', 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/compact-nudge"'):
        assert old in prompt_cmds
    pre = {(e["matcher"], h["command"]) for e in data["PreToolUse"] for h in e["hooks"]}
    assert ("Skill", mark) in pre
    assert ("Edit|Write|NotebookEdit", guard) in pre
    for old in (("Bash|PowerShell", 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/block-unsafe-kill"'),
                ("Edit|Write|NotebookEdit|Bash|PowerShell|Agent", 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/block-coordinator-edits"'),
                ("Bash", 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/rewrite-test-runs"')):
        assert old in pre
    assert [e["matcher"] for e in data["PreToolUse"][:3]] == [
        "Bash|PowerShell", "Edit|Write|NotebookEdit|Bash|PowerShell|Agent", "Bash"]   # existing indices stay
    for name in ("SessionStart", "PostToolUse", "SubagentStop", "Stop"):
        assert name in data


def test_lf_endings():
    assert b"\r" not in HOOK.read_bytes()
