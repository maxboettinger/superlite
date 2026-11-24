"""B331: docs/fleet.md names the backlog note, room wait, ship lock checks and queue grace (#1113-#1115, #1134)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def line_starting(start):
    found = [x for x in FLEET.split("\n") if x.startswith(start)]
    assert len(found) == 1
    return found[0]


def backlog_paragraph():
    return line_starting("`/superlite:backlog` works a whole issue backlog")


def ship_lock_line():
    return line_starting("Ship lock: leads ship one at a time.")


def read(name):
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_backlog_paragraph_names_note_and_room():
    p = backlog_paragraph()
    for text in [
        "sl backlog note FILE",
        "BLOCKED: sl backlog note runs only in the main session",
        "run end: standing note from <file> (<time>, <n> lines) still goes into every later lead brief; sl backlog note /dev/null clears it",
        "waiting for room: cap 0; start retried every 300 s until --timeout",
        "no free slot for B (cap 0); rerun once the cap: line shows room",
    ]:
        assert p.count(text) == 1, text
    assert "sl backlog start --note /dev/null clears it" not in p


def test_ship_lock_line_names_checks_and_grace():
    s = ship_lock_line()
    for text in [
        "refused: uncommitted changes in the worktree (",
        "lock held: fix it, then run sl backlog ship B lock again",
        "LIVE_GRACE_MS",
        "2 minutes",
    ]:
        assert s.count(text) == 1, text


def test_quoted_text_is_in_the_scripts():
    assert "BLOCKED: sl backlog note runs only in the main session" in read("backlog.py")
    run = read("backlog_run.py")
    assert "still goes into every later lead brief; sl backlog note /dev/null clears it" in run
    assert "start retried every {a.retry} s until --timeout" in run
    ship = read("backlog_ship.py")
    assert "refused: uncommitted changes in the worktree (" in ship
    assert "lock held: fix it, then run sl backlog ship {bid} lock again" in ship
    assert "LIVE_GRACE_MS = 120000" in read("ship_lock.py")
