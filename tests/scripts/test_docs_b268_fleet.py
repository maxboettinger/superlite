"""B268 (#1000): docs/fleet.md names the `; no count cap` suffix, the empty `fleet restore` line, the report contract's tests wording and the run_tests tested line and bundle WARNING; each quoted message is checked against the script printing it."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
LINES = TEXT.splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

NAMED = [  # (section, text the section holds exactly once)
    ("## Capacity", "`; no count cap`"),
    ("## Commands", "`fleet restore: nothing to restore in <sd>`"),
    ("## Roles", "`\"<test command and result line, with the tree and result bundle run_tests named>\"`"),
    ("## Run root and task trees", "`run_tests: tested tree <t>[; lacks N changed file(s) of the run root: ...][; N file(s) changed while the tests ran: ...][; result bundle <path> (+N more)]`"),
    ("## Run root and task trees", "`run_tests: WARNING: result bundle <b> is outside the tree <t>: it may hold another build's results`"),
]
CODE = [  # (script, literal its source holds)
    ("machine_load.py", '("" if lim else "; no count cap")'),
    ("fleet_restore.py", 'f"fleet restore: nothing to restore in {sd}"'),
    ("fleet_report.py", '"tests": "<test command and result line, with the tree and result bundle run_tests named>"'),
    ("run_tests.py", "print(f\"run_tests: {'tested ' if tree else ''}{tail}\""),
    ("run_tests.py", 'print(f"run_tests: WARNING: {note}"'),
    ("run_tests.py", "is outside the tree {TESTED['tree']}: it may hold another build's results"),
]


def _section(name):
    at = LINES.index(name)
    end = next((i for i in range(at + 1, len(LINES)) if LINES[i].startswith("## ")), len(LINES))
    return "\n".join(LINES[at:end])


@pytest.mark.parametrize("section,text", NAMED)
def test_section_names_it_once(section, text):
    assert _section(section).count(text) == 1


def test_tree_bullet_follows_the_fast_bullet():
    at = next(i for i, x in enumerate(LINES) if x.startswith("- A fleet worker's `run_tests --fast` without `--task`"))
    assert LINES[at + 1].startswith("- A run in a tree prints `run_tests: tested tree <t>")


@pytest.mark.parametrize("script,literal", CODE)
def test_quoted_texts_match_the_code(script, literal):
    assert literal in (SCRIPTS / script).read_text(encoding="utf-8")
