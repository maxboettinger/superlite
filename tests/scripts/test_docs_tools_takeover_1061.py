"""docs/tools.md `orchestrator` row names `takeover [--force]` and the live-owner refusals of #1047 (#1061)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _row() -> str:
    lines = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln.startswith("| `orchestrator`")][0]


def test_row_names_takeover_force():
    assert "`takeover [--force]`" in _row()


def test_row_names_the_live_owner_refusal():
    row = _row()
    assert "still runs" in row and "exit 2" in row and "#1047" in row


def test_row_names_the_backlog_start_refusal():
    assert "`sl backlog start`" in _row()
