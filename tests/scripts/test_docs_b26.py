"""backlog.md (## Main, ## Lead) and docs/fleet.md name the 1.5.23-1.5.33 backlog and fleet changes (#274)."""
from __future__ import annotations

from test_plan_tools import ROOT

BACKLOG = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")

B_FRESH = "Start main in a fresh session: one that already loaded another superlite skill or command (start, brainstorming, writing-plans, subagent-driven-development, finishing) tells the user to run `/clear` and `/superlite:backlog` again, and ends its turn."
B_PLAN = "Over-long question texts are cut, not refused: a header to 12, an option label to 60 and an option description to 200 characters (a ` (Recommended)` suffix kept), each cut named in a `shortened: \"<question>\" <field>: N -> M characters` line (at most 5, then `shortened: K more`); a question over 300 characters still fails the plan."
B_START = "4. `\"$SL\" backlog start [B ...] [--cap 2] [--model opus]`. Several ids (`start B7 B10`) are checked one by one: each refused batch prints its `BLOCKED:` reason first, the others still start, and the exit is 2 when any was refused. Exit 3 (Herdr missing) is BLOCKED."
B_REPROMPT = "A lead that stops without a Status line gets one re-prompt (no wait line); its next such stop parks the batch with `no status in stop text: <text>`, and `start` or `answer` resets the count. A stop whose transcript lags (blank, or without the status its cut `last` line holds) is re-read for 10 s from the stop; after that a cut line with a status parks the batch with `<cut line> (transcript unread)`, one without gets the re-prompt."
B_DONE = "6. A batch whose lead could not merge (its merge step was denied, so the lead ended BLOCKED and `wait` parked it) is main's to ship with one command: `\"$SL\" backlog ship B merge --from-main` (main only, refused in any fleet worker; it needs the ship approval, a parked batch and its bumped version). It takes the ship lock as main, rebases the worktree onto the default branch, bumps the version again when the default branch already has it, runs `maxapp ship`, then marks the batch shipped, records its PR and version, writes its summary, releases the ship lock and stops its lead. exit 4 is WAIT or RERUN: run it again. A CONFLICT (5), RED (6) or BLOCKED (3) releases the lock and keeps the batch parked with the reason; `\"$SL\" backlog start B` resumes its lead to fix a conflict or a red check. A batch main shipped by hand (`maxapp ship -C <worktree>`) is recorded with `\"$SL\" backlog ship B done --pr N [--version X]` (main only; `gh pr view N` must read MERGED)."
B_MAIN = (B_FRESH, B_PLAN, B_START, B_REPROMPT, B_DONE)
B_LEAD = "`backlog wait` cuts an over-long header (12), option label (60, at its last whole word, its full text moved to the front of its description) and option description (200) as `plan` does, names each cut in a `B shortened:` line and never cuts the question text; then it checks the file: 1 to 4 distinct questions, each question 1 to 300 characters, a header, and 2 to 4 options with distinct labels. A file still invalid after the cut is sent back to you once to rewrite; the next invalid one parks the batch with `invalid question.json: <errors>`."

F_SEND = "Two of task ids, `--text` and `--brief` in one call (an empty `--text` counts) exit 2 with `error: send takes task ids, --text or --brief, not two of them` on stderr, before anything is sent."
F_SPAWN = "A start that fails with `not an available shell` (a pane freed a moment ago) is retried once after 3 s on the same pane; a BLOCKED reason after that retry ends `; retried once`, and `--for-dispatch` adds `; rerun sl fleet spawn --for-dispatch` to its `BLOCKED: Tn not sent (...)` line."
F_WAIT = "A stop record whose transcript reads empty, or lacks the status its cut `last` line holds, is re-read for 10 s; after that the worker ends `UNKNOWN` with ` (transcript unread)` at the end of its line, is kept (not stopped), and its `.md` shows the cut line as a labelled block plus the last pane lines."
F_HOLD = "A task that waits on a human step is held with `sl hold Tn --reason R` (ledger line `- Hold Tn: R`) and released with `sl hold --release Tn`; `dispatch` never offers it and prints `held=Tn R` on stderr, and `/superlite:status` lists each held task with its id and reason."
F_MAIN = "Main starts in a fresh session: one that already loaded another superlite skill or command runs `/clear` first. `backlog plan` cuts an over-long question header (12), option label (60) and description (200) and names each cut in a `shortened:` line (at most 5, then `shortened: K more`). `start B7 B10` checks each id on its own: refusals print first, the others still start, exit 2 when any was refused. A batch whose lead's merge was denied is shipped by main with `sl backlog ship B merge --from-main` (main only): it takes the ship lock, rebases (a conflict aborts the rebase), bumps the version again when the default branch already has it, runs `maxapp ship`, marks the batch shipped, writes its summary, releases the ship lock and stops its lead; a batch main shipped by hand (`maxapp ship -C <worktree>`) is recorded with `sl backlog ship B done --pr N [--version X]`."
F_ESC = "A lead's `question.json` is cut like `plan`'s (header 12, option label 60 at its last whole word, option description 200; each cut named in a `B shortened:` line after the `needs_decision` line), never its question text; a file still invalid after the cut is sent back to the lead once, and the next invalid one parks the batch with `invalid question.json: <errors>`. A lead that stops without a Status line gets one re-prompt; its next such stop parks the batch with `no status in stop text: <text>` (`start` and `answer` reset it). A stop record whose transcript lags is re-read for 10 s from the stop; then a cut `last` line holding a status parks the batch with `<cut line> (transcript unread)`."
F_ROW1 = "| Lead stops without a status | A lead ends its turn with no Status line, twice | the first stop prints nothing and re-prompts the lead; the second parks the batch with `no status in stop text: <text>` |"
F_ROW2 = "| Main ships a denied merge | The lead's `merge` was denied and `wait` parked the batch; main runs `ship B merge --from-main` | `status` shows the batch shipped with its PR; the ship lock is free |"


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


def test_main_section_names_new_steps():
    main = section(BACKLOG, "## Main", "## Lead")
    for s in B_MAIN:
        assert s in main, s[:60]


def test_main_steps_numbered():
    assert BACKLOG.index("\n6. A batch whose lead") < BACKLOG.index("\n7. Hold work:")
    assert "\n6. Hold work:" not in BACKLOG
    assert "`\"$SL\" backlog start [B] [--cap 2]" not in BACKLOG


def test_lead_section_names_question_check():
    assert B_LEAD in section(BACKLOG, "## Lead", "## Permissions")


def test_fleet_sections_name_changes():
    commands = section(FLEET, "## Commands", "## How a run looks")
    for s in (F_SEND, F_SPAWN, F_WAIT):
        assert s in commands, s[:60]
    assert F_HOLD in section(FLEET, "## How a run looks", "## Smoke test")
    leads = section(FLEET, "## Batch leads", "## Troubleshooting")
    for s in (F_MAIN, F_ESC):
        assert s in leads, s[:60]


def test_fleet_rows_are_table_rows():
    lines = section(FLEET, "## Batch leads", "## Troubleshooting").split("\n")
    for row in (F_ROW1, F_ROW2):
        assert row in lines
        assert row.count(" | ") == 2
    assert lines.index(F_ROW1) > lines.index(next(x for x in lines if x.startswith("| Two leads ship in turn |")))
