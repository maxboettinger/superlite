"""Labelled-line worker reports parse in full (#500)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_report as fr  # noqa: E402

GOOD = {"status": "DONE", "files": ["src/a.py"], "tests": "3 passed", "red": "", "findings": [], "summary": "ok", "concerns": []}
LAB = ("Status: DONE_WITH_CONCERNS\n\nFiles changed:\n- `skills/a.py`\n- tests/test_a.py: new cases\n* docs/a.md\n\n"
       "Test: tests (fast): 37 passed, 0 failed\nRed run: tests (fast): 2 failed\nConcerns:\n- slow path untested\n- **name clash** with b.py\n")


def block(obj):
    return "```json\n" + json.dumps(obj) + "\n```"


def test_labelled_task_report_parses_in_full():
    assert fr.parse(LAB) == {"status": "DONE_WITH_CONCERNS", "files": ["skills/a.py", "tests/test_a.py", "docs/a.md"],
                             "tests": "tests (fast): 37 passed, 0 failed", "red": "tests (fast): 2 failed", "findings": [],
                             "summary": "", "concerns": ["slow path untested", "name clash with b.py"], "valid": False}


def test_bold_and_inline_labels():
    r = fr.parse("**Status:** DONE\n**Files changed:** `a.py`, b.py\n**Tests:** `sl run_tests --fast t.py` -> 3 passed\n"
                 "**Summary:** added x\n**Open questions:** none\n")
    assert r["status"] == "DONE" and r["files"] == ["a.py", "b.py"]
    assert r["tests"] == "`sl run_tests --fast t.py` -> 3 passed" and r["summary"] == "added x" and r["concerns"] == []


def test_empty_label_takes_next_items():
    r = fr.parse("Status: DONE\nTest:\n- tests (fast): 5 passed, 0 failed\nFiles:\n1. a.py\n2. b.py\n")
    assert r["tests"] == "tests (fast): 5 passed, 0 failed" and r["files"] == ["a.py", "b.py"]


def test_two_test_lines_join():
    r = fr.parse("Status: DONE\nTest command: sl run_tests --fast t.py\nTest result: 4 passed, 0 failed\n")
    assert r["tests"] == "sl run_tests --fast t.py; 4 passed, 0 failed"


def test_crlf_labels():
    r = fr.parse("Status: DONE\r\nFiles changed:\r\n- a.py\r\nTest: 1 passed\r\n")
    assert r["files"] == ["a.py"] and r["tests"] == "1 passed"


def test_labels_inside_fences_ignored():
    r = fr.parse("Status: BLOCKED\n```\nFiles changed: x.py\nConcerns: y\n```\n")
    assert r["files"] == [] and r["concerns"] == [] and r["status"] == "BLOCKED"


def test_none_words_dropped():
    r = fr.parse("Status: DONE\nFiles changed: none\nConcerns: n/a\n")
    assert r["files"] == [] and r["concerns"] == []


def test_finding_lines_in_a_status_report():
    r = fr.parse("Status: DONE_WITH_CONCERNS\n- src/a.py:12 - off by one - use <= - tier 1\n")
    assert r["findings"] == [{"file": "src/a.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1}]


def test_json_block_wins_and_carries_concerns():
    assert fr.parse("Status: DONE\nConcerns:\n- flaky timer\n" + block(GOOD)) == {**GOOD, "concerns": ["flaky timer"], "valid": True}
    assert fr.parse("Status: DONE\n" + block({**GOOD, "concerns": ["c1"]}))["concerns"] == ["c1"]
    r = fr.parse("Status: DONE\n" + block({**GOOD, "concerns": "c1"}))
    assert r["valid"] and r["concerns"] == []


def test_long_reply_is_linear():
    t = time.time()
    r = fr.parse("Status: DONE\nFiles changed:\n" + "- a.py\n" * 20000)
    assert r["files"] == ["a.py"] and time.time() - t < 2


def test_brief_message_full():
    p = "/r/p.md"
    assert fr.brief_message("final-reviewer", p, full=True) == (
        "Review the packet /r/p.md as your instructions say. Full review: the packet's FAST PATH line does not apply; "
        "review every section and the diff. " + fr.REVIEW)
    assert fr.brief_message("fixer", "/r/b.md", full=True) == "Read /r/b.md and do what it says. " + fr.WORK
    assert "\n" not in fr.brief_message("final-reviewer", p, full=True)
    assert fr.brief_message("final-reviewer", p) == fr.brief_message("final-reviewer", p, full=False)


def test_result_line_after_test_command_joins_tests():
    r = fr.parse("Status: DONE\nTest command: `sl run_tests --fast t.py`\nResult: `tests (fast): 42 passed, 0 failed`\n")
    assert r["tests"] == "`sl run_tests --fast t.py`; `tests (fast): 42 passed, 0 failed`"


def test_bulleted_label_like_line_under_open_label_is_an_item():
    r = fr.parse("Status: DONE_WITH_CONCERNS\nTest: 3 passed\nConcerns:\n- Tests: flaky on ci\n- slow\n")
    assert r["concerns"] == ["Tests: flaky on ci", "slow"] and r["tests"] == "3 passed"


def test_blank_line_after_empty_label_keeps_it_open():
    r = fr.parse("Status: DONE\nFiles changed:\n\n- a.py\n- b.py\n\nTest: 1 passed\n")
    assert r["files"] == ["a.py", "b.py"] and r["tests"] == "1 passed"


def test_all_bulleted_report_labels_close_sibling_labels():
    r = fr.parse("Status: DONE\n- Files changed: a.py, b.py\n- Tests: 3 passed\n- Red run: none\n- Open questions: none\n")
    assert r["files"] == ["a.py", "b.py"] and r["tests"] == "3 passed" and r["concerns"] == []


def test_deeper_bulleted_label_like_line_stays_an_item():
    r = fr.parse("Status: DONE_WITH_CONCERNS\n- Concerns:\n - Tests: slow path untested\n")
    assert r["concerns"] == ["Tests: slow path untested"] and r["tests"] == ""
