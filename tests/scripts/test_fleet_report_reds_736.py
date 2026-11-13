"""A batch worker's red runs parse per task into `reds` (#736)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_report as fr  # noqa: E402

R1 = "tests (fast): 0 passed, 1 failed"
R2 = "tests (fast): 0 passed, 2 failed"
BOTH = {"T5": R1, "T6": R2}
GOOD = {"status": "DONE", "files": ["src/a.py"], "tests": "3 passed", "findings": [], "summary": "ok", "concerns": []}


def block(obj):
    return "```json\n" + json.dumps(obj) + "\n```\n"


def test_header_list_items():
    for b1, b2 in (("- ", "- "), ("* ", "* "), ("1. ", "2. ")):
        r = fr.parse(f"Red run:\n{b1}T5: {R1}\n{b2}T6: {R2}\n\nStatus: DONE\n", "T5,T6")
        assert r["reds"] == BOTH and r["red"] == "" and r["status"] == "DONE"
    r = fr.parse(f"Red run:\n\n- T5: {R1}\n- T6: {R2}\n")
    assert r["reds"] == BOTH


def test_indented_items():
    assert fr.parse(f"Red run:\n  T5: {R1}\n  T6: {R2}\n")["reds"] == BOTH
    assert fr.parse(f"**Red runs:**\n- **T5:** {R1}\n- `T6`: {R2}\n")["reds"] == BOTH


def test_red_run_tn_lines():
    r = fr.parse(f"- Red run T5: {R1}\n- **Red run T6:** {R2}\nStatus: DONE\n")
    assert r["reds"] == BOTH and r["red"] == ""
    assert fr.parse(f"Red run (T5): {R1}\n")["reds"] == {"T5": R1}


def test_json_red_object():
    r = fr.parse("Status: DONE\n" + block({**GOOD, "red": {"T5": R1, "T6": " " + R2 + " "}}))
    assert r["valid"] and r["reds"] == BOTH and r["red"] == ""
    r = fr.parse(f"Red run: {R1}\nStatus: DONE\n" + block({**GOOD, "red": {"T5": R1, "T6": R2}}))
    assert r["valid"] and r["red"] == R1


def test_json_red_object_with_a_non_string_breaks_the_block():
    assert fr.parse("Status: DONE\n" + block({**GOOD, "red": {"T5": 1}}))["valid"] is False
    assert fr.parse("Status: DONE\n" + block({**GOOD, "red": ["x"]}))["valid"] is False


def test_header_items_stay_out_of_files():
    for text in (f"Files changed:\n- src/a.py\nRed run:\n- T5: {R1}\nStatus: DONE\n",
                 f"- Files changed:\n  - src/a.py\n- Red run:\n  - T5: {R1}\nStatus: DONE\n"):
        r = fr.parse(text)
        assert r["files"] == ["src/a.py"] and r["reds"] == {"T5": R1} and r["concerns"] == []


def test_list_ends_at_the_first_other_line():
    assert fr.parse(f"Red run:\n- T5: {R1}\nT6 needed no test.\n- T7: {R2}\n")["reds"] == {"T5": R1}


def test_later_entry_wins():
    assert fr.parse(f"Red run T5: {R2}\nRed run T5: {R1}\n")["reds"] == {"T5": R1}


def test_single_report_unchanged():
    r = fr.parse(f"Red run: {R1}\nStatus: DONE\n")
    assert r["red"] == R1 and r["reds"] == {}
    assert fr.parse("")["reds"] == {}
    assert fr.parse("Verdict: APPROVED\n")["reds"] == {}


def test_work_batch():
    one = '"red": "<the summary line of the run that saw your new tests fail, or none - no test>"'
    many = '"red": {"<task id>": "<the summary line of the run that saw that task\'s new tests fail, or none - no test>"}'
    assert fr.WORK_BATCH != fr.WORK and many in fr.WORK_BATCH
    assert fr.WORK_BATCH.replace(many, one) == fr.WORK
    assert fr.RED_ONE == one and fr.RED_MANY == many
