"""docs/hooks.md: the run-detection section and the block-coordinator-edits rules."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")


def section(text, heading):
    m = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def test_run_detection_section():
    assert "## Detecting an active run" in HOOKS
    body = section(HOOKS, "## Detecting an active run")
    for needle in ("~/.superlite/sessions/<session_id>", "pool.json", "prime.md", "stable.json", "sl orchestrator end"):
        assert needle in body, needle


def test_guard_line_names_new_rules():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    for needle in ("outside the project", "quoted", "`cd`"):
        assert needle in line, needle


def test_run_detection_matches_state_order():
    body = section(HOOKS, "## Detecting an active run")
    for needle in ("SUPERLITE_STATE_DIR", "`session` file", "Legacy", "CLAUDE_PROJECT_DIR"):
        assert needle in body, needle


def test_guard_line_names_cd_voiding():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    for needle in ("`pushd`", "`chdir`", "turns the outside base off"):
        assert needle in line, needle


def test_guard_line_names_the_124_rules():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    for needle in ("with or without a writer call", "allowed only by its prefix", "`c''d`", "`CDPATH` set or named",
                   "`rm>/dev/null`", "`GIT_WORK_TREE`", "every `-C` that member names follow", "it may enter",
                   "reads stdin as its program"):
        assert needle in line, needle
    assert "File APIs without a writer call" not in line


def test_new_hooks_documented():
    for name in ("mark-inline-flow", "inline-worktree-guard"):
        assert any(x.startswith(f"- `{name}`") for x in HOOKS.splitlines()), name
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    assert "guard_judge.py" in line


def test_commands_name_inplace():
    for name in ("small", "debug"):
        text = (ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8")
        assert "sl worktree inplace --reason" in text, name


def test_tools_row_names_inplace():
    tools = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    row = next(x for x in tools.splitlines() if x.startswith("| `worktree` |"))
    assert "inplace --reason" in row
