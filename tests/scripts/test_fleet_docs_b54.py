"""docs/fleet.md names fleet report, --help, the --plan check, sl accounts, the sonnet researcher and its reach, the run root and task trees (#372 #374 #376 #378 #387)."""
from pathlib import Path

FLEET = (Path(__file__).resolve().parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")


def line_starting(prefix):
    found = [x for x in FLEET.splitlines() if x.startswith(prefix)]
    assert len(found) == 1, prefix
    return found[0]


def test_research_row_defaults_to_sonnet():
    assert "| sonnet, low (`--tier 1\\|sonnet` the default, `2\\|sonnet-high` sonnet at high effort, `3\\|opus` opus, `haiku` haiku; any other tier exits 2; with fleet off the in-process researcher keeps the agent file's haiku);" in line_starting("| `research` |")


def test_researcher_reach_and_plan():
    para = line_starting("Research worker limits:")
    for s in ("context7", "Xcode DocumentationSearch", "WebFetch", "stays with the coordinator", "without `--plan` the run is the current directory's", "`sl fleet report Wn`"):
        assert s in para, s


def test_commands_name_report_help_plan_and_accounts():
    for s in ("`fleet report Wn [Wm ...]`", "`== <id> <path>`", "`fleet --help` lists every subcommand (on, off, status, spawn, placement, stop, name, report, collect, send, keys, wait, run, restore, resume)",
              "`error: --plan P: not a plan file or folder; pass the plan file", "`sl accounts [--tier MODEL]`", "`claude1 ok 5h=12% weekly=40%`", "`claude2 skip 5-hour 95%`"):
        assert s in FLEET, s


def test_run_root_and_task_trees():
    sec = FLEET.split("## Run root and task trees", 1)[1].split("\n## ", 1)[0]
    for s in ("shared run root", "`.superlite/trees/Tn`", "`\"isolate\": true`", "one fixer at a time per run root", "disjoint files may run at once"):
        assert s in sec, s
    assert FLEET.index("## Run root and task trees") < FLEET.index("## Limits")


def test_isolate_is_not_claimed_for_pytest():
    assert "a pytest run ignores it" in FLEET
