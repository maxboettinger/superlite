"""Session, invoke and mode events from session-start, session-end and mark-inline-flow (#933)."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import telemetry  # noqa: E402

BASH = shutil.which("bash")
HOOKS = ROOT / "hooks"
SID = "sess-1"


def home() -> Path:
    return Path(os.environ["SUPERLITE_HOME"])


def run(hook, payload, tmp_path, **env):
    e = {k: v for k, v in os.environ.items()
         if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "SUPERLITE_TELEMETRY", "CLAUDE_ENV_FILE",
                      "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_FLEET_WORKER")}
    e.update({"CLAUDE_PROJECT_DIR": str(tmp_path), "CLAUDE_PLUGIN_ROOT": str(ROOT), **env})
    return subprocess.run([BASH, str(HOOKS / hook)], input=json.dumps(payload), capture_output=True, text=True,
                          cwd=tmp_path, env=e)


def sfile(ext) -> Path:
    return home() / "telemetry" / "sessions" / f"{SID}.{ext}"


def lines(kind):
    out = [e for e in telemetry.read_events() if e["kind"] == kind]
    for e in out:
        assert telemetry.validate(e) == []
    return out


def start(tmp_path, source, **env):
    return run("session-start", {"session_id": SID, "source": source, "cwd": str(tmp_path)}, tmp_path, **env)


def prompt(tmp_path, text, **extra):
    return run("mark-inline-flow", {"session_id": SID, "hook_event_name": "UserPromptSubmit", "prompt": text,
                                    "cwd": str(tmp_path), **extra}, tmp_path)


def skill(tmp_path, name, **extra):
    return run("mark-inline-flow", {"session_id": SID, "hook_event_name": "PreToolUse", "tool_name": "Skill",
                                    "tool_input": {"skill": name}, "cwd": str(tmp_path), **extra}, tmp_path)


def test_kind_session_start_startup(tmp_path):
    r = start(tmp_path, "startup")
    assert r.returncode == 0
    (line,) = lines("session_start")
    assert line["source"] == "startup" and line["duration_s"] is None and line["session"] == SID
    first = sfile("start").read_text().strip()
    assert first.isdigit()
    sfile("start").write_text("1000\n")
    start(tmp_path, "compact")
    assert sfile("start").read_text().strip() == "1000"
    assert [e["source"] for e in lines("session_start")] == ["startup", "compact"]


def test_kind_session_end_duration(tmp_path):
    sfile("start").parent.mkdir(parents=True)
    sfile("start").write_text(f"{int(time.time()) - 120}\n")
    sfile("mode").write_text("feature\n")
    r = run("session-end", {"session_id": SID, "reason": "other", "cwd": str(tmp_path)}, tmp_path)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (line,) = lines("session_end")
    assert line["reason"] == "other" and 119 <= line["duration_s"] <= 125
    assert not sfile("start").exists() and not sfile("mode").exists()
    run("session-end", {"session_id": SID, "reason": "clear", "cwd": str(tmp_path)}, tmp_path)
    assert lines("session_end")[-1]["duration_s"] is None


def test_kind_invoke_skill(tmp_path):
    r = skill(tmp_path, "superlite:brainstorming", agent_id="a1")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (line,) = lines("invoke")
    assert (line["name"], line["via"]) == ("superlite:brainstorming", "skill")


def test_kind_invoke_command(tmp_path):
    prompt(tmp_path, "/superlite:feature add x secretword")
    (line,) = lines("invoke")
    assert (line["name"], line["via"]) == ("superlite:feature", "command")
    assert "secretword" not in (home() / "events.jsonl").read_text()


def test_kind_mode_from_command(tmp_path):
    prompt(tmp_path, "/superlite:mvp")
    (line,) = lines("mode")
    assert line["mode"] == "mvp"
    assert sfile("mode").read_text().strip() == "mvp"


def test_kind_mode_start_word(tmp_path):
    prompt(tmp_path, "/superlite:start debug fix y")
    (line,) = lines("mode")
    assert line["mode"] == "debug"
    assert sfile("mode").read_text().strip() == "debug"


def test_kind_mode_regular_once(tmp_path):
    skill(tmp_path, "superlite:brainstorming")
    assert [e["mode"] for e in lines("mode")] == ["regular"]
    sfile("mode").unlink()
    prompt(tmp_path, "/superlite:feature add x")
    assert [e["mode"] for e in lines("mode")] == ["regular", "feature"]
    skill(tmp_path, "superlite:brainstorming")
    assert [e["mode"] for e in lines("mode")] == ["regular", "feature"]


def test_non_superlite_skill_ignored(tmp_path):
    r = skill(tmp_path, "other:brainstorming")
    assert r.returncode == 0
    assert not (home() / "events.jsonl").exists()


def test_session_hooks_output_unchanged(tmp_path):
    on = start(tmp_path, "startup")
    off = start(tmp_path, "startup", SUPERLITE_TELEMETRY="0")
    assert on.returncode == 0 and on.stdout == off.stdout and on.stdout.startswith("{")
    assert on.stderr == off.stderr == ""


def test_hooks_json_session_end_entry():
    data = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    (entry,) = data["SessionEnd"]
    assert "matcher" not in entry
    (h,) = entry["hooks"]
    assert h["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/session-end"'
