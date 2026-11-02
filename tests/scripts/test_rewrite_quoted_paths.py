"""rewrite-test-runs: a test run whose arguments contain quotes passes unchanged (issue #52)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "rewrite-test-runs"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "pool.json").write_text("{}")
    return tmp_path


def run(proj, command, **extra):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, **extra})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def unchanged(r, proj):
    assert r.returncode == 0 and r.stdout == ""
    assert not (proj / ".superlite" / "incidents.jsonl").exists()


def test_double_quoted_path_unchanged(proj):
    unchanged(run(proj, 'pytest "tests/my dir/a.py"'), proj)


def test_single_quoted_path_unchanged(proj):
    unchanged(run(proj, "pytest 'tests/my dir/a.py'"), proj)


def test_unquoted_path_still_rewritten(proj):
    r = run(proj, "pytest tests/a.py")
    assert r.returncode == 0
    cmd = json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"]["command"]
    assert cmd.rstrip().endswith("run_tests --fast tests/a.py")


def test_subagent_quoted_not_denied(proj):
    r = run(proj, "pytest 'tests/my dir/a.py'", agent_id="a1", agent_type="implementer")
    assert r.returncode == 0 and "Blocked" not in r.stderr


@pytest.mark.parametrize("cmd", ['pytest "my test.py"', "pytest -x 'my test.py'"])
def test_subagent_quoted_name_without_slash_not_denied(proj, cmd):
    """No `/` in the quoted name: the old word split saw `test.py"` and denied it as a bare full suite."""
    r = run(proj, cmd, agent_id="a1", agent_type="implementer")
    assert r.returncode == 0 and "Blocked" not in r.stderr


@pytest.mark.parametrize("cmd", ['pytest -m "not slow"', "pytest -k 'foo'", 'npm test "x y"'])
def test_subagent_quoted_flag_value_still_denied(proj, cmd):
    """A quote alone is not a target: a quoted flag value on a bare runner is still the full suite."""
    r = run(proj, cmd, agent_id="a1", agent_type="implementer")
    assert r.returncode == 2 and "Blocked" in r.stderr


def test_double_quoted_name_without_slash_unchanged(proj):
    unchanged(run(proj, 'pytest "my test.py"'), proj)


def test_chained_quoted_segment_unchanged(proj):
    unchanged(run(proj, 'cd x && pytest "a b/t.py"'), proj)
