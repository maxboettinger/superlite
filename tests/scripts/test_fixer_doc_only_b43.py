"""Fixers exempt doc- and comment-only findings from the regression-test rule (#335)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXERS = ["agents/fixer-sonnet.md", "agents/fixer-sonnet-high.md", "agents/fixer-opus.md"]
EXEMPT = ("A doc- or comment-only finding (the fix changes only docs, comments or prompt wording, no code a test runs) "
          "is exempt, also when the brief says \"one regression test each\": add a check only when one fails without "
          "the fix (for example a test that reads that file's text, where the repo already has such tests), never a "
          "test that passes either way; else its report line ends `- no test: doc-only`.")
RULE = "- For each finding: read the code, make the fix, add one regression test that fails without it. " + EXEMPT
REPORT = "`FIXED - <finding>`, `FIXED - <finding> - no test: doc-only` or `NOT_FIXED - <finding> - <reason>`"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_fixers_exempt_doc_only_findings():
    for rel in FIXERS:
        lines = read(rel).splitlines()
        assert RULE in lines, rel
        assert sum(REPORT in ln for ln in lines if ln.startswith("Report,")) == 1, rel


def test_fixer_rule_lines_match():
    found = [[ln for ln in read(rel).splitlines() if ln.startswith("- For each finding:")] for rel in FIXERS]
    assert all(len(f) == 1 for f in found)
    assert found[0] == found[1] == found[2]


def test_fixing_contract_names_the_exemption():
    text = read("skills/subagent-driven-development/fixing.md")
    line = next(ln for ln in text.splitlines() if ln.startswith("- **Fixer contract:**"))
    for s in ("one regression test per fix that fails without it", "except a doc- or comment-only fix",
              "never a test that passes either way", "`no test: doc-only`;"):
        assert s in line, s
    assert "one regression test per fix;" not in line
