"""SDD fleet.md, backlog-main.md and docs/fleet.md name #906 and #1015 (B285, #1031)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
SCRIPTS = SDD / "scripts"

PINNED = "(a missing brief exits 2 before any pane; a failed send stops the worker, `BLOCKED: Wn L not sent (...)`, exit 3)."
REFUSE = " A brief file outside the project, the run folder and the plugin skills folder, or a brief that (with the plan's Global constraints, or a review spawn's `--note`) names such a path outside fenced code, exits 2 the same way with one `error:` line (every role but lead; `fleet send Wn --brief` checks it too): copy the file into `.superlite/briefs/` and name the copy (#1015, #1024)."
LEAD = "- Lead: `fleet spawn --role lead --plan P [--brief F]` starts a lead for a plan in another worktree (the checkout P lies in; its run is `<worktree>/.superlite`; without `--brief` its generated brief builds and commits but never pushes, merges or ships). `\"$SL\" fleet status` prints one `lead Wn <worktree>: plan <plan> (N tasks); ...; workers busy K; question: open <path>` line per live lead, batch leads too. Details: docs/fleet.md \"Leads outside backlog mode\" (#906)."
DECIDE = "  - `NEEDS_DECISION` (a lead's report): the line ends ` question=<worktree>/.superlite/question.json` when that file exists; read it, ask the user, answer with `\"$SL\" fleet send Wn --text \"...\"`, then wait again (#906)."
PROGRESS = "A running lead's progress without its pane: `\"$SL\" fleet status` prints one `lead Wn <worktree>: ...` line per live lead, batch leads too (plan and task count, task groups, busy workers, `question: open <path>` while its question.json waits) (#906)."
SECTION = "## Plan leads outside backlog mode\n\nA plan outside the backlog (another repository's or worktree's) gets its own lead: `\"$SL\" fleet spawn --role lead --plan P [--brief F]` (docs/fleet.md, \"Leads outside backlog mode\"). Its `fleet wait` line ends at DONE, BLOCKED or `NEEDS_DECISION`, a report status whose line ends ` question=<worktree>/.superlite/question.json`: ask the user with AskUserQuestion, then answer with `\"$SL\" fleet send Wn --text \"<answer>\"`. A plan lead starts without the ship allow rules and its generated brief never pushes, merges or ships: main decides the integration (#906).\n"
LOCATION = " A brief file that itself lies outside them gets `error: brief F is outside the project, the run folder and the plugin skills folder; a worker cannot read it: move it into <run folder>/briefs/ (#1015)` instead."


def test_sdd_fleet_names_1015_and_906():
    text = (SDD / "fleet.md").read_text(encoding="utf-8")
    assert text.count(PINNED) == 1
    assert PINNED + REFUSE in text
    lines = text.splitlines()
    layers = next(i for i, l in enumerate(lines) if l.startswith("- Test layers, in a repo with"))
    assert lines[layers + 1] == LEAD
    ctx = next(i for i, l in enumerate(lines) if l.startswith("  - `NEEDS_CONTEXT`:"))
    assert lines[ctx + 1] == DECIDE


def test_backlog_main_names_906():
    text = (SDD / "backlog-main.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    lean = next(i for i, l in enumerate(lines) if l.startswith("Main keeps a lean context:"))
    assert lines[lean + 1] == PROGRESS
    assert text.endswith("\n\n" + SECTION)


def test_docs_fleet_names_location_error():
    text = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "`, exit 2, nothing started." + LOCATION + " Copy each such file" in text


def test_messages_match_code():
    io = (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
    assert "is outside the project, the run folder and the plugin skills folder; a worker cannot read it: move it into {sd.resolve()}/briefs/ (#1015)" in io
    assert 'f" question={question}"' in io
    st = (SCRIPTS / "status.py").read_text(encoding="utf-8")
    for s in ('f"workers busy ', 'f"question: open {q}"'):
        assert s in st, s
    assert "NEEDS_DECISION" in (SCRIPTS / "fleet_report.py").read_text(encoding="utf-8")
