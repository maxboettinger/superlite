"""`status.active` / `status.active_lines` and `state.run_markers` (#671)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402
import state  # noqa: E402
import status  # noqa: E402


@pytest.fixture(autouse=True)
def held(monkeypatch):
    monkeypatch.setattr(autocommit, "held_files", lambda root: {"covered": [], "edited": []}, raising=False)


def put(sd, name, data):
    sd.mkdir(parents=True, exist_ok=True)
    (sd / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def make_sd(tmp_path):
    sd = tmp_path / "proj" / ".superlite"
    sd.mkdir(parents=True)
    return sd


def test_run_markers_order(tmp_path):
    sd = make_sd(tmp_path)
    put(sd, "orchestrator.json", {})
    put(sd, "inline-flow.json", {})
    put(sd, "prime.md", "x")
    (sd / "pool.json").mkdir()
    assert state.run_markers(sd) == ["prime.md", "orchestrator.json", "inline-flow.json"]


def test_no_run(tmp_path):
    sd = make_sd(tmp_path)
    r = status.active(sd)
    assert r["active"] is False and r["kind"] is None
    assert r["worktrees"][0]["busy"] == []


def test_plan_run_markers_and_busy(tmp_path):
    sd = make_sd(tmp_path)
    put(sd, "stable.json", {})
    put(sd, "pool.json", {"agents": [{"id": "a1", "busy": True}]})
    assert status.active(sd) == {
        "active": True, "kind": "plan run", "state_dir": str(sd), "markers": ["stable.json", "pool.json"],
        "batch": None, "worktrees": [{"path": str(sd.parent), "batch": None, "state": None, "busy": ["a1"]}],
        "checkpoint_files": [], "edited_after_checkpoint": []}


def test_orchestrator_alone_is_plan_run(tmp_path):
    sd = make_sd(tmp_path)
    put(sd, "orchestrator.json", {})
    r = status.active(sd)
    assert r["kind"] == "plan run" and r["markers"] == ["orchestrator.json"]


def test_busy_worker_alone_is_plan_run(tmp_path):
    sd = make_sd(tmp_path)
    put(sd, "fleet.json", {"on": True, "workers": {"W1": {"state": "ready"}, "W2": {"state": "busy", "task": "T3"},
                                                    "W3": {"state": "stopped"}}})
    r = status.active(sd)
    assert r["kind"] == "plan run" and r["markers"] == [] and r["worktrees"][0]["busy"] == ["W2"]


def backlog_main(tmp_path):
    sd = make_sd(tmp_path)
    wt1, wt2 = tmp_path / "wt1", tmp_path / "wt2"
    put(wt1 / ".superlite", "fleet.json", {"on": True, "workers": {"W2": {"state": "busy", "task": "T1"}}})
    put(wt1 / ".superlite", "pool.json", {"agents": [{"id": "a9", "busy": True}]})
    put(sd, "backlog.json", {"batches": [
        {"id": "B1", "state": "running", "worktree": str(wt1)},
        {"id": "B2", "state": "shipped", "worktree": str(wt2)},
        {"id": "B3", "state": "needs_decision", "worktree": ""},
        {"id": "B4", "state": "parked"}, {"id": "B5", "state": "planned"}]})
    put(sd, "fleet.json", {"on": True, "workers": {"W5": {"state": "busy", "task": "T9"}}})
    return sd, wt1


def test_backlog_main(tmp_path):
    sd, wt1 = backlog_main(tmp_path)
    r = status.active(sd)
    assert r["kind"] == "backlog main" and r["markers"] == ["backlog.json"]
    assert r["worktrees"] == [
        {"path": str(sd.parent), "batch": None, "state": None, "busy": ["W5"]},
        {"path": str(wt1), "batch": "B1", "state": "running", "busy": ["a9", "W2"]},
        {"path": "", "batch": "B3", "state": "needs_decision", "busy": []}]


def test_backlog_all_done_is_no_run(tmp_path):
    sd = make_sd(tmp_path)
    put(sd, "backlog.json", {"batches": [{"id": "B1", "state": "shipped"}, {"id": "B2", "state": "parked"},
                                         {"id": "B3", "state": "planned"}]})
    r = status.active(sd)
    assert r["active"] is False and r["markers"] == []


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                   capture_output=True)


def lead_repo(tmp_path, st):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x")
    git(main, "add", "f")
    git(main, "commit", "-q", "-m", "c")
    git(main, "worktree", "add", "-q", "../wt", "-b", "b")
    wt = tmp_path / "wt"
    put(main / ".superlite", "backlog.json", {"batches": [{"id": "B7", "state": st, "worktree": str(wt)}]})
    return wt


def test_lead(tmp_path):
    wt = lead_repo(tmp_path, "running")
    sd = wt / ".superlite"
    sd.mkdir()
    r = status.active(sd)
    assert r["kind"] == "lead" and r["batch"] == "B7"
    assert r["worktrees"][0] == {"path": str(wt), "batch": "B7", "state": "running", "busy": []}


def test_lead_shipped_is_no_run(tmp_path):
    wt = lead_repo(tmp_path, "shipped")
    sd = wt / ".superlite"
    sd.mkdir()
    assert status.active(sd)["active"] is False


def test_corrupt_files(tmp_path):
    sd = make_sd(tmp_path)
    for n in ("pool.json", "fleet.json", "backlog.json"):
        put(sd, n, "{")
    assert status.active(sd)["active"] is False


def test_checkpoint_fields(tmp_path, monkeypatch):
    sd = make_sd(tmp_path)
    monkeypatch.setattr(autocommit, "held_files", lambda root: {"covered": ["a.py"], "edited": ["b.py"]},
                        raising=False)
    r = status.active(sd)
    assert r["checkpoint_files"] == ["a.py"] and r["edited_after_checkpoint"] == ["b.py"] and not r["active"]


def test_lines_active(tmp_path):
    sd, wt1 = backlog_main(tmp_path)
    assert status.active_lines(status.active(sd)) == [
        f"run active: backlog main in {sd}; markers: backlog.json",
        f"worktree {sd.parent} (this checkout): busy W5",
        f"worktree {wt1} (B1 running): busy a9, W2",
        "worktree  (B3 needs_decision): no busy workers"]


def test_lines_lead_and_checkpoints():
    files = [f"f{i:02d}.py" for i in range(12)]
    rep = {"active": True, "kind": "lead", "state_dir": "/w/.superlite", "markers": [], "batch": "B7",
           "worktrees": [{"path": "/w", "batch": "B7", "state": "running", "busy": []}],
           "checkpoint_files": files, "edited_after_checkpoint": ["b.py"]}
    assert status.active_lines(rep) == [
        "run active: lead B7 in /w/.superlite",
        "worktree /w (this checkout): no busy workers",
        "checkpoint files: 12: " + ", ".join(files[:10]) + " (+2 more)",
        "edited after checkpoint: 1: b.py"]


def test_lines_none():
    rep = {"active": False, "kind": None, "state_dir": "/r/.superlite", "markers": [], "batch": None,
           "worktrees": [{"path": "/r", "batch": None, "state": None, "busy": []}], "checkpoint_files": [],
           "edited_after_checkpoint": []}
    assert status.active_lines(rep) == ["run active: none in /r/.superlite"]


def test_signatures_match_plan_671():
    import inspect
    import state
    import status
    for fn in (state.run_markers, status.busy_ids, status.active_lines):
        assert inspect.signature(fn).return_annotation == "list[str]" or inspect.signature(fn).return_annotation == list[str], fn.__name__
