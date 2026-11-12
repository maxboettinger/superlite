"""#659: docs/tools.md names the admission shapes, the forecast's admission waiter and the B146 rows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def row(name):
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    return next(line for line in text.splitlines() if line.startswith(f"| `{name}` |"))


def has(name, parts):
    r = row(name)
    for part in parts:
        assert part in r, part


def test_run_tests_row_names_shapes():
    has("run_tests", (
        '"self"', '"lock"', '"default"',
        "full run admitted by the machine itself",
        "full run under the <toolchain> full-suite lock",
        "simulators, UI test hosts",
        '{"admission": {"xcode": "self", "default": ["<gate>", "run", "--"]}}',
        "in arrival order: queue place N of M",
        '{"admission": ["<gate>", "run", "--"]}',
        'run_tests: full run through the admission command <name> (machine.json "admission"); no full-suite lock',
        "run_tests: waiting for the admission command <name> to start the full run",
        "admission: <name> did not start the full run after S s",
        "running under the full-suite lock",
        "keys are the lock's toolchain names: `python`, `xcode`, the test-cmd.json language slug (`bash` for a bash project) or `shell` when it names none",
    ))


def test_predict_row_names_admission_wait():
    has("predict", ('a run waiting at the admission command, shown by a live `.lockwait` note with "admission" outside the run, counts like a held lock',))


def test_backlog_row_names_notes_and_append_only():
    has("backlog", ("`sl backlog notes B`", "`ship B notes`", "`append_only`",
                    "append-only in both, no hold; conflicts resolve at the ship rebase"))


def test_b146_rows():
    has("commit_task", ("Tn: no red run (<why>); its review must prove each new test can fail",))
    has("fleet", ("Red runs (task reports):", "Plan contract outside Tn's Produces", "no red run"))
    has("plan_tools", ("`REACH:`", "`OWNS:`", "`ALSO-TOUCHES:`"))
