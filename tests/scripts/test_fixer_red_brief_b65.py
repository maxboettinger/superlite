"""The fix brief and the fixer contract name the red-run evidence (#405)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import findings  # noqa: E402
import run_tests  # noqa: E402

BRIEF = ("Fix only these findings, one regression test each, except a doc- or comment-only fix (no code a test runs): "
         "its `FIXED` line ends `- no test: doc-only`. Red run first: run each regression test red before its fix "
         "(a fix already in place: take it out by hand for that run, then put it back); its `FIXED` line ends "
         "`- red: <that run's summary line>`, for example `- red: tests (fast): 0 passed, 1 failed`.")
CONTRACT = ("and its report line ends `no test: doc-only`; run each regression test red before its fix (a fix already "
            "in place is taken out by hand for that run) and end its `FIXED` line `- red: <that run's summary line>`; "
            "run `\"$SL\" run_tests --fast PATHS --background`")


def test_fix_brief_names_red_run_and_doc_only():
    task = SimpleNamespace(id="T2", owns=["src/a.py"])
    item = {"id": "F-T2-1", "file": "src/a.py", "line": 3, "problem": "p", "fix": "f", "tier": 1, "label": "FR1"}
    text = findings.brief_text("/abs/sl", Path("/abs/plan.md"), task, [item], 1)
    assert text.count(BRIEF) == 1
    assert "one regression test each.\n" not in text


def test_brief_example_matches_run_tests_summary_line():
    assert run_tests.summary_line({"mode": "fast", "passed": 0, "failed": 1}) == "tests (fast): 0 passed, 1 failed"


def test_fixer_contract_names_red_run():
    text = (ROOT / "skills" / "subagent-driven-development" / "fixing.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("- **Fixer contract:**"))
    assert line.count(CONTRACT) == 1
