"""B143 (#601): setup, writing-plans and checker texts name the launch entry."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # O(1)


def _t(rel):
    return (ROOT / rel).read_text(encoding="utf-8")  # O(n)


SETUP_BULLET = "- for a project with an app, widget, app extension or web UI target: whether its `.superlite/test-cmd.json` (the main checkout's from a linked worktree) holds a `launch` entry, which says per platform whether a worker may launch the app and with which data."  # O(1)
SETUP_TAIL = "`build_prime` copies it into every implementer's prime, and plans name its launch arguments and fixtures in their `## Running-app checks` `reach:` parts;"  # O(1)
REACH = "- **Reach.** `reach:` names how the changed state is reached in the running app: a launch argument, fixture, URL or UI path from the project's `launch` entry in `.superlite/test-cmd.json`"  # O(1)
REACH_TAIL = "Never leave the way in for the checker to find: it reports such a check NOT REACHABLE."  # O(1)
FLAG = "| \"The checker will find a way into that state\" | `reach:` names the launch argument, fixture, URL or preview, or a task adds one. |"  # O(1)
CHECKER = "- Read the `launch` entry in `<ROOT>/.superlite/test-cmd.json` (the main checkout's when ROOT has none): never launch the app on a platform it marks `\"worker\": false` (its Debug build shares the user's own app data). A check there passes only through a preview or snapshot render (below); else it is NOT REACHABLE, naming that entry."  # O(1)


def test_setup_texts():
    s = _t("commands/setup.md")  # O(n)
    assert SETUP_BULLET in s  # O(n)
    assert SETUP_TAIL in s  # O(n)
    assert s.index("find it;") < s.index(SETUP_BULLET)  # O(n)


def test_setup_launch_example_parses():
    s = _t("commands/setup.md")  # O(n)
    m = re.search(r'`("launch": \{.*?\}\})`', s)  # O(n)
    assert m  # O(1)
    d = json.loads("{" + m.group(1) + "}")["launch"]  # O(n)
    workers = {k: v["worker"] for k, v in d.items()}  # O(n)
    assert True in workers.values() and False in workers.values()  # O(n)
    assert all(v.get("why") for v in d.values() if v["worker"] is False)  # O(n)


def test_writing_plans_texts():
    s = _t("skills/writing-plans/SKILL.md")  # O(n)
    assert REACH in s and REACH_TAIL in s  # O(n)
    assert FLAG in s  # O(n)
    assert s.rstrip().index(FLAG) > s.index("## Red flags")  # O(n)


def test_reach_rule_after_running_app_checks():
    lines = _t("skills/writing-plans/SKILL.md").splitlines()  # O(n)
    i = next(n for n, l in enumerate(lines) if l.startswith("- **Running-app checks.**"))  # O(n)
    assert lines[i + 1].startswith("- **Reach.**")  # O(1)


def test_checker_text():
    s = _t("agents/checker.md")  # O(n)
    assert CHECKER in s  # O(n)
    sec = s.split("## Every check runs")[1].split("\n## ")[0].rstrip().splitlines()  # O(n)
    assert sec[-1] == CHECKER  # O(1)
