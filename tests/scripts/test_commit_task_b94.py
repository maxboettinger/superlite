"""commit_task: run-folder --plan (#456), review lines with --dispatch (#455), shared tests held for busy workers (#484)."""
import json
import sys
from pathlib import Path

import pytest

from test_run_scripts import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# P

## 9. Implementation plan

### T1 · one · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`

### T4 · four · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`
"""
SHARED = "tests/registry/test_x.py"


@pytest.fixture
def run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/p.md", PLAN)
    write(repo, SHARED, "def test_x():\n    assert 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: None)
    sd = repo / ".superlite"
    sd.mkdir(exist_ok=True)
    return repo, sd, str(repo / "docs/plans/p.md")


def busy(sd, state="busy", brief="- F-T5-1 tests/registry/test_x.py:4 - p - x\n"):
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {
        "W7": {"state": state, "role": "fixer", "task": "fix-F-T5-1"}}}), encoding="utf-8")
    write(sd.parent, ".superlite/briefs/fix-F-T5-1.md", "# Fix F-T5-1\n" + brief)


def edit(repo):
    write(repo, "src/a.py", "X = 1\n")
    write(repo, SHARED, "def test_x():\n    assert 2\n")


def checkpoint_files(sd):
    return json.loads((sd / "checkpoints.json").read_text(encoding="utf-8"))["entries"][-1]["files"]


def test_folder_plan_resolves_and_passes_plan_to_probe_run(run, monkeypatch, tmp_path):
    repo, sd, plan = run
    (sd / "stable.json").write_text(json.dumps({"plan": plan}), encoding="utf-8")
    probe = tmp_path / "probe_run.py"
    probe.write_text("")
    monkeypatch.setenv("SUPERLITE_PROBE_RUN", str(probe))
    seen = []
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: seen.append(cmd))
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", str(sd)]) == 0
    cmd = next(c for c in seen if "--commit" in c)
    assert cmd[-2:] == ["--plan", plan]


def test_folder_plan_without_plan_file_exits_2(run, capsys):
    repo, sd, plan = run
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", str(sd)]) == 2
    assert "is a run folder with no plan file (stable.json, pool.json or plan.md name none); pass the plan file" in capsys.readouterr().err
    assert not (sd / "checkpoints.json").exists()


def hints(monkeypatch, value):
    import fleet_io
    monkeypatch.setattr(fleet_io, "review_hints", value if callable(value) else lambda sd, plan: value)


def test_dispatch_prints_review_line_for_committed_task(run, monkeypatch, capsys):
    import dispatch
    repo, sd, plan = run
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}}), encoding="utf-8")
    hints(monkeypatch, [("T1", ["seam T1-T2"]), ("T3", ["Complexity 6"])])
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: ())
    monkeypatch.setattr(dispatch, "render", lambda *a, **k: None)
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan, "--dispatch"]) == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("review:")]
    assert lines == [f"review: T1 (seam T1-T2); run {commit_task.nt.SCRIPTS / 'sl'} fleet spawn --for-review T1 --plan {plan}"]


def test_no_review_line_without_dispatch_or_fleet_off(run, monkeypatch, capsys):
    import dispatch
    repo, sd, plan = run
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: ())
    monkeypatch.setattr(dispatch, "render", lambda *a, **k: None)
    hints(monkeypatch, [("T1", ["seam T1-T2"])])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}}), encoding="utf-8")
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert "review:" not in capsys.readouterr().out
    (sd / "fleet.json").write_text(json.dumps({"on": False, "workers": {}}), encoding="utf-8")
    write(repo, "src/a.py", "X = 2\n")
    assert commit_task.main(["T1", "--plan", plan, "--dispatch"]) == 0
    assert "review:" not in capsys.readouterr().out
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}}), encoding="utf-8")

    def boom(sd, plan):
        raise OSError("x")
    hints(monkeypatch, boom)
    write(repo, "src/a.py", "X = 3\n")
    assert commit_task.main(["T1", "--plan", plan, "--dispatch"]) == 0
    cap = capsys.readouterr()
    assert "review:" not in cap.out and "warning: no review hints (x)" in cap.err


def test_shared_test_named_in_busy_fixer_brief_is_held(run, capsys):
    repo, sd, plan = run
    busy(sd)
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    err = capsys.readouterr().err
    assert ("left uncommitted (edited by busy W7 (fix-F-T5-1); commit_task T4 again once it is done): "
            + SHARED) in err
    assert "shared-test" not in err
    assert checkpoint_files(sd) == ["src/a.py"]


def test_own_worker_brief_does_not_hold(run, monkeypatch, capsys):
    repo, sd, plan = run
    busy(sd)
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W7")
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert f"shared-test {SHARED}" in capsys.readouterr().err
    assert SHARED in checkpoint_files(sd)


def test_idle_worker_does_not_hold(run, capsys):
    repo, sd, plan = run
    busy(sd, state="idle")
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert f"shared-test {SHARED}" in capsys.readouterr().err


def workers(sd, spec):
    """spec: {wid: (role, label)} all busy; extra fields via a 3rd tuple item."""
    ws = {}
    for wid, item in spec.items():
        role, label, *extra = item
        ws[wid] = {"state": "busy", "role": role, "task": label, **(extra[0] if extra else {})}
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": ws}), encoding="utf-8")


def test_unnamed_busy_worker_holds_shared_test(run, capsys):
    repo, sd, plan = run
    busy(sd, brief="- F-T5-1 tests/registry/test_x2.py:4 - p - x\n")
    write(repo, SHARED, "def test_x():\n    assert 3\n")
    write(repo, "src/a.py", "X = 5\n")
    assert commit_task.main(["T4", "--plan", plan]) == 0
    err = capsys.readouterr().err
    assert ("left uncommitted (changed while busy W7 (fix-F-T5-1) runs; commit_task T4 again once it is done): "
            + SHARED) in err
    assert "shared-test" not in err
    assert checkpoint_files(sd) == ["src/a.py"]


def test_two_busy_workers_named(run, capsys):
    repo, sd, plan = run
    workers(sd, {"W3": ("implementer", "T6"), "W7": ("fixer", "fix-F-T5-1")})
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert ("left uncommitted (changed while busy W3 (T6), W7 (fix-F-T5-1) run; commit_task T4 again once they are done): "
            + SHARED) in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/a.py"]


def test_own_report_lists_shared_test(run, capsys):
    repo, sd, plan = run
    workers(sd, {"W3": ("implementer", "T6")})
    write(sd.parent, ".superlite/fleet/reports/T4.json",
          json.dumps({"label": "T4", "role": "implementer", "files": [SHARED]}))
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert f"shared-test {SHARED}" in capsys.readouterr().err
    assert SHARED in checkpoint_files(sd)


def test_caller_worker_edit_after_send_joins(run, monkeypatch, capsys):
    repo, sd, plan = run
    edit(repo)
    sent = int(Path(repo / SHARED).stat().st_mtime * 1000) - 5000
    workers(sd, {"W9": ("implementer", "T4", {"sent": sent}), "W3": ("implementer", "T6")})
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W9")
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert f"shared-test {SHARED}" in capsys.readouterr().err
    assert SHARED in checkpoint_files(sd)


@pytest.mark.parametrize("role", ["final-reviewer", "research"])
def test_reader_roles_do_not_hold(run, capsys, role):
    repo, sd, plan = run
    workers(sd, {"W5": (role, "rev-x")})
    edit(repo)
    assert commit_task.main(["T4", "--plan", plan]) == 0
    assert f"shared-test {SHARED}" in capsys.readouterr().err
    assert SHARED in checkpoint_files(sd)


def test_commit_without_plan_uses_stable_plan(run, monkeypatch):
    repo, sd, plan = run
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(sd))
    (sd / "stable.json").write_text(json.dumps({"plan": "docs/plans/p.md"}), encoding="utf-8")
    assert not (sd / "plan.md").exists()
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1"]) == 0
    assert checkpoint_files(sd) == ["src/a.py"]


def test_only_held_file_fails(run, capsys):
    repo, sd, plan = run
    busy(sd)
    write(repo, SHARED, "def test_x():\n    assert 2\n")
    assert commit_task.main(["T4", "--plan", plan]) == 1
    out = capsys.readouterr().out
    assert f"T4 FAILED: nothing to commit; held for busy W7: {SHARED}" in out
