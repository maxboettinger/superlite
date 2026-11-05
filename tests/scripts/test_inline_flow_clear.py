"""The inline-flow marker (#148) is cleared by `orchestrator end` and by session-start startup/clear, not compact."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "session-start"
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "inline-flow.json").write_text('{"flow":"small"}', encoding="utf-8")
    return tmp_path


def marker(proj):
    return proj / ".superlite" / "inline-flow.json"


def start(proj, source):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "CLAUDE_ENV_FILE"}
    env.update(CLAUDE_PLUGIN_ROOT=str(ROOT), SUPERLITE_HOME=str(proj / "home"), CLAUDE_PROJECT_DIR=str(proj))
    r = subprocess.run([BASH, str(HOOK)], input=json.dumps({"session_id": "s1", "source": source}),
                       capture_output=True, text=True, encoding="utf-8", cwd=proj, env=env)
    assert r.returncode == 0, r.stderr


def test_orchestrator_end_removes_marker(proj):
    sys.path.insert(0, str(SCRIPTS))
    import orchestrator
    orchestrator.end(proj / ".superlite")
    assert not marker(proj).exists()


@pytest.mark.parametrize("source", ["startup", "clear"])
def test_session_start_clears_marker(proj, source):
    start(proj, source)
    assert not marker(proj).exists()


def test_compact_keeps_marker(proj):
    start(proj, "compact")
    assert marker(proj).exists()
