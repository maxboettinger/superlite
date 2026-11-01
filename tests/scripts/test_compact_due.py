import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
HOOK = ROOT / "hooks" / "compact-nudge"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")

sys.path.insert(0, str(SCRIPTS))
import compact_due  # noqa: E402


def _sl(tmp_path, *, compact_mtime=None, launch_t=0):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "metrics.jsonl").write_text(
        json.dumps({"ev": "launch", "t": launch_t, "agent_id": "a1"}) + "\n", encoding="utf-8"
    )
    if compact_mtime is not None:
        marker = sl / "last-compact"
        marker.write_text("", encoding="utf-8")
        os.utime(marker, (compact_mtime, compact_mtime))
    return sl


def _env(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("SUPERLITE_STATE_DIR", "CLAUDE_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT",
                        "CURSOR_AGENT", "CURSOR_TRACE_ID", "SUPERLITE_NO_AUTOCOMPACT",
                        "COPILOT_CLI", "MUSE_PLUGIN_ROOT")}
    env.update({"CLAUDE_PROJECT_DIR": str(tmp_path), "SUPERLITE_HOME": str(tmp_path / "home")})
    env.update(extra)
    return env


def _run(tmp_path, **extra):
    return subprocess.run([BASH, str(HOOK)], input="{}", capture_output=True, text=True,
                          env=_env(tmp_path, **extra), cwd=str(tmp_path))


def test_due_when_stale(tmp_path):
    sl = _sl(tmp_path, compact_mtime=0, launch_t=0)
    assert compact_due.is_due(str(sl), now=10000.0, window_s=100.0) is True


def test_not_due_when_fresh(tmp_path):
    sl = _sl(tmp_path, compact_mtime=50, launch_t=0)
    assert compact_due.is_due(str(sl), now=100.0, window_s=100.0) is False


def test_launch_t_is_ms(tmp_path):
    sl = _sl(tmp_path, launch_t=100000)
    assert compact_due.is_due(str(sl), now=2000.0) is True
    assert compact_due.is_due(str(sl), now=1000.0) is False


def test_opt_out_env(tmp_path):
    _sl(tmp_path, compact_mtime=0, launch_t=0)
    r = _run(tmp_path, SUPERLITE_NO_AUTOCOMPACT="1")
    assert r.returncode == 0
    assert "compact" not in r.stdout.lower()
    assert "compact" not in r.stderr.lower()


def test_nudge_line_mentions_compact():
    line = compact_due.nudge_line()
    assert "compact" in line.lower()
    assert "last-compact" not in line


def test_nudge_once_per_window(tmp_path):
    _sl(tmp_path, compact_mtime=0)
    first = _run(tmp_path)
    assert first.returncode == 0 and "compact" in first.stdout.lower()
    second = _run(tmp_path)
    assert second.returncode == 0 and second.stdout == ""


def test_claude_output_shape(tmp_path):
    _sl(tmp_path, compact_mtime=0)
    r = _run(tmp_path, CLAUDE_PLUGIN_ROOT=str(ROOT))
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "compact" in out["hookSpecificOutput"]["additionalContext"].lower()


def test_no_superlite_dir_silent(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_mark_writes_last_compact(tmp_path):
    sl = _sl(tmp_path)
    compact_due.mark(str(sl))
    assert (sl / "last-compact").exists()
