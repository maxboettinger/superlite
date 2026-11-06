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


def run(proj, command, env_extra=None, **extra):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, **extra})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), **(env_extra or {})}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if not env_extra:
        env.pop("SUPERLITE_FLEET_ROLE", None)
        env.pop("SUPERLITE_FLEET_WORKER", None)
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def rows(proj):
    f = proj / ".superlite" / "incidents.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


@pytest.mark.parametrize("cmd", [
    "uv run pytest --collect-only",
    "pytest --co -q",
    "python -m pytest --collect-only tests/",
    "uv run pytest --collect-only -q && echo ok",
])
def test_worker_collect_only_passes(proj, cmd):
    r = run(proj, cmd, agent_id="a1")
    assert r.returncode == 0 and r.stdout == ""
    assert rows(proj) == []


def test_fleet_worker_collect_only_passes(proj):
    r = run(proj, "pytest --collect-only", {"SUPERLITE_FLEET_WORKER": "W1", "SUPERLITE_FLEET_ROLE": "implementer"})
    assert r.returncode == 0 and r.stdout == ""


@pytest.mark.parametrize("cmd", ["pytest --cov", "pytest --co-x"])
def test_cov_is_not_co(proj, cmd):
    assert run(proj, cmd, agent_id="a1").returncode == 2


def test_worker_block_names_the_full_route(proj):
    r = run(proj, "pytest", agent_id="a1")
    assert r.returncode == 2
    assert "sl run_tests --full" in r.stderr and "sl run_tests --fast <files>" in r.stderr


def test_coordinator_collect_only_not_rewritten(proj):
    r = run(proj, "uv run pytest --collect-only")
    assert r.returncode == 0 and r.stdout == ""


def test_deny_rows_carry_rule_and_cwd(proj):
    run(proj, "pytest", agent_id="a1", cwd="/w/x")
    row = rows(proj)[-1]
    assert row["rule"] == "subagent-full-suite" and row["cwd"] == "/w/x"
    run(proj, "until pytest; do sleep 1; done", cwd="/w/x")
    row = rows(proj)[-1]
    assert row["rule"] == "hidden-test-wait" and row["cwd"] == "/w/x"
    run(proj, "pytest " + "x" * 500, agent_id="a1", cwd="/w/x")
    # a path-less long command is still a full-suite run only when no path-like arg; 'xxx' has none
    row = rows(proj)[-1]
    assert row["rule"] == "subagent-full-suite"
    prefix = "full suite: "
    assert row["target"].startswith(prefix) and len(row["target"]) - len(prefix) <= 400
