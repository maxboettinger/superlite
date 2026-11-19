"""B268 (#1000): docs/tools.md names the run_tests tested line and bundle WARNING, predict's suite and review terms, lint SIZE's extra_min NOTE, the live in-progress switch, the linked-spec rules, the resume-brief lines, the brief check, the cut-code packet title, trees.prepare_at, fleet collect, the report home, the researcher Bash hook and pytest skip names; each quoted message is checked against the script printing it."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
LINES = TEXT.splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

NAMED = [  # (row, text the row holds exactly once)
    ("run_tests", "`run_tests: tested <tested>`"),
    ("run_tests", "`run_tests: WARNING: result bundle <b> is outside the tree <t>: it may hold another build's results`"),
    ("predict", "`- tests fast`"),
    ("predict", "0.2 s `case_s` prior"),
    ("predict", "`review.round_min`"),
    ("predict", "`extra_min` (their minutes together)"),
    ("plan_tools", "`NOTE: Tn predicted X min, Y of it outside the size band (existing tests, review rounds); splitting does not shrink it`"),
    ("backlog_brief", "`SPEC_TRIAGE`"),
    ("backlog_brief", "`SPEC_LEAD`"),
    ("backlog_run", "`- Checkpointed tasks (ledger .superlite/progress.md; hidden checkpoints are not in the commits above): N`"),
    ("backlog_run", "`- Steps left after the park: final review, full suite, ship`"),
    ("brief_check", "`Brief check (sl, before sending): a; b.`"),
    ("brief_check", "`brief check: <path>: <problem>`"),
    ("pt_review", "`REVIEW REQUIRED (code diffs cut)`"),
    ("pt_review", "`Read in full before your verdict (section 8 cut their diff; one Read each): <files>`"),
    ("trees", "`prepare_at(root, key, rev)`"),
    ("fleet", "`collect Wn [--plan P]`"),
    ("fleet", "`hooks/researcher-bash`"),
    ("fleet_io", "`report_dir`"),
    ("testcmd", "`SKIPPED <node id>`"),
    ("testcmd", "`skipped_names`"),
]
CODE = [  # (script, literal its source holds)
    ("run_tests.py", "print(f\"run_tests: {'tested ' if tree else ''}{tail}\""),
    ("run_tests.py", "is outside the tree {TESTED['tree']}: it may hold another build's results"),
    ("predict.py", '"case_s": 0.2'),
    ("predict.py", '"round_min": 2.5'),
    ("plan_tools.py", "of it outside the size band (existing tests, review rounds); splitting does not shrink it"),
    ("backlog_in_progress.py", 'LIVE_ENV = "SUPERLITE_IN_PROGRESS_LIVE"'),
    ("backlog_in_progress.py", "); worktrees and branches still checked"),
    ("backlog_brief.py", "SPEC_TRIAGE = ("),
    ("backlog_brief.py", "SPEC_LEAD = ("),
    ("backlog_run.py", "- Checkpointed tasks (ledger .superlite/progress.md; hidden checkpoints are not in the commits above): "),
    ("backlog_run.py", '"- Steps left after the park: "'),
    ("brief_check.py", "Brief check (sl, before sending): "),
    ("fleet_report.py", 'print(f"brief check: {path}: {item}"'),
    ("pt_review.py", '"# Review packet: REVIEW REQUIRED (code diffs cut)"'),
    ("pt_review.py", '"Read in full before your verdict (section 8 cut their diff; one Read each): "'),
    ("trees.py", "def prepare_at(root, key, rev):"),
    ("fleet_io.py", "def recollect(sd, wid):"),
    ("fleet_io.py", "def report_dir(sd, w):"),
    ("fleet_roles.py", "def research_bash_refusal(command: str)"),
    ("testcmd.py", "def _pytest_skipped(lines"),
]


def row(tool):
    rows = [x for x in LINES if x.startswith(f"| `{tool}` |")]
    assert len(rows) == 1, tool
    return rows[0]


@pytest.mark.parametrize("tool,text", NAMED)
def test_row_names_it_once(tool, text):
    assert row(tool).count(text) == 1


def test_brief_check_row_follows_fleet_io():
    assert LINES[LINES.index(row("fleet_io")) + 1] == row("brief_check")


def test_in_progress_paragraph_names_the_switch():
    para = next(x for x in LINES if x.startswith("`backlog plan` leaves out an issue another session builds"))
    assert "`SUPERLITE_IN_PROGRESS_LIVE=0`" in para
    assert "`in progress: worktrees and branches not read (<error>)`" in para


@pytest.mark.parametrize("script,literal", CODE)
def test_quoted_texts_match_the_code(script, literal):
    assert literal in (SCRIPTS / script).read_text(encoding="utf-8")
