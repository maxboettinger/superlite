"""#599: the hook lets the coordinator write the Owns of an inline one-task plan."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "block-coordinator-edits"
BASH = shutil.which("bash")
INLINE = "- An inline build (the run's plan holds exactly one task): you may write that task's Owns yourself."
ONE = "# Plan\n\n### T1 a\n**Owns:** src/app.py\n"
TWO = ONE + "\n### T2 b\n**Owns:** src/other.py\n"


def make(tmp_path, plan_text=ONE):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / "docs" / "plans").mkdir(parents=True)
    (p / ".superlite").mkdir()
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(plan_text)
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan)}))
    return p


def run(p, tool, path):
    env = {k: v for k, v in os.environ.items()
           if k != "SUPERLITE_STATE_DIR" and k != "SUPERLITE_SESSION_ID" and not k.startswith("SUPERLITE_FLEET_")}
    env["CLAUDE_PROJECT_DIR"] = str(p)
    raw = json.dumps({"tool_name": tool, "tool_input": {"file_path": path}, "cwd": str(p)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_edit_of_inline_owns_passes(tmp_path, tool):
    p = make(tmp_path)
    assert run(p, tool, str(p / "src" / "app.py")).returncode == 0
    assert run(p, tool, "src/app.py").returncode == 0
    assert run(p, tool, "src/other.py").returncode == 2


def test_two_task_plan_blocks_edit(tmp_path):
    p = make(tmp_path, TWO)
    assert run(p, "Edit", str(p / "src" / "app.py")).returncode == 2


def test_human_mode_blocks_owned_edit(tmp_path):
    p = make(tmp_path)
    (p / ".superlite" / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    assert run(p, "Edit", str(p / "src" / "app.py")).returncode == 2


def test_protected_still_blocks(tmp_path):
    p = make(tmp_path, "# Plan\n\n### T1 a\n**Owns:** .superlite/\n")
    assert run(p, "Write", str(p / ".superlite" / "orchestrator.json")).returncode == 2


def test_block_message_names_inline_build(tmp_path):
    p = make(tmp_path)
    r = run(p, "Edit", str(p / "src" / "other.py"))
    assert r.returncode == 2 and INLINE in r.stderr
    assert r.stderr.rstrip("\n").splitlines()[-1] == "Blocked target: src/other.py"
