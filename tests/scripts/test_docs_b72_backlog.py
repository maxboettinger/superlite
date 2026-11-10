"""B72 (#429): docs/fleet.md, backlog.md and commands/backlog.md name the question.json cut, the report's red field and status --all."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
BACKLOG = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

ESC = "A lead's `question.json` is cut like `plan`'s (header 12, option label 60 at its last whole word, option description 200; each cut named in a `B shortened:` line after the `needs_decision` line), never its question text; a file still invalid after the cut is sent back to the lead once, and the next invalid one parks the batch with `invalid question.json: <errors>`."
RED = "- A saved report JSON (`<sd>/fleet/reports/<id>.json`) carries a `red` string, the red-run evidence: the json block's non-empty `red`, else the reply's last `Red run:` line (a bullet, a bold or backticked label and CRLF line ends work), else `\"\"`; a non-string `red` makes the block unparsable. The report contract `fleet send` appends asks for it between `tests` and `findings`, except in the final reviewer's."
LEAD = "`backlog wait` cuts an over-long header (12), option label (60, at its last whole word, its full text moved to the front of its description) and option description (200) as `plan` does, names each cut in a `B shortened:` line and never cuts the question text; then it checks the file: 1 to 4 distinct questions, each question 1 to 300 characters, a header, and 2 to 4 options with distinct labels. A file still invalid after the cut is sent back to you once to rewrite; the next invalid one parks the batch with `invalid question.json: <errors>`."
MAIN1 = " Shipped batches of earlier plan rounds fold into one `earlier rounds: N shipped (sl backlog status --all lists them)` line after the head line; `\"$SL\" backlog status --all` lists every batch."
CMD1 = " Shipped batches of earlier plan rounds show as one `earlier rounds: N shipped` line; `\"$SL\" backlog status --all` lists them."


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


def test_fleet_escalation_names_the_cut():
    assert ESC in section(FLEET, "## Batch leads", "## Troubleshooting")
    assert "checked strictly, never cut" not in FLEET


def test_fleet_red_bullet_follows_fleet_wait():
    lines = FLEET.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("- `fleet wait [--timeout 540000]"))
    assert lines[i + 1] == RED


def test_backlog_lead_names_the_cut():
    assert LEAD in section(BACKLOG, "## Lead", "## Permissions")
    assert "checks that file strictly and never cuts it" not in BACKLOG


def test_backlog_main_step_one_names_status_all():
    line = next(ln for ln in BACKLOG.splitlines() if ln.startswith('1. `"$SL" backlog status`'))
    assert line.endswith("its last line is `next: sl backlog plan`." + MAIN1)


def test_command_step_one_names_status_all():
    line = next(ln for ln in CMD.splitlines() if ln.startswith('1. Run `"$SL" backlog status`'))
    assert line.endswith("its last line is `next: sl backlog plan`." + CMD1)


def test_quoted_strings_exist_in_code():
    run = (SCRIPTS / "backlog_run.py").read_text(encoding="utf-8")
    assert "cuts = bc.fit_question(obj)" in run and "question_reprompted" in run and "(an over-long header, label or description is cut for you)" in run
    assert "a lead's question keeps its text" in (SCRIPTS / "backlog_checks.py").read_text(encoding="utf-8")
    assert "shipped (sl backlog status --all lists them)" in (SCRIPTS / "backlog_state.py").read_text(encoding="utf-8")
    rep = (SCRIPTS / "fleet_report.py").read_text(encoding="utf-8")
    assert "Red run" in rep and '"red": red or _red_line(text)' in rep
    assert 'fleet_report.REVIEW if role == "final-reviewer" else fleet_report.WORK' in (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
