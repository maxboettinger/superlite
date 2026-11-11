"""#438: the fix brief names the run_tests next: cue; #461: commit_task's docstring has no stray parenthesis."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import findings  # noqa: E402


def test_fix_brief_names_the_next_cue():
    text = "\n".join(findings.shared_lines("/abs/sl"))
    assert "`next:`" in text and "`wait:`" in text


def test_commit_task_docstring_parentheses_balance():
    doc = ast.get_docstring(ast.parse((SCRIPTS / "commit_task.py").read_text(encoding="utf-8")))
    assert doc.count("(") == doc.count(")")
