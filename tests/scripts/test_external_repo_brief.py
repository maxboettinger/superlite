"""The worker's task text and fleet message for an external repository task (#332)."""
from __future__ import annotations

import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402
import plan_tools  # noqa: E402
import task  # noqa: E402


def setup(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    p = tmp_path / "plan.md"
    p.write_text("\n".join([
        "# Plan", "**Goal:** test.", "**Wave0:** none", "", "Global constraints:", "- keep it small", "",
        "```mermaid", "flowchart LR", "  T1[a]", "  T2[b]", "  %% taskgraph", "  T1 --> T2", "```", "",
        "### T1 shared helper · Est. time 2 min", "**Owns:** src/helper.py, tests/test_helper.py",
        f"**Repo:** {root}", "**Repo test:** `pytest -q`", "**Repo ship:** `maxapp ship -C {tree}`", "",
        "### T2 local · Est. time 2 min", "**Owns:** src/app.py, tests/test_app.py", ""]), encoding="utf-8")
    return p, root


def test_task_text_has_external_section(tmp_path):
    p, root = setup(tmp_path)
    plan = plan_tools.Plan.load(str(p))
    text = task.render(plan, "T1")
    assert "\n## External repository\n" in text
    assert f"`sl plan_tools external T1 --plan {p} --test` runs `pytest -q` in the tree" in text
    assert text.index("## External repository") < text.index("## Global constraints")
    assert "## External repository" not in task.render(plan, "T2")


def test_fleet_message_external_verify(tmp_path):
    p, root = setup(tmp_path)
    msg = fleet_io.task_message(p, ["T1"], "/x/sl", "/x")
    plan = p.resolve()
    assert (f"Verify: `/x/sl plan_tools external T1 --plan {plan} --test` (its **Repo test:** command in the "
            "task's tree), not run_tests.") in msg
    assert f"Owns (relative to the task's tree of {root}): src/helper.py, tests/test_helper.py" in msg
    assert "run_tests --fast" not in msg
    local = fleet_io.task_message(p, ["T2"], "/x/sl", "/x")
    assert "run_tests --fast tests/test_app.py --task T2" in local and "plan_tools external" not in local
    assert "Owns: src/app.py, tests/test_app.py" in local


def test_haiku_message_carries_section(tmp_path):
    p, root = setup(tmp_path)
    assert "## External repository" in fleet_io.task_message(p, ["T1"], "/x/sl", "/x", tier="haiku")
