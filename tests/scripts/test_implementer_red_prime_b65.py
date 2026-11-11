"""The prime's TDD lines and the SDD task-message report list name the red-run evidence (#405)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import build_prime  # noqa: E402

RED = ("- Red run first: run your new tests through the verify command before you write the code they test, and see "
       "them fail for the right reason. A test written together with its code, or one that passes at once, has no red "
       "run yet: break the code on purpose, run it red, then restore the code. Your report's `Red run:` line copies "
       "that run's summary line (for example `tests (fast): 0 passed, 1 failed`), or says `none - no test`.")
TDD = {"PREAMBLE": "- Test first: write the failing test, run it, implement, run it again.",
       "PREAMBLE_SLIM": "- Test first: write the failing test, run it, implement, run it again.",
       "PREAMBLE_MINI": "- Test first, run only the fast focused tests, code to the interfaces below. Never change a signature."}
SKILL = ROOT / "skills" / "subagent-driven-development" / "SKILL.md"


def test_each_prime_names_the_red_run_after_its_tdd_line():
    for name, tdd in TDD.items():
        lines = getattr(build_prime, name).splitlines()
        assert lines.count(RED) == 1, name
        assert lines[lines.index(RED) - 1] == tdd, name


def test_task_message_report_list_names_the_red_run_line():
    text = SKILL.read_text(encoding="utf-8")
    step3 = next(ln for ln in text.splitlines() if ln.startswith("3. "))
    assert ("status DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, files, test result, "
            "`Red run:` line, open questions\"") in step3
