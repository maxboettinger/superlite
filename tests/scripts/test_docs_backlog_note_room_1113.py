from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTE = "run end: standing note from <file> (<time>, <n> lines) still goes into every later lead brief; sl backlog note /dev/null clears it"
HOLD = "waiting for room: cap 0; start retried every 300 s until --timeout"


def flat(rel):
    return " ".join((ROOT / rel).read_text().split())


def test_docs_name_note_command():
    for rel in ("commands/backlog.md", "skills/subagent-driven-development/backlog-main.md"):
        t = flat(rel)
        assert "backlog note FILE" in t and "starts no batch" in t, rel


def test_docs_name_run_end_note_clear():
    for rel in ("commands/backlog.md", "skills/subagent-driven-development/backlog-main.md"):
        assert NOTE in flat(rel), rel


def test_main_rules_name_room_wait():
    t = flat("skills/subagent-driven-development/backlog-main.md")
    assert HOLD in t and "no free slot for B (cap 0)" in t
