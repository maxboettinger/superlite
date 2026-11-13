import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _blocked_roles():
    text = (ROOT / "skills/subagent-driven-development/fleet.md").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if "never call `Agent` for a superlite role" in l)
    m = re.search(r"never call `Agent` for a superlite role \(([^)]*)\); a hook blocks it", line)
    assert m, line
    return [r.strip() for r in m.group(1).split(",")]


def _hook_arms():
    hook = (ROOT / "hooks/block-coordinator-edits").read_text(encoding="utf-8")
    m = re.search(r'case "\$fname" in\n(.*?)\n\s*esac', hook, re.S)
    assert m, "fleet role case block not found"
    arms = set()
    for line in m.group(1).splitlines():
        lm = re.match(r"\s*([a-z|-]+)\) frole=", line)
        assert lm, line
        arms.update(lm.group(1).split("|"))
    return arms


def _covers(role, arm):
    return arm == role or arm.startswith(role + "-")


def test_fleet_md_blocked_roles_name_writer():
    assert "writer" in _blocked_roles()


def test_each_listed_role_has_a_hook_arm():
    arms = _hook_arms()
    for role in _blocked_roles():
        name = role.replace(" ", "-")
        assert any(_covers(name, a) for a in arms), (role, sorted(arms))


def test_each_hook_arm_is_listed_in_fleet_md():
    names = [r.replace(" ", "-") for r in _blocked_roles()]
    for arm in _hook_arms():
        assert any(_covers(n, arm) for n in names), (arm, names)
