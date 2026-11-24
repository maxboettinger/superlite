"""docs/tools.md `fleet` row and fleet.with_constraints record that review and fix briefs keep the plan's Global constraints (#1059, #635)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = ROOT / "skills" / "subagent-driven-development" / "scripts" / "fleet.py"


def _row() -> str:
    lines = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln.startswith("| `fleet`")][0]


def test_row_names_the_constraints_append():
    assert "(`fleet.with_constraints`, #635; none added when the brief already has the heading)" in _row()


def test_row_records_the_keep_ruling():
    assert "review and fix briefs keep them by ruling (#1059), since reviewers and fixers get the constraints only there (#900);" in _row()


def test_with_constraints_comment_names_the_ruling():
    line = [ln for ln in FLEET.read_text(encoding="utf-8").splitlines() if ln.startswith("def with_constraints(")][0]
    assert "review and fix briefs keep it by ruling (#1059) | O(L + len)" in line
