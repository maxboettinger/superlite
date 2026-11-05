"""`/superlite:debug` without a plan fixes inline; fixers run only inside a plan run."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_debug_command_fixes_inline():
    t = read("commands/debug.md")
    assert "Fix inline" in t
    assert "Fixes go to fix-only agents by tier" not in t


def test_debug_command_scopes_fixers_to_plan_runs():
    assert "only inside a plan run" in read("commands/debug.md")


def test_debugging_skill_names_the_inline_rule():
    t = read("skills/systematic-debugging/SKILL.md")
    assert "/superlite:debug" in t
    assert "only inside a plan run" in t


def test_ensure_precedes_inline_fix():
    t = read("commands/debug.md")
    assert "worktree ensure" in t and "Fix inline" in t
    assert t.index("worktree ensure") < t.index("Fix inline")
