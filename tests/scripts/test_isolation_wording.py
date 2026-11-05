"""Flows call `worktree ensure`; the old no-worktree wording is gone."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ["skills/brainstorming/SKILL.md", "skills/writing-plans/SKILL.md", "skills/subagent-driven-development/SKILL.md",
         "commands/small.md", "commands/debug.md"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_no_worktree_wording_is_gone():
    for d in ("skills", "commands"):
        for p in (ROOT / d).rglob("*.md"):
            t = p.read_text(encoding="utf-8")
            assert "(no worktree)" not in t and "create that worktree or branch first" not in t, p


def test_flows_call_the_tool():
    for rel in FLOWS:
        assert "worktree ensure" in read(rel), rel
    assert read("skills/brainstorming/SKILL.md").count("worktree ensure") >= 2


def test_task_message_names_root():
    assert "ROOT=<abs run root>" in read("skills/subagent-driven-development/SKILL.md")


def test_claude_code_reference_names_enterworktree():
    t = read("skills/using-superlite/references/claude-code-tools.md")
    assert "EnterWorktree" in t and "path" in t


def test_using_superlite_within_limit():
    assert len(read("skills/using-superlite/SKILL.md")) <= 1500


def test_commands_are_code_spans_with_runnable_path():
    for rel in ("commands/small.md", "commands/debug.md"):
        assert "`<superlite skill dir>/subagent-driven-development/scripts/sl worktree ensure <topic>`" in read(rel), rel
    for rel in ("skills/brainstorming/SKILL.md", "skills/writing-plans/SKILL.md"):
        t = read(rel)
        assert "`<skill-dir>/../subagent-driven-development/scripts/sl worktree ensure <topic>`" in t, rel
        assert "`**Worktree:** none`" in t, rel
    assert "run `<skill-dir>/../subagent-driven-development/scripts/sl worktree ensure" in read("skills/brainstorming/SKILL.md").split("**Bounded:**")[1].split("**Architectural:**")[0]


def test_ensure_precedes_first_write_in_commands():
    s = read("commands/small.md")
    assert s.index("worktree ensure") < s.index("Do it inline")
    d = read("commands/debug.md")
    assert d.index("worktree ensure") < d.index("write the failing regression test")


def test_no_shared_checkout_branching_left():
    for rel in FLOWS:
        t = read(rel)
        assert "if on the default branch (no" not in t and "branch `superlite/<topic>` if on the default" not in t, rel
    assert "Run root: a worktree" in read("skills/subagent-driven-development/SKILL.md")


def test_enterworktree_is_optional_harness_help():
    t = read("skills/using-superlite/references/claude-code-tools.md")
    assert "Optional harness help, not a superlite tool" in t and "`EnterWorktree` with `path`" in t


def test_ai_orchestrator_section_names_worktree_ensure():
    sec = read("skills/brainstorming/SKILL.md").split("## AI orchestrator")[1].split("## Red flags")[0]
    assert "worktree ensure" in sec
