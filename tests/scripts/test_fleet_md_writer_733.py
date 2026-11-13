import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _blocked_roles():
    text = (ROOT / "skills/subagent-driven-development/fleet.md").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if "never call `Agent` for a superlite role" in l)
    m = re.search(r"never call `Agent` for a superlite role \(([^)]*)\); a hook blocks it", line)
    assert m, line
    return [r.strip() for r in m.group(1).split(",")]


def test_fleet_md_blocked_roles_name_writer():
    assert "writer" in _blocked_roles()


def test_fleet_md_blocked_roles_match_hook_arms():
    hook = (ROOT / "hooks/block-coordinator-edits").read_text(encoding="utf-8")
    roles = _blocked_roles()
    for word, arm in (("implementer", "implementer"), ("fixer", "fixer"), ("package reviewer", "package-reviewer"),
                      ("final reviewer", "final-reviewer"), ("researcher", "researcher"), ("checker", "checker"),
                      ("writer", "writer")):
        assert word in roles, word
        assert arm in hook, arm
