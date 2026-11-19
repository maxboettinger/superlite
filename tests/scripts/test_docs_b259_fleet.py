"""B259 (#988, #985): docs/fleet.md rewrites the lines append-only batches left stale and names the remote collect wait, the remote brief check, not_run, fleet resume and the session fleet folder; each quoted message is checked against the script printing it."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
LINES = TEXT.splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

STALE = [
    "while that is at most 30 min old",
    "so the 30-minute limit above is gone",
    "an account signed out there",
    "leaves `moved_to` behind",
    "One `ps` call finds",
    "A file of a dead process or older than an hour is dropped",
    "(on, off, status, spawn, stop, report, send, keys, wait, run)",
    "fleet: this session's fleet moved from A to B`",
    "A fleet that moved (`moved_to` in an off `fleet.json`) is read at its target",
]
NAMED = [  # (section, text the section holds exactly once)
    ("## What it is", "`~/.superlite/fleets/<sid>/fleet.json`"),
    ("## Commands", "(on, off, status, spawn, placement, stop, name, report, collect, send, keys, wait, run, restore, resume)"),
    ("## Commands", "`~/.superlite/fleets/<sid>/fleet.json`"),
    ("## Commands", "`fleet: this session's fleet in F now also serves R (N workers)`"),
    ("## Commands", "`fleet: this session's fleet moved from R to F (N workers)`"),
    ("## Commands", " not_run=N"),
    ("## Commands", "`status_reported`"),
    ("## Commands", "`fleet_report.NOT_RUN`"),
    ("## Commands", "`fleet resume Wn --text TEXT [--plan P]`"),
    ("## Commands", "`Wn resumed pane=P session=S (<role>, last task T)`"),
    ("## Commands", 'continue its session: sl fleet resume Wn --text "..." --plan <sd>; or start a fresh one: ...'),
    ("## Remote machines", "`placement: account A skipped on L (not signed in there); local`"),
    ("## Remote machines", "no stop record of its task reached this machine within 45 s; its tree T stays on L (snapshot ref R)"),
    ("## Remote machines", "its stop hook took none (remote_apply snapshot failed or ran past 30 s); its tree T stays on L"),
    ("## Remote machines", "`BLOCKED: Wn <label> not sent (brief not taken after one resend)`"),
    ("## Remote machines", "`remote_margin`"),
]
CODE = [  # (script, literal its source holds)
    ("fleet_state.py", "fleet: this session's fleet in {held} now also serves {target} ({_count(held)} workers)"),
    ("fleet_state.py", "fleet: this session's fleet moved from {run} to {held} ({_count(held)} workers)"),
    ("fleet.py", "placement: account {acct} skipped on {machine} (not signed in there); local"),
    ("fleet_remote_collect.py", "no stop record of its task reached this machine within {WAIT_S} s; its tree {tree} stays on {label} (snapshot ref "),
    ("fleet_remote_collect.py", "WAIT_S = 45"),
    ("fleet_remote_collect.py", "its stop hook took none (remote_apply snapshot failed or ran past 30 s); its tree {tree} stays on {label}"),
    ("fleet_remote_worker.py", '"brief not taken after one resend"'),
    ("fleet_resume.py", "resumed pane={pane} session={sid[:8]} ({role}, last task "),
    ("fleet_io.py", 'extra["status_reported"]'),
    ("fleet_io.py", 'f" not_run={len(unrun)}"'),
    ("fleet_io.py", "continue its session: {fleet_resume.CMD} {wid} --text"),
    ("fleet_placement.py", '["remote_margin"]'),
    ("accounts.py", "using its reading from %s ago"),
    ("machine_load.py", "WAIT_TTL = 3600"),
]


def _section(name):
    at = LINES.index(name)
    end = next((i for i in range(at + 1, len(LINES)) if LINES[i].startswith("## ")), len(LINES))
    return "\n".join(LINES[at:end])


@pytest.mark.parametrize("text", STALE)
def test_stale_text_is_gone(text):
    assert text not in TEXT


@pytest.mark.parametrize("section,text", NAMED)
def test_section_names_it_once(section, text):
    assert _section(section).count(text) == 1


def test_capacity_usage_line_says_any_age():
    line = next(x for x in LINES if x.startswith("- An account whose `claude-profile usage` reading failed"))
    assert "of any age" in line and "minus limits that have reset" in line


@pytest.mark.parametrize("script,literal", CODE)
def test_quoted_texts_match_the_code(script, literal):
    assert literal in (SCRIPTS / script).read_text(encoding="utf-8")
