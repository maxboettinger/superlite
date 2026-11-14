"""#803: a docs-only task with a cmd= check can be mechanical."""
from __future__ import annotations

from test_0_3_1_scripts import lint

REASON = "KIND: T1 is not mechanical: no test code or contract with exact inputs and outputs"


def kind_plan(tmp_path, owns, tests):
    p = tmp_path / "plan.md"
    p.write_text("\n".join(["# Plan", "**Goal:** test.", "", "```mermaid", "%% taskgraph", "flowchart LR", "  T1", "```", "",
                            "### T1 docs · Complexity 1 · Est. context 10k", f"**Owns:** {owns}", "**Kind:** mechanical",
                            f"**Tests:** {tests}", "**Components:** 1", "**LOC owned:** 20", ""]), encoding="utf-8")
    return p


def test_docs_only_cmd_is_mechanical(tmp_path):
    r = lint(kind_plan(tmp_path, "docs/guide.md", "fast cmd=bunx prettier --check docs"))
    assert "KIND" not in r.stdout, r.stdout


def test_code_owns_cmd_not_mechanical(tmp_path):
    r = lint(kind_plan(tmp_path, "src/a.py", "fast cmd=bunx prettier --check docs"))
    assert REASON in r.stdout, r.stdout


def test_docs_only_without_cmd_not_mechanical(tmp_path):
    r = lint(kind_plan(tmp_path, "docs/guide.md", "fast"))
    assert REASON in r.stdout, r.stdout
