"""#784: the fleet task message names the run root right after PLAN=, except for an external-repo task."""
from __future__ import annotations

import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402
import plan_tools as pt  # noqa: E402


def plan(tmp_path, repo=None):
    out = ["# Plan", "**Goal:** test.", "", "Global constraints:", "- small", "", "```mermaid", "flowchart LR", "  T1[a]", "  T2[b]", "  %% taskgraph", "```", ""]
    out += ["### T1 thing · Complexity 1", "**Owns:** src/a.py, tests/test_a.py", "**Tests:** fast"] + ([f"**Repo:** {repo}", "**Repo test:** `pytest -q`"] if repo else []) + [""]
    out += ["### T2 other · Complexity 1", "**Owns:** src/b.py, tests/test_b.py", "**Tests:** fast", ""]
    p = tmp_path / "plan.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def root_of(p):
    return pt.stable_root(str(p)).resolve().as_posix()


def test_task_message_names_root_after_plan(tmp_path):
    p = plan(tmp_path)
    lines = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl").splitlines()
    i = lines.index(f"PLAN={p.resolve()}")
    assert lines[i + 1] == f"ROOT={root_of(p)}"


def test_batch_message_names_root_once(tmp_path):
    p = plan(tmp_path)
    lines = fleet_io.task_message(p, ["T1", "T2"], "/sl/sl", "/sl").splitlines()
    assert len([ln for ln in lines if ln.startswith("ROOT=")]) == 1


def test_haiku_message_names_root(tmp_path):
    p = plan(tmp_path)
    lines = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl", tier="haiku").splitlines()
    i = lines.index(f"PLAN={p.resolve()}")
    assert lines[i + 1] == f"ROOT={root_of(p)}"


def test_external_task_has_no_root_line(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    subprocess.run(["git", "init", "-q", str(shared)], check=True)
    p = plan(tmp_path, repo=shared)
    msg = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert not [ln for ln in msg.splitlines() if ln.startswith("ROOT=")]
