"""#843: a run ended in a worktree outlives it: report and the predictor find it in the main checkout."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_metrics_history import setup_run
from test_plan_tools import SCRIPTS, run
from test_report import REPORT
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import predict_live  # noqa: E402

ORCH = SCRIPTS / "orchestrator.py"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True, env=env)


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))


def test_run_survives_worktree_removal(tmp_path):
    main, src = tmp_path / "main", tmp_path / "src"
    main.mkdir()
    src.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x")
    git(main, "add", "f")
    git(main, "commit", "-qm", "c")
    wt, wt2 = tmp_path / "wt", tmp_path / "wt2"
    git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    git(main, "worktree", "add", "-q", str(wt2), "-b", "other")
    # a real report pair, made by report.py in a scratch folder
    sp = mech_plan(src, 2, name="p.md")
    setup_run(src)
    cp = run(REPORT, "--plan", sp, "--dir", src / ".superlite", cwd=src)
    assert cp.returncode == 0, cp.both
    plans = wt / "docs" / "plans"
    plans.mkdir(parents=True)
    plan = plans / "p.md"
    plan.write_text("# plan\n")
    for ext in ("md", "json"):
        shutil.copy(src / f"p.build-report.{ext}", plans / f"p.build-report.{ext}")
    git(wt, "add", "docs")
    git(wt, "commit", "-qm", "plan")
    sd = wt / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan)}))
    (sd / "progress.md").write_text("".join("- tests full passed=900 failed=0 skipped=2 seconds=240\n" for _ in range(3)))
    (sd / "metrics.jsonl").write_text("{}\n")
    (sd / "briefs" / "lead.md").write_text("# Lead brief: B9 (t)\n")
    cp = run(ORCH, "end", "--plan", plan, cwd=wt)
    assert cp.returncode == 0, cp.both
    git(main, "worktree", "remove", "--force", str(wt))
    assert not wt.exists()
    lst = run(REPORT, "--list", "--root", main, cwd=main).out
    m = re.search(r"^  (\S+-B9)  p  B9  ", lst, re.M)
    assert m, lst
    rid = m.group(1)
    assert run(REPORT, "--show", rid, "--root", main, cwd=main).out.startswith("build report (projected -> actual)")
    want = (main / ".superlite" / "runs" / rid / "progress.md").resolve()
    assert want in predict_live.ledger_paths(main)
    assert want in predict_live.ledger_paths(wt2)
