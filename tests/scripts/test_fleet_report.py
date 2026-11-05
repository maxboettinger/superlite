# tests/scripts/test_fleet_report.py
import json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_report as fr  # noqa: E402

def block(obj):
    return "```json\n" + json.dumps(obj) + "\n```"

GOOD = {"status": "DONE", "files": ["src/a.py"], "tests": "3 passed", "findings": [], "summary": "ok"}
FINDING = {"file": "src/a.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1}
EMPTY = {"files": [], "tests": "", "findings": [], "summary": "", "valid": False}

def test_json_block_wins():
    assert fr.parse("Status: DONE\n" + block(GOOD)) == {**GOOD, "valid": True}

def test_last_block_counts_and_status_comes_from_json():
    text = block({**GOOD, "status": "BLOCKED"}) + "\nStatus: DONE\n" + block({**GOOD, "status": "DONE_WITH_CONCERNS", "findings": [FINDING]})
    r = fr.parse(text)
    assert r["status"] == "DONE_WITH_CONCERNS" and r["findings"] == [FINDING] and r["valid"]

def test_final_reviewer_block_after_checked_lines():
    text = "Verdict: CHANGES_REQUESTED\nsrc/a.py:12 - off by one - use <= - tier 1\nChecked:\nT1 diff: read\n" + block(
        {"status": "CHANGES_REQUESTED", "files": [], "tests": "", "findings": [FINDING], "summary": "1 finding"})
    assert fr.parse(text) == {"status": "CHANGES_REQUESTED", "files": [], "tests": "", "findings": [FINDING], "summary": "1 finding", "valid": True}

@pytest.mark.parametrize("bad", [
    {**FINDING, "tier": "critical"}, {**FINDING, "tier": 4}, {**FINDING, "tier": True}, {**FINDING, "line": "12"},
    {k: v for k, v in FINDING.items() if k != "fix"}])
def test_bad_finding_breaks_the_block(bad):
    assert fr.parse("Status: DONE\n" + block({**GOOD, "findings": [bad]})) == {"status": "DONE", **EMPTY}

def test_unknown_json_status_and_broken_json_fall_back():
    assert fr.parse("Status: BLOCKED - no db\n" + block({**GOOD, "status": "FINISHED"}))["status"] == "BLOCKED"
    assert fr.parse("Status: NEEDS_CONTEXT\n```json\n{not json\n```") == {"status": "NEEDS_CONTEXT", **EMPTY}

def test_verdict_lines_become_findings_without_a_block():
    text = "Verdict: CHANGES_REQUESTED\nsrc/a.py:12 - off by one - use <= - tier 1\n- src/b.py:3 - crash on empty - guard it - tier 3\nChecked:\nT1 diff: read"
    assert fr.parse(text) == {"status": "CHANGES_REQUESTED", "files": [], "tests": "", "summary": "", "valid": False,
                              "findings": [FINDING, {"file": "src/b.py", "line": 3, "problem": "crash on empty", "fix": "guard it", "tier": 3}]}
    assert fr.parse("Verdict: APPROVED") == {"status": "APPROVED", **EMPTY}

def test_status_regexes_then_unknown():
    assert fr.parse("T3: DONE, all green", "T3")["status"] == "DONE"
    assert fr.parse("Here you go.\nT4 gallery: BLOCKED by the API", "T4")["status"] == "BLOCKED"
    assert fr.parse("no status here") == {"status": "UNKNOWN", **EMPTY}
    assert fr.parse("") == {"status": "UNKNOWN", **EMPTY}

def test_screen_text_never_parses_json():
    assert fr.parse("Status: DONE\n" + block({**GOOD, "status": "BLOCKED"}), allow_json=False) == {"status": "DONE", **EMPTY}

@pytest.mark.parametrize("text", ["```json\n" + "[" * 5000 + "\n```", "```json\n[1, 2]\n```", "```json\n\"x\"\n```",
                                  "\x00﻿" * 1000, '```json\n{"status": "DONE", "findings": {}}\n```'])
def test_parse_never_raises(text):
    assert fr.parse(text)["status"] in fr.STATUSES + ("UNKNOWN",)

def test_brief_messages():
    m = fr.brief_message("fixer", "/r/.superlite/briefs/fix-F-T1-1.md")
    assert m.startswith("Read /r/.superlite/briefs/fix-F-T1-1.md and do what it says. End your reply with the line `Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>`")
    assert '"tier": <1|2|3>' in m and "only the findings still open" in m and "\n" not in m
    f = fr.brief_message("final-reviewer", "/r/.superlite/review-packet.md")
    assert f.startswith("Review the packet /r/.superlite/review-packet.md as your instructions say.")
    assert "<APPROVED|CHANGES_REQUESTED>" in f and "Checked:" in f and "300-word cap" in f and "Status:" not in f and "\n" not in f
