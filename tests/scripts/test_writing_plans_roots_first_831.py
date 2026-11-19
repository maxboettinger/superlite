"""writing-plans: root tasks first, then the rest (#831); the header names **Read first:** (#798)."""
from pathlib import Path

WP = Path(__file__).resolve().parents[2] / "skills" / "writing-plans"


def read(name):
    return (WP / name).read_text(encoding="utf-8")


def test_split_rule_one_writes_roots_first():
    s = read("split.md")
    assert "1. **Root tasks first, then the rest.** Write the plan in two Writes" in s
    assert "One Write" not in s and "in one Write" not in s
    assert "Run `prune` and `lint --stable` on it and dispatch its `DISPATCH NOW:` line." in s
    assert "Declare a task in the taskgraph only in the Write that adds its block" in s
    assert "a later consumer of a root task keeps its edge and waits for that task's commit" in s


def test_core_names_roots_first_and_read_first():
    core = read("SKILL.md")
    assert "the seven rules (root tasks first, producers first," in core
    assert "one Write" not in core
    assert "`**Read first:** a, b` (files every primed implementer reads in full before its first task)" in core
    assert len(core.encode("utf-8")) < 11960
