"""Fixers run each regression test red before its fix and name that run in the FIXED line (#379)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXERS = ["agents/fixer-sonnet.md", "agents/fixer-sonnet-high.md", "agents/fixer-opus.md"]
RED = ("- Red run first: run each regression test through the commands of the next rule before you make its fix, "
       "and see it fail for the right reason. A test written after its fix, or together with it, has no red run yet: "
       "take the fix out by hand, run the test red, then put the fix back. Its `FIXED` line ends "
       "`- red: <that run's summary line>` (for example `- red: tests (fast): 0 passed, 1 failed`).")
REPORT = ("`NOT_FIXED - <finding> - <reason>`; a `FIXED` line with a regression test ends "
          "`- red: <its red run's summary line>`. Then the test summary line")


def lines(rel):
    return (ROOT / rel).read_text(encoding="utf-8").splitlines()


def test_red_rule_sits_between_the_fix_and_run_rules():
    for rel in FIXERS:
        ls = lines(rel)
        assert ls.count(RED) == 1, rel
        i = ls.index(RED)
        assert ls[i - 1].startswith("- For each finding:"), rel
        assert ls[i + 1].startswith("- Run only the touched test files"), rel


def test_report_line_names_the_red_suffix():
    for rel in FIXERS:
        report = [ln for ln in lines(rel) if ln.startswith("Report,")]
        assert len(report) == 1 and REPORT in report[0], rel
