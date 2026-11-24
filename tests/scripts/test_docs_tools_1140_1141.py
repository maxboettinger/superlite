"""#1140, #1141: docs/tools.md names the per-tree import-check environment and the state-folder defaults."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROWS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
PYRUN = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "_pyrun.py").read_text(encoding="utf-8")


def row(title):
    found = [r for r in ROWS if r.startswith(f"| `{title}")]
    assert found, title
    return found[0]


def test_import_check_row_names_1140():
    r = row("commit_task` import check")
    for text in ("_pyrun.project_env", "uv run --frozen --project <root> python", "#1140"):
        assert text in r, text
    for text in ("running the import check in", "own environment: uv run --frozen --project",
                 "the import check may import that folder's package, not", "is the main checkout's environment, outside"):
        assert text in r and text in PYRUN, text


def test_run_tests_uv_row_names_1140():
    r = row("run_tests` --fast filter and uv env")
    text = "so the tests may import that folder's package, not"
    assert "#1140" in r and text in r and text in PYRUN


def test_state_default_rows_1141():
    for title in ("run_tests`", "history`", "metrics`", "report`"):
        r = row(title)
        assert "state.default_dir" in r and "#1131" in r, title
    for title in ("testcmd`", "trees`", "autocommit`", "commit_task`"):
        r = row(title)
        assert "state.default_root" in r and "state.Refused" in r and "#1131" in r, title


def test_report_row_is_one_and_after_metrics():
    idx = [i for i, r in enumerate(ROWS) if r.startswith("| `report` |")]
    assert len(idx) == 1
    assert ROWS[idx[0] - 1].startswith("| `metrics` |")
