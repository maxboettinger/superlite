"""docs/fleet.md states the research worker's limits: no Write tool, the 300-word cap, the research path (#337)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def line_starting(prefix):
    found = [ln for ln in FLEET.splitlines() if ln.startswith(prefix)]
    assert len(found) == 1, prefix
    return found[0]


def test_research_row_names_missing_write_and_model_pin():
    row = line_starting("| `research` |")
    for s in ("read-only (Read, Grep, Glob; no Write, Edit or shell)", "(`--tier haiku\\|opus` pins another model"):
        assert s in row, s


def test_research_limits_paragraph():
    para = line_starting("Research worker limits:")
    for s in ("cannot write a report file", "at most 300 words", "`<sd>/fleet/reports/<label>.md`", "brief's file name without `.md`",
              "one brief per question and one worker each", "`<sd>/briefs/<name>.md`",
              "`sl fleet spawn --role research --plan PLAN`", "`sl fleet send Wn --brief", "`sl fleet wait Wn --plan PLAN`",
              "Bash timeout 600000", "before a plan exists"):
        assert s in para, s


def test_doc_cap_matches_the_agent_file():
    agent = (ROOT / "agents" / "researcher.md").read_text(encoding="utf-8")
    assert "at most 300 words" in agent
    assert "at most 300 words" in line_starting("Research worker limits:")
