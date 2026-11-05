# Regression tests for the package review of fleet phase 3 guard and hooks (T1-T4).
import json, os, subprocess
import pytest
from test_block_coordinator_edits import BASH, HOOK


def run(proj, tool, inp, env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj.parent / "slhome"), **env})
    raw = json.dumps({"session_id": "s", "tool_name": tool, "tool_input": inp, "cwd": str(proj)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e).returncode


@pytest.fixture(params=["idle", "active"])
def world(tmp_path, request):
    proj = tmp_path / "wt"; (proj / ".superlite").mkdir(parents=True)
    parent = tmp_path / "main" / ".superlite"; parent.mkdir(parents=True)
    if request.param == "active":
        (proj / ".superlite" / "pool.json").write_text("{}")
    env = {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": "lead",
           "SUPERLITE_STATE_DIR": str(proj / ".superlite"), "SUPERLITE_FLEET_PARENT_DIR": str(parent)}
    return proj, parent, env, tmp_path


def test_relative_path_leaving_the_project_reaches_the_parent_run_files(world):
    proj, parent, env, _ = world
    for tool in ("Write", "Edit"):
        assert run(proj, tool, {"file_path": "../main/.superlite/backlog.json"}, env) == 2
        assert run(proj, tool, {"file_path": "./../main/.superlite/orchestrator.json"}, env) == 2
    assert run(proj, "Write", {"file_path": "../main/.superlite/backlog/B1.md"}, env) == 0


def test_outside_symlink_to_a_run_file_is_protected(world):
    proj, parent, env, tmp = world
    (tmp / "out").mkdir()
    (tmp / "out" / "ln").symlink_to(parent / "backlog.json")
    (tmp / "out" / "ok").symlink_to(parent / "progress.md")
    assert run(proj, "Write", {"file_path": str(tmp / "out" / "ln")}, env) == 2
    assert run(proj, "Write", {"file_path": str(tmp / "out" / "ok")}, env) == 0
