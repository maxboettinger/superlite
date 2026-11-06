"""Debugging skill trigger description."""
from __future__ import annotations

from pathlib import Path

TEXT = (Path(__file__).resolve().parents[2] / "skills/systematic-debugging/SKILL.md").read_text()


def test_description_fires_first():
    expected = ("description: Use first on any bug report, failing test or unexpected behavior, "
                "even when the fix looks obvious, before reading code to fix it")
    assert expected in TEXT.splitlines()


def test_obvious_fixes_stay_quick():
    assert "## Obvious failures: fix directly" in TEXT
    assert "/superlite:debug" in TEXT
