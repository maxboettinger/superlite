"""B118: docs/tools.md names the per-toolchain lock, killed runs, the machine limit and render_edit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def row(name):
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    return next(line for line in text.splitlines() if line.startswith(f"| `{name}` |"))


def test_run_tests_row_names_toolchain_lock_and_kills():
    r = row("run_tests")
    for part in ("~/.superlite/locks/full-suite-<toolchain>.lock", "other toolchains do not wait", "test run killed by SIG<NAME>"):
        assert part in r, part


def test_fleet_row_names_the_machine_flags():
    r = row("fleet")
    assert "--over-limit" in r and "--machine-wait S" in r


def test_backlog_run_row_names_machine_busy_and_park_line():
    r = row("backlog_run")
    assert "machine busy" in r and "machine: ... parks" in r


def test_render_edit_row():
    r = row("render_edit")
    for part in ("start F", "restore", "status", "finish refuses"):
        assert part in r, part
