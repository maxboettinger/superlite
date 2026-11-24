"""docs/tools.md names #1068's import check, #1069's route --send, bare --wait and capture hint, and #1085's trims (#1087)."""
from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "tools.md"
ROWS = [
    ("| `commit_task` |", "| `commit_task` import check (#1068) | The import check runs under the project's Python: the root's `.venv`, then, for a root in a linked worktree or task tree without a `.venv` of its own, the root's own `uv run --frozen --project <root> python` environment when `uv` is on PATH and the root holds `uv.lock` and `pyproject.toml` (each tree syncs its own `.venv` once; stderr `import check: <main>/.venv is the main checkout's environment, outside <root>; running the import check in <root>'s own environment: uv run --frozen --project <root> (#1140)`), else the main checkout's `.venv` with the note ending `the import check may import that folder's package, not <root>'s (#1140)` (`_pyrun.project_env`, #1133's rule); the main checkout itself keeps its `.venv` with no note; then `VIRTUAL_ENV`, then `uv run --frozen --project <root> python` when `uv` is on PATH and the root holds `uv.lock` and `pyproject.toml`, then superlite's own interpreter. A declared dependency that is not installed prints `import warning F:L <error> (declared dependency not installed under CMD; environment gap, not blocking)`; a uv check that printed no result prints `import warning F:0 import check not run under CMD: WHY (environment gap, not blocking)`; a script whose module-level code runs the program is compiled, not imported: `import check skipped (script: top-level code runs the program): F`. |"),
    ("| `findings` |", "| `findings route --send` (#1069) | Starts one fixer worker per routed brief after the unchanged route lines; with the fleet off it refuses: `error: --send needs the fleet on (sl fleet on --plan PLAN); without the fleet start each brief with the Agent tool`. |"),
    ("| `run_tests` |", "| `run_tests --wait` (#1069, #1085) | A bare `--wait` (no summary path) waits on this tree's newest background run, also from a subfolder of the checkout. Its stdout JSON leaves out `files` and the keys its stderr lines print (`run_tests.WAIT_STDERR_KEYS`: `output`, `warning`, `tree`, `lacks`, `drift`, `result_bundles`); the summary file its `summary` key names keeps them (#1085). |"),
    ("| `run_tests` |", "| coordinator guard capture hint (#1069) | When the guard cannot resolve a word whose variable was captured from `sl` output, the line before `Unresolved word:` (`guard_tools.capture_hint`) names a form that needs no capture: `sl run_tests --wait` with no path for `run_tests`, `sl findings route --send` for `findings route`, and copying the printed text for any other `sl` tool; verdicts are unchanged (docs/hooks.md). |"),
    ("| `pt_review` |", "| `pt_review packet` trims (#1085) | Diff stat rows read ` path \\| +A -D` (` path \\| Bin` for a binary file) with no padding and no `+`/`-` bar, then git's summary line. The head's `Cut to fit the size cap:` line merges its section-8 truncated files into one `section 8 truncated: a, b` entry and leaves out the files the `Read in full before your verdict` line names; with no entry left there is no Cut line; `section 8 left out:` and the stdout `cut:` lines are unchanged. |"),
]


def _lines():
    return DOC.read_text(encoding="utf-8").splitlines()


def test_new_rows_follow_their_anchor():
    lines = _lines()
    for anchor, row in ROWS:
        assert lines.count(row) == 1, row[:60]
        first = next(i for i, ln in enumerate(lines) if ln.startswith(anchor))
        assert lines.index(row) > first, row[:60]


def test_existing_rows_unchanged():
    lines = _lines()
    for anchor, _ in ROWS:
        assert sum(ln.startswith(anchor) for ln in lines) == 1, anchor
