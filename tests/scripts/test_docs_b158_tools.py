from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SETUP = (ROOT / "commands" / "setup.md").read_text(encoding="utf-8")

RT = ("a `--fast` value is split on commas, then on whitespace unless the part is an existing path; "
      "a pytest test-cmd.json command gets the same `test path not found` check for `.py` paths; "
      "the built-in pytest runner refuses an existing file that is not `.py` (exit 2, "
      "`pytest cannot collect <path> (not a .py file)` naming `**Tests:** cmd=` and a test-cmd.json command, no incident); "
      "a test wrapper's xcsift JSON summary (`summary.passed_tests`, `failed_tests`, `skipped_tests`; "
      "`failed_tests[]` `test`, `message`, `file`, `line`; `errors[]`) is read when no raw xcodebuild lines were printed: "
      "its counts are the run's, a zero summary stops with `no tests ran ...; runner: xcsift summary: 0 passed, 0 failed tests`, "
      "and each failure is placed at its file when that file is under the run folder; ")
TC = ("writes it to the root's own `.superlite/test-cmd.json`, also in a linked worktree "
      "(the file `run_tests` reads first; `--propose` prints the same `target`); "
      "`--shared` writes the main checkout's file instead, which every worktree without its own reads; "
      "`--plan P` (a plan or run folder) writes that run's `.superlite/test-cmd.json` and makes its project the root; "
      "after a write a second line says `testcmd: run_tests in <root> reads <file>`")
ST = ("and `target` the file it would write (the root's own, also in a linked worktree; "
      "`sl testcmd --write --shared` writes the main checkout's, which every worktree without its own reads)")


def row(name):
    return next(line for line in TOOLS.splitlines() if line.startswith(f"| `{name}` |"))


def test_run_tests_row():
    assert RT in row("run_tests")


def test_testcmd_row():
    assert TC in row("testcmd")


def test_setup_target_text():
    assert ST in SETUP
    line = next(x for x in SETUP.splitlines() if "and `target` the file it would write" in x)
    assert "(the main checkout's from a linked worktree)" not in line
