"""fleet_report: the optional quote of a finding."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import fleet_report as fr  # noqa: E402

LINE = "src/a.py:12 - off by one - use <= - tier 1"


def _findings(line: str) -> list:
    return fr.parse("Verdict: CHANGES_REQUESTED\n" + line)["findings"]


def test_finding_line_with_quote():
    got = _findings(LINE + " - quote: `for i in range(n - 1):`")
    assert got == [{"file": "src/a.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1, "quote": "for i in range(n - 1):"}]


def test_finding_line_without_quote():
    assert _findings(LINE) == [{"file": "src/a.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1, "quote": ""}]


def test_quote_keeps_inner_dashes_and_tier_words():
    got = _findings(LINE + " - quote: `x = a - b  # - tier 2 - quote: y`")
    assert got[0]["tier"] == 1 and got[0]["fix"] == "use <="
    assert got[0]["quote"] == "x = a - b  # - tier 2 - quote: y"


def test_quote_without_backticks():
    assert _findings(LINE + " - quote: return None")[0]["quote"] == "return None"


def test_labelled_fallback_keeps_quote():
    got = fr.parse("Status: DONE\n- src/a.py:3 - p - f - tier 2 - quote: `a = 1`")["findings"]
    assert got[0]["quote"] == "a = 1" and got[0]["tier"] == 2


def _block(quote) -> str:
    f = '{"file": "a.py", "line": 1, "problem": "p", "fix": "f", "tier": 1%s}' % (quote,)
    return '```json\n{"status": "APPROVED", "files": [], "tests": "", "findings": [%s], "summary": "s"}\n```' % f


def test_json_finding_quote_must_be_a_string():
    ok = fr.parse(_block(', "quote": "x = 1"'))
    assert ok["valid"] and ok["findings"][0]["quote"] == "x = 1"
    assert fr.parse(_block(""))["valid"]
    assert not fr.parse(_block(', "quote": 5'))["valid"]


def test_review_and_work_templates_name_quote():
    for t in (fr.REVIEW, fr.WORK, fr.WORK_BATCH):
        assert '"quote": "<the exact text of that source line>"' in t
