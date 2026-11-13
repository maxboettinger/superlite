"""#480: docs/tools.md names the machine-wide full-suite lock in the run_tests row."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def row():
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    return next(line for line in text.splitlines() if line.startswith("| `run_tests` |"))


def test_row_names_the_lock():
    r = row()
    for part in (
        "passes the full-run gate (the `machine.json` admission below, else the lock; `\"lock\": false` skips both): it first takes the machine-wide full-suite lock `~/.superlite/locks/full-suite-<toolchain>.lock`",
        "`--lock-wait S` (default 3600; 0 = no limit)",
        "`full-suite lock: still held by ... after S s (run_tests --lock-wait S; 0 = no limit)`",
        "`SUPERLITE_FULL_SUITE_LOCK`",
        "`run_tests: full-suite lock not taken: <error>; running without it`",
        "is waiting for the <toolchain> full-suite lock (held by ...)",
    ):
        assert part in r, part


def test_lock_text_follows_the_limit_text():
    r = row()
    assert r.index("a `no-result` incident); a full run (no `--fast`") > r.index("`--limit S` (default 3600; 0 = none)")
    assert "A run whose test processes a signal ended" in r
    assert r.index("A run whose test processes a signal ended") > r.index("`--limit S` (default 3600; 0 = none)")
