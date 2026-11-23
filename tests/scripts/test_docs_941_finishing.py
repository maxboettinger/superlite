"""#941: finishing skill, task template and README wording."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def _has_once(text, phrase):
    assert text.count(phrase) == 1, phrase


def test_finishing_rules_941():
    t = _read("skills/finishing-a-development-branch/SKILL.md")
    for p in ("**Detached HEAD** (no branch name)", "its path is under `.claude/worktrees/`",
              "never add `--force`", "- Remove a worktree with `--force`."):
        _has_once(t, p)


def test_template_and_readme_941():
    _has_once(_read("skills/writing-plans/task-template.md"), "could write only one reasonable thing from it")
