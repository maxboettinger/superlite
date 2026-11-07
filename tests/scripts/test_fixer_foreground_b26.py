"""Fixer agents, the package reviewer and the fix brief run the wait: line in the foreground (#278)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))

import findings  # noqa: E402

AGENTS = Path(__file__).resolve().parents[2] / "agents"
RULE = "then run the `wait:` line it prints (`<abs sl> run_tests --wait <path>`) in the foreground, never as a background command, and end your turn only after it reports; read only its summary."
FIXER_LINE = "- Run only the touched test files, in the background: `<abs sl> run_tests --fast <touched test files> --background`, " + RULE + " Never run the full suite, raw `pytest` or `python`."
REVIEWER_LINE = "- Focused tests, in the background: `<abs sl> run_tests --fast PATHS --background`, " + RULE + " Do not run the full suite."
OLD = "then the `wait:` line it prints (`"
OLD_REVIEWER = "(the printed `wait:` line) for the summary"
BRIEF_VERIFY = "Verify: `/x/sl run_tests --fast <the test files you touched> --background`, then run the printed `wait:` line in the foreground (never as a background command) and end your turn only after it reports."


def test_fixers_run_wait_in_foreground():
    for name in ("fixer-sonnet.md", "fixer-sonnet-high.md", "fixer-opus.md"):
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert FIXER_LINE in text.split("\n"), name
        assert OLD not in text, name


def test_package_reviewer_runs_wait_in_foreground():
    text = (AGENTS / "package-reviewer.md").read_text(encoding="utf-8")
    assert REVIEWER_LINE in text.split("\n")
    assert OLD_REVIEWER not in text


def test_fix_brief_runs_wait_in_foreground():
    task = SimpleNamespace(id="T1", owns=["a.py"])
    item = {"id": "F-T1-1", "file": "a.py", "line": 3, "problem": "p", "fix": "f", "tier": 1, "label": "FR1"}
    out = findings.brief_text("/x/sl", Path("/p/plan.md"), task, [item], 1)
    assert BRIEF_VERIFY in out.split("\n")
    assert "then the printed `run_tests --wait <path>` line" not in out
