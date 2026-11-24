"""docs/fleet.md and backlog.md name the #1089 text rules and the #1086 lint warning."""
from test_plan_tools import ROOT

FLEET = ("- The #1015 check reads quoted text as text, not as a path a worker must read (#1089): fenced blocks, the standing-note "
         "block (its `Standing note from main` line and the four-space lines after it, wherever a brief copies it) and a finding's "
         "`quote:` span; a path missing on this machine (a deploy host's `~/app`) is text too. A research worker may name an outside "
         "path the lead brief's research line lists (spawn it with `--machine local`). `plan_tools lint` prints `WARNING: OUTSIDE:` "
         "with the line for each existing outside path a plan names (#1086).")
BACKLOG = ("- A path the standing note names that is missing on this machine is text: neither copied nor named. Each one that is "
           "copied or over the copy cap is listed on the brief's `Standing note: a research worker may read` line: a research brief "
           "may name it or a path below it; spawn that research worker with `--machine local`, since a remote machine lacks it (#1089).")


def test_fleet_md_names_the_text_rules():
    assert FLEET in (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def test_backlog_md_names_research_reads():
    assert BACKLOG in (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
