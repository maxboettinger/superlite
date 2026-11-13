"""orchestrator end: the scratch folder (sd/scratch) is removed with the run (#690)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_end_removes_scratch_with_run(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "stable.json").write_text("{}", encoding="utf-8")
    (sd / "scratch" / "sub").mkdir(parents=True)
    (sd / "scratch" / "m.py").write_text("print(1)\n", encoding="utf-8")
    (sd / "scratch" / "sub" / "x.txt").write_text("x", encoding="utf-8")

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 1 files moved to ")
    assert line.endswith("; scratch folder removed")
    assert not (sd / "scratch").exists()


def test_end_removes_scratch_without_run(tmp_path):
    sd = tmp_path / ".superlite"
    (sd / "scratch").mkdir(parents=True)
    (sd / "scratch" / "m.py").write_text("print(1)\n", encoding="utf-8")

    line = orchestrator.end(sd)

    assert line == f"orchestrator: nothing to end in {sd}; scratch folder removed"
    assert not (sd / "scratch").exists()


def test_end_without_scratch_unchanged(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "stable.json").write_text("{}", encoding="utf-8")

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 1 files moved to ")
    assert "scratch folder" not in line

    empty = tmp_path / "empty" / ".superlite"
    empty.mkdir(parents=True)

    assert orchestrator.end(empty) == f"orchestrator: nothing to end in {empty}"


def test_end_scratch_symlink_keeps_target(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    (sd / "scratch").symlink_to(outside, target_is_directory=True)

    line = orchestrator.end(sd)

    assert not (sd / "scratch").is_symlink()
    assert not (sd / "scratch").exists()
    assert (outside / "keep.txt").exists()
    assert line.endswith("; scratch folder removed")


def test_end_scratch_plain_file(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "scratch").write_text("not a folder", encoding="utf-8")

    line = orchestrator.end(sd)

    assert not (sd / "scratch").exists()
    assert line.endswith("; scratch folder removed")


def test_end_survives_unremovable_scratch(tmp_path):
    import os

    if os.name == "nt" or os.geteuid() == 0:
        pytest.skip("permissions not enforced")
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "stable.json").write_text("{}", encoding="utf-8")
    locked = sd / "scratch" / "locked"
    locked.mkdir(parents=True)
    (locked / "x.txt").write_text("x", encoding="utf-8")
    locked.chmod(0o500)
    try:
        line = orchestrator.end(sd)
        assert line.startswith("orchestrator: run ended; 1 files moved to ")
        assert not (sd / "stable.json").exists()
        assert not line.endswith("; scratch folder removed")
    finally:
        locked.chmod(0o700)
