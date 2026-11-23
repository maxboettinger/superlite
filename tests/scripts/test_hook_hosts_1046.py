"""#1046: hooks speak Claude Code (nested) or the top-level fallback; no Cursor, Copilot, Muse, Codex or Gemini branch."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(not BASH, reason="bash not available")
GONE_VARS = ("CURSOR_PLUGIN_ROOT", "COPILOT_CLI", "MUSE_PLUGIN_ROOT")
HOST_ENV = GONE_VARS + ("CLAUDE_PLUGIN_ROOT", "CLAUDE_ENV_FILE", "CLAUDE_PID", "CURSOR_AGENT", "CURSOR_TRACE_ID")
MODE_FILE = "orchestrator" + ".json"

sys.path.insert(0, str(SCRIPTS))
import feedback  # noqa: E402


def _env(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k not in HOST_ENV}
    env.update({"CLAUDE_PROJECT_DIR": str(tmp_path), "SUPERLITE_HOME": str(tmp_path / "home"), "HOME": str(tmp_path)})
    env.update(extra)
    return env


def _hook(tmp_path, name, inp, **extra):
    r = subprocess.run([BASH, str(HOOKS / name)], input=json.dumps(inp), capture_output=True, text=True,
                       encoding="utf-8", env=_env(tmp_path, **extra), cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _session_start(tmp_path, **extra):
    inp = {"hook_event_name": "SessionStart", "source": "startup", "session_id": "s1046", "cwd": str(tmp_path)}
    return _hook(tmp_path, "session-start", inp, **extra)


def _nudge(tmp_path, **extra):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / MODE_FILE).write_text("{}", encoding="utf-8")
    usage = {"input_tokens": 2, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 650000 - 1002,
             "output_tokens": 70000}
    t = tmp_path / "transcript.jsonl"
    t.write_text(json.dumps({"type": "assistant", "isSidechain": False,
                             "message": {"role": "assistant", "usage": usage}}) + "\n", encoding="utf-8")
    inp = {"hook_event_name": "UserPromptSubmit", "prompt": "go on", "session_id": "s1046", "transcript_path": str(t)}
    return _hook(tmp_path, "compact-nudge", inp, **extra)


@needs_bash
@pytest.mark.parametrize("var", GONE_VARS)
def test_session_start_under_claude_code_ignores_removed_host_vars(tmp_path, var):
    out = _session_start(tmp_path, CLAUDE_PLUGIN_ROOT=str(ROOT), **{var: "1"})
    assert list(out) == ["hookSpecificOutput"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "superlite:using-superlite" in out["hookSpecificOutput"]["additionalContext"]


@needs_bash
def test_session_start_without_claude_plugin_root_keeps_top_level_fallback(tmp_path):
    out = _session_start(tmp_path, CURSOR_PLUGIN_ROOT=str(ROOT))
    assert list(out) == ["additionalContext"]
    assert "superlite:using-superlite" in out["additionalContext"]


@needs_bash
@pytest.mark.parametrize("var", GONE_VARS)
def test_compact_nudge_under_claude_code_ignores_removed_host_vars(tmp_path, var):
    out = _nudge(tmp_path, CLAUDE_PLUGIN_ROOT=str(ROOT), **{var: "1"})
    assert list(out) == ["hookSpecificOutput"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "650k" in out["hookSpecificOutput"]["additionalContext"]


@needs_bash
def test_compact_nudge_without_claude_plugin_root_keeps_top_level_fallback(tmp_path):
    out = _nudge(tmp_path, CURSOR_PLUGIN_ROOT=str(ROOT))
    assert list(out) == ["additionalContext"]
    assert "650k" in out["additionalContext"]


def test_hooks_name_no_removed_host():
    assert not (HOOKS / "hooks-cursor.json").exists()
    for name in ("session-start", "compact-nudge", "pre-compact", "telemetry.sh"):
        text = (HOOKS / name).read_text(encoding="utf-8")
        for word in GONE_VARS + ("CODEX_", "GEMINI_CLI", "Cursor", "Copilot", "Muse", "Factory Droid", "Qwen"):
            assert word not in text, (name, word)
    assert "hooks-cursor.json" not in (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")


def test_feedback_detects_only_claude_code(monkeypatch):
    assert feedback.HARNESS_ENV == [("CLAUDECODE", "claude-code")]
    for var in ("SUPERLITE_HARNESS", "CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SANDBOX", "GEMINI_CLI"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "t1")
    monkeypatch.setenv("GEMINI_CLI", "1")
    assert feedback.harness() == "unknown"
    monkeypatch.setenv("CLAUDECODE", "1")
    assert feedback.harness() == "claude-code"


def test_feedback_session_ignores_codex_thread(monkeypatch, tmp_path):
    for var in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "t1")
    monkeypatch.chdir(tmp_path)
    assert feedback.new_entry("bug", "x y z", ver="1.0.0")["session"] == ""
