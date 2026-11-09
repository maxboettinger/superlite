"""Implementers run each new test red before its code and report that run's summary line (#379)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTERS = ["agents/implementer.md", "agents/implementer-haiku.md"]
RED = ("- Red run first: run the new tests through that fast check before you write the code they test, and see them "
       "fail for the right reason (the behavior is missing, not a typo or an import error). A test written together "
       "with its code, or one that passes at once (a regression guard for behavior that already works), has no red "
       "run yet: break the code on purpose, run the test red, then restore the code. Your report's `Red run:` line "
       "copies that run's summary line.")
REPORT = ("- Red run: the summary line of the run that saw your new tests fail (for example "
          "`tests (fast): 0 passed, 1 failed`), or `none - no test` for a task that adds no test")


def lines(rel):
    return (ROOT / rel).read_text(encoding="utf-8").splitlines()


def test_red_rule_follows_the_tdd_rule():
    for rel in IMPLEMENTERS:
        ls = lines(rel)
        assert ls.count(RED) == 1, rel
        assert ls[ls.index(RED) - 1].startswith("- TDD."), rel


def test_report_names_the_red_run():
    for rel in IMPLEMENTERS:
        ls = lines(rel)
        assert ls.count(REPORT) == 1, rel
        i = ls.index(REPORT)
        assert ls[i - 1] == "- Test command and its result line", rel
        assert ls[i + 1] == "- Concerns or open questions", rel


def test_example_is_the_wait_summary_line():
    sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
    import run_tests
    data = {"passed": 0, "failed": 1, "skipped": 0, "mode": "fast"}
    assert run_tests.summary_line(data) == "tests (fast): 0 passed, 1 failed"
