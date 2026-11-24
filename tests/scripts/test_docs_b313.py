"""docs/fleet.md and backlog.md name the #1089 text rules, the #1086 lint warning and the #1132 spawn brief rule."""
from test_plan_tools import ROOT

FLEET = ("- The #1015 check reads quoted text as text, not as a path a worker must read (#1089): fenced blocks, the standing-note "
         "block (its `Standing note from main` line and the four-space lines after it, wherever a brief copies it) and a finding's "
         "`quote:` span; a path missing on this machine (a deploy host's `~/app`) is text too. A research worker may name an outside "
         "path the lead brief's research line lists (`fleet spawn --brief` keeps that worker on this machine, #1132). "
         "`plan_tools lint` prints `WARNING: OUTSIDE:` with the line for each existing outside path a plan names (#1086).")
BACKLOG = ("- A path the standing note names that is missing on this machine is text: neither copied nor named. Each one that is "
           "copied or over the copy cap is listed on the brief's `Standing note: a research worker may read` line: a research brief "
           "may name it or a path below it; `fleet spawn --brief` keeps a research worker whose brief names one on this machine, "
           "since a remote machine lacks it (#1089, #1132).")
FLEET_1132 = ("- A research worker whose brief names a path the lead brief's research line lists (`Standing note: a research worker "
              "may read ...`) stays here without `--machine local`; stderr says `placement: research worker stays local: ... (#1111)`. "
              "`fleet spawn --brief` hands placement the brief, so a research worker whose brief names no such path is placed as usual (#1132).")


def test_fleet_md_names_the_text_rules():
    assert FLEET in (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def test_backlog_md_names_research_reads():
    assert BACKLOG in (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")


def test_fleet_md_names_the_spawn_brief_rule():
    text = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert FLEET_1132 in text and "Until `fleet spawn` hands placement the brief" not in text
