"""#907: commit_task Tn fails when Tn edited a file another task owns."""
import json
import os
import subprocess
import sys

import pytest

from test_run_scripts import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# P

## 9. Implementation plan

### T1 · one · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`

### T2 · two · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/map.py`

### T3 · three · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/c.py`
"""


@pytest.fixture
def run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/p.md", PLAN)
    for f in ("a", "map", "c"):
        write(repo, f"src/{f}.py", "X = 0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: None)
    sd = repo / ".superlite"
    sd.mkdir(exist_ok=True)
    return repo, sd, str(repo / "docs/plans/p.md")


def report(sd, label, files):
    p = sd / "fleet" / "reports" / f"{label}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"label": label, "role": "implementer", "files": files}), encoding="utf-8")
    return p


def pool(sd, busy):
    agents = [{"id": f"W{i}", "busy": True, "current": t} for i, t in enumerate(busy, 1)]
    (sd / "pool.json").write_text(json.dumps({"agents": agents}), encoding="utf-8")


def stable(sd, plan, dirty):
    (sd / "stable.json").write_text(json.dumps({"plan": plan, "baseline_dirty": dirty}), encoding="utf-8")


def entries(sd):
    return json.loads((sd / "checkpoints.json").read_text(encoding="utf-8"))["entries"]


def files(sd):
    return entries(sd)[-1]["files"]


def edit(repo, *names, n=1):
    for f in names:
        write(repo, f"src/{f}.py", f"X = {n}\n")


def go(args, p):
    return commit_task.main(args + ["--plan", p])


def test_report_names_foreign_file_fails(run, capsys):
    repo, sd, p = run
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1"], p) == 1
    cap = capsys.readouterr()
    assert "T1 FAILED: edits src/map.py owned by T2" in cap.out
    assert f"next: commit_task T1 --also src/map.py --ruling TEXT --plan {p}" in cap.err
    assert not (sd / "checkpoints.json").exists()


def test_also_ruling_commits_it(run):
    repo, sd, p = run
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1"], p) == 1
    assert go(["T1", "--also", "src/map.py", "--ruling", "needs the mapper"], p) == 0
    assert sorted(files(sd)) == ["src/a.py", "src/map.py"]
    assert "Ruling: T1 also commits src/map.py - needs the mapper" in (sd / "progress.md").read_text(encoding="utf-8")


def test_claim_then_commit(run):
    repo, sd, p = run
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1", "--claim", "src/map.py", "--ruling", "x"], p) == 0
    assert go(["T1"], p) == 0
    assert "src/map.py" in files(sd)


def test_owner_in_call_commits_it(run, capsys):
    repo, sd, p = run
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1", "T2"], p) == 0
    assert "FAILED" not in capsys.readouterr().out
    es = entries(sd)
    assert "src/map.py" in es[-1]["files"]
    assert "src/map.py" not in es[-2]["files"]


def test_owner_checkpointed_first(run):
    repo, sd, p = run
    edit(repo, "a", "map")
    assert go(["T2"], p) == 0
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1"], p) == 0
    assert files(sd) == ["src/a.py"]


def test_two_files_reason_and_hint(run, capsys):
    repo, sd, p = run
    edit(repo, "a", "map", "c")
    report(sd, "T1", ["src/a.py", "src/map.py", "src/c.py"])
    assert go(["T1"], p) == 1
    cap = capsys.readouterr()
    assert "T1 FAILED: edits src/c.py owned by T3; edits src/map.py owned by T2" in cap.out
    assert f"next: commit_task T1 --also src/c.py src/map.py --ruling TEXT --plan {p}" in cap.err


def test_running_owner_hint(run, capsys):
    repo, sd, p = run
    pool(sd, ["T2"])
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    assert go(["T1"], p) == 1
    cap = capsys.readouterr()
    assert "T1 FAILED: edits src/map.py owned by T2" in cap.out
    assert (f"next: once T2 is done: commit_task T2 T1 --plan {p}, or "
            f"commit_task T1 --also src/map.py --ruling TEXT --plan {p}") in cap.err


def test_running_owner_without_report_silent(run, capsys):
    repo, sd, p = run
    pool(sd, ["T2"])
    edit(repo, "a", "map")
    report(sd, "T1", ["src/a.py"])
    assert go(["T1"], p) == 0
    cap = capsys.readouterr()
    assert files(sd) == ["src/a.py"]
    assert "edits" not in cap.out and "edits" not in cap.err


def test_foreign_only_change_fails_edits(run, capsys):
    repo, sd, p = run
    edit(repo, "map")
    report(sd, "T1", ["src/map.py"])
    assert go(["T1"], p) == 1
    out = capsys.readouterr().out
    assert "T1 FAILED: edits src/map.py owned by T2" in out
    assert "nothing to commit" not in out


def test_owned_note_dropped_on_failure(run, capsys):
    repo, sd, p = run
    edit(repo, "map")
    assert go(["T2"], p) == 0
    edit(repo, "map", n=2)
    edit(repo, "a")
    report(sd, "T1", ["src/a.py", "src/map.py"])
    capsys.readouterr()
    assert go(["T1"], p) == 1
    cap = capsys.readouterr()
    assert "T1 FAILED: edits src/map.py owned by T2" in cap.out
    assert "left uncommitted (owned by T2" not in cap.err


def test_stale_report_ignored(run, capsys):
    repo, sd, p = run
    edit(repo, "a")
    report(sd, "T1", ["src/a.py"])
    assert go(["T1"], p) == 0
    ct = int(subprocess.run(["git", "show", "-s", "--format=%ct", entries(sd)[-1]["sha"]],
                            capture_output=True, text=True, check=True).stdout.strip())
    rp = report(sd, "T1", ["src/a.py", "src/map.py"])
    os.utime(rp, (ct - 100, ct - 100))
    edit(repo, "a", "map", n=2)
    capsys.readouterr()
    assert go(["T1"], p) == 0
    assert files(sd) == ["src/a.py"]
    assert "edits" not in capsys.readouterr().out


def fallback_setup(run):
    repo, sd, p = run
    pool(sd, [])
    stable(sd, p, [])
    edit(repo, "a", "map")
    return repo, sd, p


def test_fallback_fails_single_task(run, capsys):
    repo, sd, p = fallback_setup(run)
    assert go(["T1"], p) == 1
    assert "T1 FAILED: edits src/map.py owned by T2" in capsys.readouterr().out


@pytest.mark.parametrize("case", ["no-pool", "other-running", "dirty-before", "no-baseline",
                                  "busy-editor", "two-task-call", "owner-committed"])
def test_fallback_off_cases(run, capsys, case):
    repo, sd, p = fallback_setup(run)
    args = ["T1"]
    if case == "no-pool":
        (sd / "pool.json").unlink()
    elif case == "other-running":
        pool(sd, ["T3"])
    elif case == "dirty-before":
        stable(sd, p, ["src/map.py"])
    elif case == "no-baseline":
        (sd / "stable.json").unlink()
    elif case == "busy-editor":
        (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {
            "W3": {"state": "busy", "role": "implementer", "task": "T3"}}}), encoding="utf-8")
    elif case == "two-task-call":
        edit(repo, "c")
        args = ["T1", "T3"]
    elif case == "owner-committed":
        assert go(["T1", "T2"], p) == 0
        edit(repo, "a", "map", n=2)
    capsys.readouterr()
    assert go(args, p) == 0
    cap = capsys.readouterr()
    assert "src/map.py" not in files(sd)
    assert "edits" not in cap.out
    if case == "owner-committed":
        assert "left uncommitted (owned by T2, changed after its checkpoint; run commit_task T2): src/map.py" in cap.err


def test_helpers(tmp_path):
    sd = tmp_path / "sd"
    rp = sd / "fleet" / "reports" / "T1.json"
    rp.parent.mkdir(parents=True)
    rp.write_text(json.dumps({"label": "T1", "files": ["src/map.py"]}), encoding="utf-8")
    os.utime(rp, (200, 200))
    assert commit_task.fresh_report_files(sd, "T1", 100) == ["src/map.py"]
    assert commit_task.fresh_report_files(sd, "T1", 300) == []
    assert commit_task.fresh_report_files(sd, "T1", None) == ["src/map.py"]
    assert commit_task.fresh_report_files(sd, "T9", None) == []
    led = tmp_path / "progress.md"
    led.write_text("- commit T1 abc1234\n- commit T2 def5678\n- commit T1 0123abc\n", encoding="utf-8")
    assert commit_task.last_checkpoint(str(led), "T1") == "0123abc"
    assert commit_task.last_checkpoint(str(led), "T3") is None
    assert commit_task.last_checkpoint(str(tmp_path / "none.md"), "T1") is None
    ok = tmp_path / "ok.json"
    ok.write_text('{"agents": []}', encoding="utf-8")
    lst = tmp_path / "l.json"
    lst.write_text("[1]", encoding="utf-8")
    bad = tmp_path / "b.json"
    bad.write_text("nope", encoding="utf-8")
    assert commit_task.pool_readable(str(ok)) is True
    assert commit_task.pool_readable(str(tmp_path / "missing.json")) is False
    assert commit_task.pool_readable(str(lst)) is False
    assert commit_task.pool_readable(str(bad)) is False
