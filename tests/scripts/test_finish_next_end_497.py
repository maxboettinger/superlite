"""#497: finish ends with `sl orchestrator end` as its own next step; the finishing skill has a conflict step."""
from __future__ import annotations

import json
from pathlib import Path

from test_plan_tools import ROOT, SCRIPTS, run

FINISH = SCRIPTS / "finish.py"
TAIL = " (archives the run markers; the coordinator guard blocks every edit, a merge-conflict fix too, until it runs)"


def lines(tmp_path, *extra, incidents=""):
    led = tmp_path / "progress.md"
    led.write_text("- commit T1 abcdef1234 t1\n", encoding="utf-8")
    (tmp_path / "incidents.jsonl").write_text(incidents, encoding="utf-8")
    out = run(FINISH, "--ledger", led, "--log", tmp_path / "incidents.jsonl", *extra, cwd=tmp_path).out
    return [ln for ln in out.splitlines() if ln.strip()]


def test_next_line_is_last(tmp_path):
    out = lines(tmp_path)
    assert out[-1] == "next: sl orchestrator end" + TAIL
    assert not any(ln.startswith("after finishing:") for ln in out)


def test_next_line_is_last_with_open_incidents(tmp_path):
    inc = json.dumps({"file": "a.py", "line": 3, "context": "boom", "agent": "probe_run", "status": "open"}) + "\n"
    out = lines(tmp_path, incidents=inc)
    assert out[-1] == "next: sl orchestrator end" + TAIL


def test_finishing_skill_has_conflict_step():
    text = (ROOT / "skills" / "finishing-a-development-branch" / "SKILL.md").read_text(encoding="utf-8")
    for need in ("conflict", "sl orchestrator end", "git merge", "run_tests --full"):
        assert need in text, need
