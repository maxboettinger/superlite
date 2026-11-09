"""The package reviewer reports an out-of-scope fix as an open finding instead of applying it (#385)."""
from __future__ import annotations

from pathlib import Path

REVIEWER = Path(__file__).resolve().parents[2] / "agents" / "package-reviewer.md"
FIX = ("- Fix every finding you report, including findings the coordinator sends you later, and add a regression test "
       "per fix that fails before the fix (a red run; a test written together with its fix has none), except for a "
       "doc- or comment-only fix, which needs no test. Log each with `resolution`. No finding stays open unless you "
       "cannot verify it or its fix is out of scope.")
SCOPE = ("- Out of scope: change only the files in scope and their regression tests (in `tests/regression/` or an "
         "in-scope test file). A fix that needs another file, a new dependency (a package manifest, lockfile or build "
         "target entry) or a wider allowlist, exemption or threshold in a test, lint or config file is never applied: "
         "leave the code as it is, list the finding under open with `out of scope: <what the fix needs>`, and log it "
         "`--resolution open`.")
REPORT = ("Report in at most 300 words: findings fixed or open (`file:line — problem — fix`; an out-of-scope fix is "
          "open, never fixed), tests added (each with its red run's summary line), probes run, and a final "
          "`Status: DONE | DONE_WITH_CONCERNS | BLOCKED`. No file contents or logs.")


def lines():
    return REVIEWER.read_text(encoding="utf-8").splitlines()


def test_scope_rule_follows_the_fix_rule():
    ls = lines()
    assert ls.count(FIX) == 1 and ls.count(SCOPE) == 1
    assert ls.index(SCOPE) == ls.index(FIX) + 1
    assert not any(ln.startswith("- Fix every finding") and "add a regression test per fix. Log" in ln for ln in ls)


def test_report_keeps_out_of_scope_fixes_open():
    ls = lines()
    assert ls.count(REPORT) == 1
    assert sum(ln.startswith("Report in at most 300 words:") for ln in ls) == 1
