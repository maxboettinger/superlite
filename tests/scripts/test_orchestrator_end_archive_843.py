"""orchestrator end: the run moves into the main checkout's .superlite/runs/<time>-<label>/ with a manifest (#843)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402

ORCH = SCRIPTS / "orchestrator.py"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True, env=env)


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))


def make_run(tmp_path, brief="# Lead brief: B7 (topic)\n", stable=True):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x")
    git(main, "add", "f")
    git(main, "commit", "-qm", "c")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    plans = wt / "docs" / "plans"
    plans.mkdir(parents=True)
    plan = plans / "p.md"
    plan.write_text("# plan\n")
    (plans / "p.build-report.md").write_text("report")
    (plans / "p.build-report.json").write_text("{}")
    sd = wt / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    if stable:
        (sd / "stable.json").write_text(json.dumps({"plan": str(plan)}))
    (sd / "progress.md").write_text("p")
    (sd / "metrics.jsonl").write_text("{}\n")
    if brief:
        (sd / "briefs" / "lead.md").write_text(brief)
    (sd / "briefs" / "T1.md").write_text("t1")
    return main, wt, sd, plan


def dest_of(line):
    return line.split(" files moved to ", 1)[1].split(";", 1)[0]


def test_end_archives_into_main_checkout(tmp_path):
    main, wt, sd, plan = make_run(tmp_path)
    line = orchestrator.end(sd)
    assert re.search(r"run ended; \d+ files moved to ", line)
    dest = (main / ".superlite" / "runs").resolve()
    d = dest_of(line)
    assert d.startswith(str(dest)) and re.search(r"-B7$", d)
    from pathlib import Path
    names = {p.name for p in Path(d).iterdir()}
    assert {"progress.md", "metrics.jsonl", "stable.json", "briefs", "plan.md", "build-report.md",
            "build-report.json", "run.json"} <= names
    assert (Path(d) / "briefs" / "T1.md").exists()
    assert not (sd / "runs").exists()
    assert (sd / "briefs" / "lead.md").exists()
    assert plan.exists() and (plan.parent / "p.build-report.md").exists() and (plan.parent / "p.build-report.json").exists()


def test_manifest_fields(tmp_path):
    main, wt, sd, plan = make_run(tmp_path)
    from pathlib import Path
    d = Path(dest_of(orchestrator.end(sd)))
    m = json.loads((d / "run.json").read_text())
    assert m["id"] == d.name and m["batch"] == "B7" and m["branch"] == "feat"
    assert m["worktree"] == str(wt.resolve()) and m["plan"] == str(plan.resolve())
    assert re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", m["ended"])
    assert m["files"] == sorted(p.name for p in d.iterdir())


def test_end_without_brief_labels_by_checkout(tmp_path):
    main, wt, sd, plan = make_run(tmp_path, brief=None)
    from pathlib import Path
    d = Path(dest_of(orchestrator.end(sd)))
    assert d.name.endswith("-wt")
    assert json.loads((d / "run.json").read_text())["batch"] is None


def test_end_with_plan_argument(tmp_path):
    main, wt, sd, plan = make_run(tmp_path, stable=False)
    from pathlib import Path
    d = Path(dest_of(orchestrator.end(sd, str(plan))))
    assert (d / "plan.md").exists() and (d / "build-report.md").exists() and (d / "build-report.json").exists()


def test_end_outside_git_keeps_sd_runs(tmp_path):
    sd = tmp_path / "plain" / ".superlite"
    sd.mkdir(parents=True)
    (sd / "progress.md").write_text("p")
    line = orchestrator.end(sd)
    assert dest_of(line).startswith(str(sd / "runs"))


def test_nothing_to_end_creates_no_run(tmp_path):
    main, wt, sd, plan = make_run(tmp_path, brief=None)
    for p in list(sd.rglob("*")):
        if p.is_file():
            p.unlink()
    line = orchestrator.end(sd)
    assert "nothing to end" in line
    assert not (main / ".superlite" / "runs").exists()


def test_end_trims_old_runs(tmp_path):
    main, wt, sd, plan = make_run(tmp_path)
    arch = main / ".superlite" / "runs"
    for n in range(30):
        r = arch / f"20261101-1200{n:02d}"
        r.mkdir(parents=True)
        (r / "progress.md").write_text("p")
        (r / "plan.md").write_text("p")
    line = orchestrator.end(sd)
    assert line.endswith("; 1 older runs trimmed")
    old = arch / "20261101-120000"
    assert (old / "progress.md").exists() and not (old / "plan.md").exists()


def test_lead_batch(tmp_path):
    sd = tmp_path / "sd"
    (sd / "briefs").mkdir(parents=True)
    assert orchestrator.lead_batch(sd) is None
    (sd / "briefs" / "lead.md").write_text("# Lead brief: B222 (run-archive)\n")
    assert orchestrator.lead_batch(sd) == "B222"


def test_cli_end_passes_plan(tmp_path):
    main, wt, sd, plan = make_run(tmp_path, stable=False)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(tmp_path / "home"))
    r = subprocess.run([sys.executable, str(ORCH), "end", "--plan", str(plan)], capture_output=True, text=True,
                       cwd=wt, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "run ended" in r.stdout
    from pathlib import Path
    assert (Path(dest_of(r.stdout.strip().splitlines()[0])) / "plan.md").exists()


def test_end_survives_cross_volume_move(tmp_path, monkeypatch):
    import errno
    main, wt, sd, plan = make_run(tmp_path)

    def exdev(*a, **k):
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr(os, "replace", exdev)
    real_rename = os.rename

    def rename(src, dst, *a, **k):
        if "runs" in str(dst):
            raise OSError(errno.EXDEV, "cross-device link")
        return real_rename(src, dst, *a, **k)

    monkeypatch.setattr(os, "rename", rename)
    d = Path(dest_of(orchestrator.end(sd)))
    assert (d / "progress.md").is_file() and (d / "briefs" / "T1.md").is_file()
    assert not (sd / "progress.md").exists()
