"""Both fix briefs name the reviewed checkpoint (#670)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "scripts"))
import findings  # noqa: E402
from test_plan_tools import make_plan  # noqa: E402

ST = {"run": "p-20261113", "entries": [{"task": "T1", "sha": "a1"}, {"task": "T2", "sha": "b2"}, {"task": "T1", "sha": "c3"}]}
TAIL = "restore from it or from your own saved patch, never with `git checkout --` in the shared tree."
NONE = ("Reviewed version: no checkpoint yet; save `git diff -- <file>` as a patch under .superlite/ before an experiment "
        "and revert with `git apply -R` of that patch, never with `git checkout --` in the shared tree.")
HEAD = ("Reviewed version: newest checkpoint c3 (T1, ref refs/superlite/p-20261113/T1): "
        "`git show c3:<path>` prints a file as reviewed; " + TAIL)


def test_checkpoint_line_task_entry():
    assert findings.checkpoint_line(ST, "T2") == (
        "Reviewed version: T2's checkpoint b2 (ref refs/superlite/p-20261113/T2): "
        "`git show b2:<path>` prints a file as reviewed; " + TAIL)


def test_checkpoint_line_chain_head():
    assert findings.checkpoint_line(ST, None) == HEAD


def test_checkpoint_line_unknown_task_uses_head():
    assert findings.checkpoint_line(ST, "T9") == HEAD


def test_checkpoint_line_none():
    assert findings.checkpoint_line(None, "T1") == NONE


def test_checkpoint_line_empty_entries():
    assert findings.checkpoint_line({"run": "r", "entries": []}, "T1") == NONE
    assert findings.checkpoint_line({"entries": [{"task": "T1", "sha": "a"}]}, "T1") == NONE
    assert findings.checkpoint_line({"run": "r", "entries": "x"}, "T1") == NONE


def _item():
    return {"id": "F-T2-1", "file": "src/a.py", "line": 3, "problem": "p", "fix": "f", "tier": 1, "label": "FR1"}


def test_brief_text_names_task_checkpoint(monkeypatch):
    monkeypatch.setattr(findings.commit_task.autocommit, "load_state", lambda: ST)
    task = SimpleNamespace(id="T2", owns=["src/a.py"])
    lines = findings.brief_text("/abs/sl", Path("/abs/plan.md"), task, [_item()], 1).splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("Task: T2 · Owns:"))
    assert lines[i + 1] == findings.checkpoint_line(ST, "T2")


def test_coordinator_text_names_newest_checkpoint(monkeypatch):
    monkeypatch.setattr(findings.commit_task.autocommit, "load_state", lambda: ST)
    lines = findings.coordinator_text("/abs/sl", Path("/abs/plan.md"), [_item()], 1, ["T3"]).splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("Task: none · running:"))
    assert lines[i + 1] == findings.checkpoint_line(ST, None)


def test_route_brief_file_names_checkpoint(tmp_path, monkeypatch):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    (root / ".git").mkdir()
    rep = sd / "fleet" / "reports" / "FR1.json"
    rep.write_text(json.dumps({"id": "W4", "label": "FR1", "status": "CHANGES_REQUESTED", "valid": True,
                               "findings": [{"file": "src/a.py", "line": 1, "problem": "p", "fix": "x", "tier": 1}]}))
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}])
    (sd / "progress.md").write_text("- commit T1 abcdef1234 done\n")
    (sd / "checkpoints.json").write_text(json.dumps({"run": "r-1", "entries": [{"task": "T1", "sha": "deadbee"}]}))
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    findings.route(sd, plan, [str(rep)], "/sl/sl")
    briefs = list((sd / "briefs").glob("*"))
    assert briefs
    want = ("Reviewed version: T1's checkpoint deadbee (ref refs/superlite/r-1/T1): "
            "`git show deadbee:<path>` prints a file as reviewed; " + TAIL)
    assert any(want in b.read_text() for b in briefs)
