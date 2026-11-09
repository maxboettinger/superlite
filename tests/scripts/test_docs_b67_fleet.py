"""B67 (#401): docs/fleet.md ## Batch leads names the 1.5.64 plan details and the 1.5.69 orchestrator takeover."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
LEADS = FLEET.split("## Batch leads (backlog mode)", 1)[1].split("\n## ", 1)[0]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

PLAN = "An option label over 60 characters is cut at its last whole word, and its full text (without ` (Recommended)`) leads its description, which is then cut to 200. A `plan` refused by planned or parked batches ends `; sl backlog plan --reset drops them and plans every open issue again (shipped batches stay)`; with a running or needs_decision batch it ends `; --reset is refused too while a batch is running or needs_decision` instead (exit 2). `sl backlog status` with no batch open ends with the line `next: sl backlog plan`."
TAKEOVER = "Taking a run over: a session that continues another session's run (a resumed lead, or a coordinator whose session ran out of usage) runs `sl orchestrator takeover --plan .superlite` first (a plan path works too). `sl orchestrator end`, `set`, `approve` and `bind` refuse a run folder another live session owns and name that command, and `sl finish` prints it as a hint; `takeover` binds the run to this session and prints `orchestrator: run <dir> taken over from session <id>; this session owns it now`."


def paragraphs():
    return [p for p in LEADS.strip().split("\n\n")]


def test_plan_paragraph_follows_the_main_paragraph():
    ps = paragraphs()
    i = next(k for k, p in enumerate(ps) if p.startswith("`/superlite:backlog` works"))
    assert ps[i + 1] == PLAN


def test_takeover_paragraph_follows_the_lead_paragraph():
    ps = paragraphs()
    i = next(k for k, p in enumerate(ps) if p.startswith("A lead is a fleet worker"))
    assert ps[i + 1] == TAKEOVER


def test_hints_match_the_code():
    src = (SCRIPTS / "backlog.py").read_text(encoding="utf-8")
    for hint in ("; sl backlog plan --reset drops them and plans every open issue again (shipped batches stay)",
                 "; --reset is refused too while a batch is running or needs_decision", "next: sl backlog plan"):
        assert f'"{hint}"' in src and f"`{hint}`" in PLAN


def test_takeover_text_matches_the_code():
    src = (SCRIPTS / "orchestrator.py").read_text(encoding="utf-8")
    assert "taken over from session {old}; this session owns it now" in src
    assert "sl orchestrator takeover --plan" in (SCRIPTS / "finish.py").read_text(encoding="utf-8")
