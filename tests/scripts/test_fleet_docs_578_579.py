"""Docs: fleet.md names the one-call spawn, the BUSY finisher suffix and the reported/dead status (#578, #579)."""
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/fleet.md"

SENTENCES = [
    "One call does all three: `fleet spawn --role R [--tier T] --brief <abs file> [--label L] --wait [--timeout 540000] --plan $PLAN` (a missing brief exits 2 before any pane; a failed send stops the worker, `BLOCKED: Wn L not sent (...)`, exit 3).",
    "`BUSY Wn Wm (reported: Wk <json>)` lists the workers still running and names this call's finishers; `--timeout` is in ms (a bare number under 1000 is read as seconds; `540s` and `9m` work too). Each report is returned once: `Wn <label> already collected: <json>` means another wait got it.",
    "`\"$SL\" fleet status` lists workers; `reported` means the turn ended and `fleet wait Wn` collects it (`fleet report Wn` reads it first), `dead` (also `Wn <label> DEAD` from wait) means its agent is gone: the line names the fresh `fleet spawn`. `fleet send` to a stopped or dead worker exits 2 with that spawn line. `fleet stop Wn` or `--all` closes them. At freeze, `\"$SL\" fleet stop --all` runs before `trees clean` (no-op without fleet mode).",
]


def test_fleet_md_names_new_lines():
    text = DOC.read_text()
    for s in SENTENCES:
        assert text.count(s) == 1, s
