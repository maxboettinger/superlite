"""Worker reports carry the red-run evidence as a `red` field (#405)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_report as fr  # noqa: E402

RED = "tests (fast): 0 passed, 1 failed"
GOOD = {"status": "DONE", "files": ["src/a.py"], "tests": "3 passed", "findings": [], "summary": "ok", "concerns": []}


def block(obj):
    return "```json\n" + json.dumps(obj) + "\n```\n"


def test_json_red_field_is_carried():
    assert fr.parse("Status: DONE\n" + block({**GOOD, "red": RED})) == {**GOOD, "red": RED, "valid": True}


def test_json_without_red_takes_the_red_run_line():
    r = fr.parse("Red run: tests (fast): 0 passed, 2 failed\nStatus: DONE\n" + block(GOOD))
    assert r["valid"] and r["red"] == "tests (fast): 0 passed, 2 failed"


def test_empty_json_red_takes_the_red_run_line():
    r = fr.parse("- Red run: none - no test\nStatus: DONE\n" + block({**GOOD, "red": ""}))
    assert r["valid"] and r["red"] == "none - no test"


def test_bold_bullet_line_without_json():
    assert fr.parse("Status: DONE\n- **Red run:** none - no test\n") == {
        "status": "DONE", "files": [], "tests": "", "red": "none - no test", "findings": [], "summary": "",
        "concerns": [], "valid": False}


def test_last_red_run_line_counts():
    text = "Red run: tests (fast): 0 passed, 1 failed\nRed run: tests (fast): 1 passed, 2 failed\nStatus: DONE"
    assert fr.parse(text)["red"] == "tests (fast): 1 passed, 2 failed"


def test_blank_red_run_line_is_empty():
    assert fr.parse("Red run:   \nStatus: DONE")["red"] == ""


def test_non_string_red_breaks_the_block():
    r = fr.parse("Status: DONE\n" + block({**GOOD, "red": ["T1: " + RED]}))
    assert r["status"] == "DONE" and not r["valid"] and r["red"] == ""


def test_no_red_anywhere_is_empty():
    for text in ("Status: DONE", "", "Verdict: APPROVED"):
        assert fr.parse(text)["red"] == "", text


def test_screen_text_still_reads_the_line():
    r = fr.parse("Status: DONE\nRed run: " + RED + "\n" + block({**GOOD, "red": "x"}), allow_json=False)
    assert r["red"] == RED and not r["valid"]


def test_work_contract_asks_for_red_between_tests_and_findings():
    field = '"red": "<the summary line of the run that saw your new tests fail, or none - no test>"'
    assert fr.WORK.count(field) == 1
    assert fr.WORK.index('"tests"') < fr.WORK.index(field) < fr.WORK.index('"findings"')
    assert '"red"' not in fr.REVIEW


def test_crlf_reply_has_no_carriage_return():
    r = fr.parse("Red run: " + RED + "\r\nStatus: DONE\r\n")
    assert r["red"] == RED


def test_fully_bold_line_drops_the_closing_stars():
    assert fr.parse("**Red run: " + RED + "**\nStatus: DONE")["red"] == RED


def test_backticked_and_bold_label_forms():
    for line in ("- `Red run:` " + RED, "* **Red run**: " + RED, "`Red run`: " + RED):
        assert fr.parse(line + "\nStatus: DONE")["red"] == RED, line
