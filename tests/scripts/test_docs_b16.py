"""docs/tools.md: the run_tests and testcmd rows name the 1.5.21 and B16 behaviour."""
from pathlib import Path

TOOLS = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")
RT_ADD = "; a green `--full` run (no `--task`, no `--fast`, the default pytest runner, from a git toplevel holding `scripts/test_layers.py`) stamps the unit layer itself (`run_tests: unit layer stamped`); a missing pytest `--fast` path is a usage error (exit 2, `test path not found: P (cwd C, root R)`, no incident); a non-Python run that exits 0 with no test count (xcodebuild `Executed 0 tests`) is a `no-result` stop (exit 1, `no tests ran: ...`); a Node runner (`npm`, `npx`, `pnpm`, `yarn`, `bun`, `bunx`, `vitest`, `jest`, `mocha`) whose `package.json` declares dependencies, with no `node_modules`, no Yarn PnP file and no `setup` command, is a usage error (exit 2, `node_modules missing in <root>: run <install> first`, the install command for the lockfile, else `npm install`; no incident)"
TC_ADD = "`swift_suites` blanks comments (`//`, nested `/* */`) and string literals (`\"...\"`, `\"\"\"...\"\"\"`, raw `#\"...\"#`) before it looks for suites, so a column-0 `}` inside one never ends a type."


def row(name):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |"))


def test_run_tests_row_names_unit_stamp():
    assert RT_ADD in row("run_tests")


def test_testcmd_row_names_blanking():
    assert TC_ADD in row("testcmd")


def test_testcmd_row_keeps_sentence_split():
    assert "detects the stack. `swift_suites` blanks" in row("testcmd")


def test_rows_stay_one_line():
    for name in ("run_tests", "testcmd"):
        assert row(name).endswith(" |")
