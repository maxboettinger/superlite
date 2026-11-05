"""Fixer agents report a denied commit; setup offers the allow rule that avoids it."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE = "Bash(*/skills/subagent-driven-development/scripts/sl commit_task *)"
FIXERS = ["agents/fixer-sonnet.md", "agents/fixer-sonnet-high.md", "agents/fixer-opus.md"]
DENIED = "`commit: denied`"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_offers_the_allow_rule():
    t = read("commands/setup.md")
    assert RULE in t and "permissions.allow" in t


def test_config_doc_names_the_rule():
    t = read("docs/config.md")
    assert "## Permissions (Claude Code)" in t.splitlines() and RULE in t


def test_fixers_report_a_denied_commit():
    for rel in FIXERS:
        t = read(rel)
        assert t.count(DENIED) == 2, rel
        assert "commit_task <Tn>" in t, rel


def test_fixer_commit_lines_match():
    lines = []
    for rel in FIXERS:
        found = [ln for ln in read(rel).splitlines() if ln.startswith("- Commit:")]
        assert len(found) == 1, rel
        lines.append(found[0])
    assert lines[0] == lines[1] == lines[2]


def test_fixing_contract_names_the_fallback():
    t = read("skills/subagent-driven-development/fixing.md")
    assert DENIED in t and "/superlite:setup" in t
