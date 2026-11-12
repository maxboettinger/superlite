"""#655: docs/tools.md names the full-run queue, the admission command and the status waiting line."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def row(name):
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    return next(line for line in text.splitlines() if line.startswith(f"| `{name}` |"))


def test_run_tests_row_names_queue_and_admission():
    r = row("run_tests")
    for part in (
        "in arrival order: queue place N of M",
        '{"admission": ["<gate>", "run", "--"]}',
        'run_tests: full run through the admission command <name> (machine.json "admission"); no full-suite lock',
        "run_tests: waiting for the admission command <name> to start the full run",
        "admission: <name> did not start the full run after S s",
        "running under the full-suite lock",
    ):
        assert part in r, part


def test_status_row_names_waiting_line():
    r = row("status")
    for part in (
        "full run waiting: N min for the <toolchain> full-suite lock, queue place P of Q",
        "full run waiting: N min for the admission command <name>",
    ):
        assert part in r, part
