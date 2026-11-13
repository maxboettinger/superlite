"""B72 (#429): docs/tools.md names what shipped in 1.5.70 to 1.5.76 and the contract default rule."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

RT_OLD = "with `--background` (prints `summary: <path>` and a `wait:` line)"
RT_NEXT = "with `--background` (prints `summary: <path>`, then the cue `next: tests still running; run the wait line below now, in the foreground (never as a background command), and do not end your turn until it reports.` and, last, the `wait:` line)"
RT_SWIFT = "a Swift `--fast` run whose test-cmd.json template holds `{only_testing}` maps each test file to one shell-quoted `-only-testing:<Target>/<Suite>` id per suite it declares (`-only-testing:<Target>` when it declares none, with the stderr note `run_tests: <path> declares no test suite; using -only-testing:<Target>`), the target read from target membership (the Sources-phase files and Xcode 16 synchronized folders of each `project.pbxproj`, the `Package.swift` test targets with their `path:`), else from the folder names; a path outside every test target runs the unfiltered `test` command with the stderr note `run_tests: <path> is not in a test target; running the unfiltered test command` (testcmd.py holds this one mapping for `testcmd.resolve` and `run_tests`, #431); "
CT_CLAIM = "(nothing is printed when its claimer is in the call or the file equals the newest checkpoint; else `left uncommitted (claimed by T2, changed after its checkpoint; run commit_task T2): F` when the claimer is committed and not running, or `left uncommitted (claimed by T2; commit_task T2 commits it once T2 is done): F`); "
CT_NOTES = "a file another task owns prints `left uncommitted (owned by T2, changed after its checkpoint; run commit_task T2): F` when its owners are outside the call and not running, at least one of them is committed and the file differs from the newest checkpoint; a file this task owns that a running sibling (busy in pool.json, outside this call) also owns and that differs from the newest checkpoint is held out with one `left uncommitted (shared with running T2; commit_task T1 again once it is done): F` note per task, a task left with nothing fails `Tn FAILED: nothing to commit; held for running T2: F`, and `--also` files and the Wave 0 task are never held; every stderr note prints once per call, not once per task; "
AC_SKIP = "; `apply` writes no commit whose tree equals the commit it sits on (squash and `--no-squash`): each such entry prints `apply: skipped <title> (no change left)`, `applied N commit(s)` counts only the real commits, and with N = 0 HEAD and the index stay untouched while the checkpoints are still removed"
BL_HEAD = "| `backlog` | Backlog mode CLI: `status [--all]`, `plan [--tier sonnet]"
BL_STATUS = "; each successful `plan` (`--reset` too) records the batch ids it added as backlog.json `round`, and `status` lists the batches not shipped plus that round's, folding the other shipped batches into one `earlier rounds: N shipped (sl backlog status --all lists them)` line right after the head line; `status --all` lists every batch"
PT_DEFAULT = "a Python producer is compared by signature, defaults included: a planned literal default must equal the code's value; a planned name default (`tid=TID`) must be a name in the code too, matched by its last dotted part, so a literal (`None`, `-1`, `'x'`, `set()`) or a call there is a mismatch (`parameter 'tid' default is None, planned TID`); any other expression (`LIMIT + 1`, `x[0]`) is not compared; "
IO_RED = " (a saved report JSON `fleet/reports/<id>.json` carries a `red` string: the json block's non-empty `red` string, else the reply's last `Red run:` line, else empty; and a `reds` object, a batch worker's red run per task id, from `Red run Tn:` lines, a `Red run:`/`Red runs:` header's `- Tn: text` items, or a json `red` object keyed by task id (an object with a non-string value, or any other non-string `red`, makes the block unparsable); the `no red run` review gap reads `reds[Tn]` before `red`; the report contract (`report_contract`, which `send --text`, the ask and `fleet restore`'s continue prompt append; `send --brief` ends with the brief line's `WORK`, a final reviewer's `REVIEW` or a planning lead's `PLANNED`) asks for `red` between `tests` and `findings`, except the final reviewer's, and for a batch implementer (a task label with a comma) is `WORK_BATCH`, whose `red` is that per-task object; a task message (`send Wn Tn ...`) adds the `Also edit:` line of `sl task`, and a batch's `Batch:` line asks for the per-task red runs)"


def row(name):
    rows = [ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |")]
    assert len(rows) == 1, name
    return rows[0]


def test_rows_keep_table_shape():
    for name in ("run_tests", "commit_task", "autocommit", "backlog", "pt_review", "fleet_io"):
        r = row(name)
        assert r.count(" | ") == 1 and r.endswith(" |"), name


def test_run_tests_row_names_the_cue_and_the_swift_mapping():
    r = row("run_tests")
    assert RT_NEXT in r and RT_OLD not in r
    assert "(the summary stays in the main `.superlite`); " + RT_SWIFT in r


def test_commit_task_row_names_the_notes():
    assert CT_CLAIM + CT_NOTES + "`--also` counts" in row("commit_task")


def test_autocommit_row_names_the_skip_line():
    assert row("autocommit").endswith("is a usage error (exit 2)" + AC_SKIP + " |")


def test_backlog_row_names_status_all():
    r = row("backlog")
    assert r.startswith(BL_HEAD)
    assert "and `next: sl backlog plan` when no batch is open" + BL_STATUS + "; `start`, `wait`" in r


def test_pt_review_row_names_the_default_rule():
    assert "and `contract` (seam checks; " + PT_DEFAULT + "a producer without Python sources" in row("pt_review")


def test_fleet_io_row_names_the_red_field():
    assert row("fleet_io").endswith("and report extraction" + IO_RED + " |")


def test_quoted_strings_exist_in_code():
    rt = (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
    assert 'WAIT_CUE = "next: tests still running; run the wait line below now, in the foreground (never as a background command), and do not end your turn until it reports."' in rt
    tc = (SCRIPTS / "testcmd.py").read_text(encoding="utf-8")
    for s in ("is not in a test target; running the unfiltered test command", "declares no test suite; using -only-testing:{tgt}", "-only-testing:{want}", "PBXSourcesBuildPhase", "fileSystemSynchronizedGroups"):
        assert s in tc, s
    assert 'print(f"run_tests: {n}"' in rt
    ct = (SCRIPTS / "commit_task.py").read_text(encoding="utf-8")
    for s in ("changed after its checkpoint; run commit_task ", " again once it is done): ", "nothing to commit; held for running "):
        assert s in ct, s
    ac = (SCRIPTS / "autocommit.py").read_text(encoding="utf-8")
    assert "(no change left)" in ac and "apply: skipped " in ac and "applied {len(done)} commit(s)" in ac
    assert "shipped (sl backlog status --all lists them)" in (SCRIPTS / "backlog_state.py").read_text(encoding="utf-8")
    assert 'add_argument("--all"' in (SCRIPTS / "backlog.py").read_text(encoding="utf-8")
    pt = (SCRIPTS / "pt_review.py").read_text(encoding="utf-8")
    assert "default is {shown}, planned {w['default']}" in pt and "def _literal_or_call(" in pt
    assert "Red run" in (SCRIPTS / "fleet_report.py").read_text(encoding="utf-8")
    assert 'ASK + " " + report_contract(w)' in (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
