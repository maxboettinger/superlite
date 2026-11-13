"""batch_cost rows carry the batch's run config, experiment and arm (#682)."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import batch_cost  # noqa: E402
import experiment  # noqa: E402


def test_row_carries_config_experiment_and_arm(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "assignment", lambda root, b: {"experiment": "e1", "arm": "cheap"}, raising=False)
    row = batch_cost.build_row(tmp_path, {"id": "B5", "run_config": "cheap-1a2b3c4d"}, "shipped")
    assert row["config"] == "cheap-1a2b3c4d"
    assert row["experiment"] == "e1"
    assert row["arm"] == "cheap"


def test_batch_without_an_arm_has_none(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "assignment", lambda root, b: None, raising=False)
    row = batch_cost.build_row(tmp_path, {"id": "B5", "run_config": "cheap-1a2b3c4d"}, "shipped")
    assert row["experiment"] is None and row["arm"] is None


def test_batch_without_run_config_is_default(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "assignment", lambda root, b: None, raising=False)
    row = batch_cost.build_row(tmp_path, {"id": "B5"}, "shipped")
    assert row["config"] == "default"


def test_assignment_error_never_breaks_row(tmp_path, monkeypatch):
    def broken(root, b):
        raise RuntimeError("experiments.json unreadable")

    monkeypatch.setattr(experiment, "assignment", broken, raising=False)
    row = batch_cost.build_row(tmp_path, {"id": "B5", "run_config": "cheap-1a2b3c4d"}, "shipped")
    assert row["experiment"] is None and row["arm"] is None
    assert row["config"] == "cheap-1a2b3c4d" and row["batch"] == "B5"
