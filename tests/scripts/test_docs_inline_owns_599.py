from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USING = (ROOT / "skills/using-superlite/SKILL.md").read_text(encoding="utf-8")
SDD = (ROOT / "skills/subagent-driven-development/SKILL.md").read_text(encoding="utf-8")
HOOKS = (ROOT / "docs/hooks.md").read_text(encoding="utf-8")


def test_using_superlite_one_task():
    assert "inline only if small: one task, few files (the guard then lets you write its Owns; say so)" in USING
    assert "one chain" not in USING


def test_sdd_inline_and_graphify_lines():
    assert ("- Inline build (a plan of exactly one task, few files): after `lint --stable` write its Owns yourself "
            "(the guard allows them; no implementer), commit with `commit_task T1`, then Final review.") in SDD
    assert (" When `use` is true it also adds `graphify-out/` to the repo's info/exclude, "
            "so `git status` and `commit_task` skip it.") in SDD


def test_hooks_doc_names_owns_exclude_moved():
    line = next(x for x in HOOKS.splitlines() if x.startswith("- `block-coordinator-edits`"))
    assert "guard_judge.py --owns PATH" in line
    assert "--git-path info/exclude" in line
    assert "moved_to" in line
