"""finish.read_stops appends a rule-block row's rule and cwd to the target (#233)."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402


def write(tmp_path, *rows):
    p = tmp_path / "incidents.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


FULL = {"kind": "rule-block", "agent": "coordinator", "tool": "Bash", "target": "rm src/a.py", "rule": "code", "cwd": "/p/src"}


def test_read_stops_appends_rule_and_cwd(tmp_path):
    assert finish.read_stops(write(tmp_path, FULL)) == [("rule-block", "Bash", "rm src/a.py (rule code, cwd /p/src)")]


def test_read_stops_rule_only(tmp_path):
    row = {"kind": "rule-block", "tool": "Agent", "target": "superlite:implementer (fleet on)", "rule": "fleet"}
    assert finish.read_stops(write(tmp_path, row)) == [("rule-block", "Agent", "superlite:implementer (fleet on) (rule fleet)")]


def test_read_stops_cwd_only(tmp_path):
    row = {"kind": "rule-block", "tool": "Bash", "target": "x", "cwd": "/p"}
    assert finish.read_stops(write(tmp_path, row)) == [("rule-block", "Bash", "x (cwd /p)")]


def test_read_stops_without_rule_keeps_target(tmp_path):
    a = {"kind": "rule-block", "tool": "Bash", "target": "x"}
    b = dict(a, rule="", cwd="")
    assert finish.read_stops(write(tmp_path, a, b)) == [("rule-block", "Bash", "x")] * 2


def test_cwd_whitespace_is_flattened(tmp_path):
    row = dict(FULL, rule="", cwd="/a\nb")
    assert finish.read_stops(write(tmp_path, row))[0][2] == "rm src/a.py (cwd /a b)"
    row = dict(FULL, cwd="/a\nb")
    assert finish.read_stops(write(tmp_path, row))[0][2].endswith("(rule code, cwd /a b)")


def test_log_auto_entry_names_the_rule(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    assert finish.log_auto(finish.read_stops(write(tmp_path, FULL))) == 1
    rows = [json.loads(x) for x in (home / "feedback.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert "rule-block: rm src/a.py (rule code, cwd /p/src)" in rows[0]["text"]
