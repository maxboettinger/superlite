"""batch_grade reads the runs a worktree archived in the main checkout (#843)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import batch_grade  # noqa: E402
from test_batch_grade_workers_682 import _transcript  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(cwd, *a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, env=ENV, check=True, capture_output=True)


def _repo(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "x")
    wts = []
    for n in ("wt", "wt2"):
        _git(main, "worktree", "add", "-q", str(tmp_path / n))
        wts.append((tmp_path / n).resolve())
    arch = main / ".superlite" / "runs"
    return main, wts, arch


def _run(arch, name, wt, summaries=(), metrics=None):
    r = arch / name
    r.mkdir(parents=True)
    (r / "run.json").write_text(json.dumps({"worktree": str(wt)}), encoding="utf-8")
    for i, (mode, sec) in enumerate(summaries):
        (r / f"test-summary-2026111{i}T100000-{i}-a.json").write_text(json.dumps({"mode": mode, "seconds": sec}), encoding="utf-8")
    if metrics:
        (r / "metrics.jsonl").write_text(metrics, encoding="utf-8")


def test_test_runs_reads_main_archive(tmp_path):
    main, (wt, wt2), arch = _repo(tmp_path)
    _run(arch, "20261112-101500", wt, [("full", 120), ("fast", 30)])
    _run(arch, "20261113-101500", wt2, [("full", 60)])
    (wt / ".superlite").mkdir()
    assert batch_grade.test_runs(wt / ".superlite") == {"full": 1, "full_min": 2.0, "fast": 1, "fast_min": 0.5}


def test_workers_reads_main_archive(tmp_path):
    main, (wt, wt2), arch = _repo(tmp_path)
    sd = wt / ".superlite"
    sd.mkdir()
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"role": "implementer"}}}), encoding="utf-8")
    t1, t2 = tmp_path / "w1.jsonl", tmp_path / "w2.jsonl"
    _transcript(t1, "m1")
    _transcript(t2, "m2")

    def text(t, w):
        return "".join(json.dumps(x) + "\n" for x in [
            {"ev": "launch", "t": 1, "agent_id": w, "type": "fleet:superlite:implementer"},
            {"ev": "stop", "t": 2, "agent_id": w, "type": "fleet:superlite:implementer", "transcript": str(t)}])
    _run(arch, "20261112-101500", wt, metrics=text(t1, "W1"))
    _run(arch, "20261113-101500", wt2, metrics=text(t2, "W1"))
    w = batch_grade.workers(sd)
    assert w["implementer"]["tokens"]["cache_read"] == 1000 and w["implementer"]["n"] == 1


def test_missing_worktree_folder_empty(tmp_path):
    main, (wt, wt2), arch = _repo(tmp_path)
    _run(arch, "20261112-101500", wt, [("full", 120)])
    got = batch_grade.test_runs(main / ".superlite" / "backlog" / "missing-worktree")
    assert got == {"full": 0, "full_min": 0.0, "fast": 0, "fast_min": 0.0}
