from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def test_implementers_name_the_task_test_command():
    for n in ("agents/implementer.md", "agents/implementer-haiku.md"):
        assert "cmd=" in read(n), n


def test_writing_plans_names_contracts_and_prose():
    t = "\n".join(read(p) for p in ("skills/writing-plans/SKILL.md", "skills/writing-plans/task-template.md", "skills/writing-plans/split.md"))
    for s in ("acyclic_siblings", "tsconfig", "prose"):
        assert s in t, s


def test_sdd_fleet_blocks_checker_and_language_names_launch():
    line = next(l for l in read("skills/subagent-driven-development/fleet.md").splitlines() if "never call `Agent` for a superlite role" in l)
    assert "checker" in line
    assert "`launch`" in read("docs/language.md")
