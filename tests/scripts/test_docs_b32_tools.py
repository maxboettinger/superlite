"""docs/tools.md rows name the 1.5.23-1.5.39 changes (#310)."""
from pathlib import Path

TOOLS = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")


def row(name):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |"))


def check(name, *parts):
    r = row(name)
    missing = [p for p in parts if p not in r]
    assert not missing, (name, missing)


def test_feedback_mark_splits_checks_and_takes_hosts():
    check("feedback", "`mark ID... [--host H]...`", "split on whitespace", "`feedback-triaged.json`", "`feedback-hosts`",
          "`feedback mark: unknown feedback id X`", "exit 2", "nothing written")


def test_fleet_spawn_retry_and_rerun_hint():
    check("fleet", "`not an available shell`", "retried once after a 3 s pause", "`; retried in a fresh pane after Wn`", "`; retried once`",
          "`; rerun sl fleet spawn --for-dispatch`", "only when the reason holds `not an available shell`")


def test_fleet_io_send_refuses_two_kinds():
    check("fleet_io", "`send Wn --brief FILE`", "`error: send takes task ids, --text or --brief, not two of them`",
          "an empty `--text` included", "exit 2")


def test_next_tasks_and_dispatch_name_the_lapse_the_stderr_lines_and_id_lists():
    check("next_tasks", "`depends on unstable <ids>`", "`unstable=Tn <reason>; rerun sl lint --stable`",
          "`not in stable.json`", "`held=Tn <reason>`", "split on commas or whitespace",
          "`warning: --<flag>: Tn is not a task of the plan`")
    check("dispatch", "`unstable=Tn <reason>; rerun sl lint --stable`", "`depends on unstable <ids>`",
          "split on commas or whitespace", "`warning: --committed: T7 is not a task of the plan`")


def test_commit_task_no_change_line():
    check("commit_task", "`Tn: no change since its last checkpoint <sha>`", "writes no commit, ref or entry",
          "a task's first checkpoint always commits")


def test_autocommit_takes_plan():
    check("autocommit", "`--plan P` or `--plan=P` anywhere", "`state.git_root(P)`", "usage error (exit 2)")


def test_run_tests_links_node_modules_into_a_task_tree():
    check("run_tests", "`tree/node_modules`", "`../../../node_modules`", "a wrong or dangling link is replaced",
          "refuses with exit 2 naming the tree")


def test_testcmd_placeholder_gate():
    check("testcmd", "`{names}` and `{only_testing}` only when the command holds them",
          "`testcmd: <file> declares no test suite`")


def test_backlog_rows_name_shortening_and_lead_questions():
    check("backlog", '`shortened: "<question>" <field>: N -> M characters`', "`shortened: K more`",
          "over 300 characters still fails", "clears the ship approval", "`decide --print --batch B`",
          "`not planned (cap)`", "`not triaged (200 cap)`")
    check("backlog_run", "re-read for 10 s", "`<cut line> (transcript unread)`", "`B shortened: ...`",
          "sent back to the lead once", "`invalid question.json: <errors>`")


def test_rows_stay_one_table_line():
    rows = [ln for ln in TOOLS.splitlines() if ln.startswith("| `")]
    assert all(ln.endswith(" |") and ln.count(" | ") == 1 for ln in rows if "\\|" not in ln)
