"""B131 docs: lock key, name mapping, --env, pass-through args and destinations are named."""
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def row(name):
    return next(ln for ln in (DOCS / "tools.md").read_text(encoding="utf-8").splitlines() if ln.startswith(f"| `{name}` |"))


def test_docs_b131_lock_key():
    assert '"lock": false' in (DOCS / "language.md").read_text(encoding="utf-8")
    assert '"lock": false' in (DOCS / "tools.md").read_text(encoding="utf-8")


def test_docs_b131_run_tests_flags():
    text = row("run_tests")
    for word in ("--env K=V", "--destination", "-- ARGS"):
        assert word in text


def test_docs_b131_names():
    assert "test name not found" in (DOCS / "language.md").read_text(encoding="utf-8")


def test_docs_b131_testcmd_row():
    text = row("testcmd")
    assert "`lock`" in text and "`destinations`" in text


def test_docs_b131_exit_127_stop_text():
    text = row("run_tests")
    assert "test command could not run" in text
    assert "or exits 127" not in text
