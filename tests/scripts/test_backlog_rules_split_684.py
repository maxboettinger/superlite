"""Backlog rules split by reader (#684): no rule sentence lost, each reader its file."""
import re
from pathlib import Path

from _fixtures import FIXTURES

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
FIXTURE = FIXTURES / "rules_684" / "backlog.txt"

_MARKER = re.compile(r"^\s*(?:#+\s+|[-*]\s+|\d+[a-z]?\.\s+)")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\"(*\[])")


def rule_sentences(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        line = _MARKER.sub("", line)
        if not line.strip() or line.strip() == "---":
            continue
        for part in _SPLIT.split(line):
            part = " ".join(part.split())
            if len(part) >= 12:
                out.add(part)
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_backlog_rule_lost():
    have = rule_sentences(_read(SDD / "backlog.md") + "\n" + _read(SDD / "backlog-main.md"))
    want = [s for s in _read(FIXTURE).splitlines() if s.strip()]
    lost = [s for s in want if s not in have]
    assert not lost, (
        f"{len(lost)} rule sentence(s) lost from backlog.md + backlog-main.md; "
        "edit the fixture line when a rewrite is on purpose:\n"
        + "\n".join(f"- {s[:200]}" for s in lost[:5])
    )


def test_each_reader_has_its_section():
    lead = _read(SDD / "backlog.md")
    main = _read(SDD / "backlog-main.md")
    assert "## Lead" in lead and "## Permissions" in lead
    assert "## Main" not in lead
    assert "## Main" in main and "## Limits" in main
    assert "## Lead" not in main


def test_simulators_pointer_names_lead_file():
    """The fixture line was rewritten on purpose: '(Lead: Simulators)' became '(`backlog.md`, Lead: Simulators)'."""
    main = _read(SDD / "backlog-main.md")
    assert "(Lead: Simulators)" not in main
    assert "(`backlog.md`, Lead: Simulators)" in main


def test_command_names_only_main_file():
    cmd = _read(ROOT / "commands" / "backlog.md")
    assert "backlog-main.md" in cmd
    assert "subagent-driven-development/backlog.md" not in cmd


def test_command_steps_and_experiment():
    cmd = _read(ROOT / "commands" / "backlog.md")
    for needle in ("step B:", '"steps"', "experiment set", "experiment next", "experiment report"):
        assert needle in cmd, needle
    assert "experiment report" in _read(SDD / "backlog-main.md")
