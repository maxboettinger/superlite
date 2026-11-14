import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTE = "run end: standing note from <file> (<time>, <n> lines) still goes into every later lead brief; sl backlog start --note /dev/null clears it"


def step(n):
    for line in (ROOT / "commands/backlog.md").read_text().splitlines():
        if line.startswith(f"{n}. "):
            return " ".join(line.split())
    raise AssertionError(f"no step {n}")


def test_command_step2_names_depends_lines():
    s = step(2)
    assert "depends: B no longer waits for D: no shared file and no reason" in s
    assert "depends: B waits for D: <reason> (the order the dropped dependencies held)" in s
    assert "B waits for D: <reason>" in s


def test_command_step5_names_note_line():
    assert NOTE in step(5)


def test_command_step8_clears_or_keeps_note():
    s = step(8)
    assert '"$SL" backlog start --note /dev/null' in s
    assert "standing note" in s
    assert "closing report" in s


def test_main_rules_name_note_line():
    t = " ".join((ROOT / "skills/subagent-driven-development/backlog-main.md").read_text().split())
    assert NOTE in t
    assert "--note /dev/null" in t


def test_tools_row_names_note_line():
    row = next(l for l in (ROOT / "docs/tools.md").read_text().splitlines() if l.startswith("| `backlog_run` |"))
    assert "run end: standing note" in row
    assert "--note /dev/null" in row
