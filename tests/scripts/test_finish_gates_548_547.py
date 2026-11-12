"""#548/#547: finish does not file a signal-killed no-result, and refuses while render edits are applied."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402


def test_signal_kill_not_filed(tmp_path):
    log = tmp_path / "incidents.jsonl"
    rows = [
        {"kind": "no-result", "tool": "run_tests", "file": "-", "signal": "SIGKILL"},
        {"kind": "no-result", "tool": "run_tests", "file": "-"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert finish.read_stops(log) == [("no-result", "run_tests", "")]


def test_open_render_edit_refuses(tmp_path, capsys):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "render-edits.json").write_text(
        json.dumps({"files": {"Demo/Seed.swift": {"existed": True}}, "started": 1}), encoding="utf-8")
    (sd / "progress.md").write_text("", encoding="utf-8")
    (sd / "incidents.jsonl").write_text("", encoding="utf-8")
    (sd / "stable.json").write_text("{}", encoding="utf-8")
    assert finish.main(["--ledger", str(sd / "progress.md"), "--log", str(sd / "incidents.jsonl")]) == 2
    cap = capsys.readouterr()
    assert "BLOCKED: render edits still applied: Demo/Seed.swift; run sl render_edit restore first" in cap.out + cap.err
