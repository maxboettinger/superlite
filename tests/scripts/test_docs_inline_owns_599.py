from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USING = (ROOT / "skills/using-superlite/SKILL.md").read_text(encoding="utf-8")
SDD = (ROOT / "skills/subagent-driven-development/SKILL.md").read_text(encoding="utf-8")
HOOKS = (ROOT / "docs/hooks.md").read_text(encoding="utf-8")


def test_using_superlite_one_task():
    assert "inline only if small (one task, few files; say so)" in USING
    assert "one chain" not in USING


def test_sdd_keeps_main_text():
    assert "- Inline build (a plan of exactly one task" not in SDD
    assert "graphify-out" not in SDD


def test_hooks_doc_names_owns_exclude_moved():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    assert "guard_judge.py --owns PATH" in line
    assert "--git-path info/exclude" in line
    assert "moved_to" in line


def test_hooks_doc_exclude_matches_code():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    assert "passes as git's own exclude file" in line
    assert "defines a `git` function or alias" in line
    assert "one known shell directory" not in line
