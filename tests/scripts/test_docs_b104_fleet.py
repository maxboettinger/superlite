"""B104 (#495): the fleet docs name the run the fleet rule reads, the owner skip and the no-plan PLAN form."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = (ROOT / "docs" / "plans" / "2026-11-11-fleet-rule-run-state.md").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
SDD = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")


def _text(name):
    m = re.search(rf"{name} \(verbatim[^)]*\): ``(.+?)``$", PLAN, re.M) or re.search(rf"{name} = ``(.+?)``$", PLAN, re.M)
    assert m, name
    return m.group(1)


D1, D2, S1 = _text("D1"), _text("D2"), _text("S1")


def _section(text, heading):
    start = text.index(heading + "\n")
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def test_fleet_doc_names_run_state():
    assert DOCS.count("is blocked. " + D1) == 1
    assert "is blocked. " + D1 in _section(DOCS, "## What it is")


def test_fleet_doc_troubleshooting_names_stale_fleet():
    assert D2 in _section(DOCS, "## Troubleshooting").splitlines()


def test_sdd_fleet_names_run_state():
    assert SDD.count("a hook blocks it. " + S1) == 1
