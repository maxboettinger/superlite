"""B259 (#976, #985, #988): docs/tools.md names run_tests --worker NAME and its tested tail, the current gate refusal and --over-limit, the session fleet folder, the account-only placement skip, not_run, fleet resume and any-age usage readings; each quoted message is checked against the script printing it."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

STALE = [
    "`--over-limit` skips both checks",
    "memory 11% free, floor 15% (23 agents, about 0.7 GB each); largest non-agent process WindowServer 20.0 GB; rerun later, or pass --over-limit",
    "leaving `moved_to` behind",
    "while at most 30 min old",
    "`tests (<mode>): P passed, F failed[, S skipped][; error: E]`",
]
NAMED = [  # (row, text the row holds exactly once)
    ("run_tests", "`--worker NAME`"),
    ("run_tests", "`.superlite/trees/worker-NAME`"),
    ("run_tests", "`--worker NAME: 1 to 64 letters, digits, - or _ (got ...)`"),
    ("run_tests", "[; error: E][; <tested>]`"),
    ("run_tests", "`lacks N changed file(s) of the run root: ...`"),
    ("run_tests", "`N file(s) changed while the tests ran: ...`"),
    ("fleet", "gave up after K checks in N s: <what>; room comes when <ways>; rerun later, or pass --over-limit"),
    ("fleet", "plain `--over-limit` skips every check"),
    ("fleet", "`~/.superlite/fleets/<sid>/fleet.json`"),
    ("fleet", "`fleet: this session's fleet in F now also serves R (N workers)`"),
    ("fleet", "`placement: account A skipped on L (not signed in there); local`"),
    ("fleet", "`resume Wn --text T`"),
    ("fleet_io", " not_run=N"),
    ("fleet_io", "`status_reported`"),
    ("fleet_state", "`~/.superlite/fleets/<sid>/fleet.json`"),
    ("fleet_resume", "`sl fleet resume Wn --text T [--plan P]`"),
    ("fleet_resume", "`sl fleet_resume`"),
    ("accounts", "of any age"),
]
CODE = [  # (script, literal its source holds)
    ("run_tests.py", 'ap.add_argument("--worker", default=None, metavar="NAME"'),
    ("run_tests.py", "--worker NAME: 1 to 64 letters, digits, - or _ (got "),
    ("run_tests.py", "of the run root: {names(lacks)}"),
    ("run_tests.py", "changed while the tests ran: {names(drift)}"),
    ("machine_load.py", "gave up after {k} check"),
    ("machine_load.py", '"room comes when "'),
    ("fleet.py", '"; rerun later, or pass --over-limit"'),
    ("fleet_state.py", "now also serves {target} ({_count(held)} workers)"),
    ("fleet.py", "placement: account {acct} skipped on {machine} (not signed in there); local"),
    ("fleet_io.py", 'extra["status_reported"]'),
    ("accounts.py", "whatever its age, minus limits that have reset"),
]


def row(tool):
    rows = [x for x in TEXT.splitlines() if x.startswith(f"| `{tool}` |")]
    assert len(rows) == 1, tool
    return rows[0]


@pytest.mark.parametrize("text", STALE)
def test_stale_text_is_gone(text):
    assert text not in TEXT


@pytest.mark.parametrize("tool,text", NAMED)
def test_row_names_it_once(tool, text):
    assert row(tool).count(text) == 1


def test_fleet_resume_row_follows_fleet_restore():
    lines = TEXT.splitlines()
    i = lines.index(row("fleet_restore"))
    assert lines[i + 1] == row("fleet_resume")


@pytest.mark.parametrize("script,literal", CODE)
def test_quoted_texts_match_the_code(script, literal):
    assert literal in (SCRIPTS / script).read_text(encoding="utf-8")
