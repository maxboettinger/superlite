"""docs name `worktree scratch` (#816)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def line(path, start):
    return next(ln for ln in (ROOT / path).read_text(encoding="utf-8").splitlines() if ln.startswith(start))


def test_tools_row_names_scratch():
    row = line("docs/tools.md", "| `worktree` |")
    for text in ("`worktree scratch [--rev REV] [--repo DIR] -- COMMAND...`", "start SHA", "-clonedSourcePackagesDirPath",
                 ".build/SourcePackages", "SUPERLITE_RUN_ROOT", "SUPERLITE_SOURCE_PACKAGES", "worktree: scratch tree removed"):
        assert text in row


def test_fleet_checker_names_scratch():
    row = line("skills/subagent-driven-development/fleet.md", "- Checker:")
    assert "`worktree scratch -- '<build and capture command>'`" in row
    assert "never swap files in the run's worktree" in row
