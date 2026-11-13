"""#475: docs name the per-task verify command `cmd=`."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "skills" / "writing-plans").glob("*.md")))
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def _row(prefix):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(prefix))


def test_writing_plans_names_cmd():
    assert "`**Tests:** fast cmd=bash tests/hooks/test.sh`" in SKILL
    assert "lint rejects (`TESTS:`)" in SKILL


def test_tools_run_tests_row():
    assert "`--task Tn` of a task whose plan `**Tests:**` field holds `cmd=<command>`" in _row("| `run_tests` |")


def test_tools_plan_tools_row():
    assert "Lint rejects (`TESTS: Tn verifies with" in _row("| `plan_tools` |")
