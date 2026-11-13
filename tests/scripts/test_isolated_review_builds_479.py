"""#479: a fleet worker's --fast run without --task (package reviewer, fixer) builds in its own tree."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts"
sys.path.insert(0, str(SCRIPTS))

import run_tests as rt  # noqa: E402
from test_plan_tools import make_plan  # noqa: E402
from test_run_tests_plan_fallback import OUT, RUN_TESTS, git  # noqa: E402

RED = "Executed 2 tests, with 1 failure (0 unexpected) in 0.1 (0.1) seconds"
FILES = ("src/a.py", "src/b.py", "src/c.py", "src/d.py")


def repo(tmp_path, out=OUT, code=0):
    for f in FILES:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("base", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\ncwd.txt\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    plan = make_plan(tmp_path / "docs", [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"},
                                         {"id": "T3", "owns": "src/c.py, src/d.py"}], name="p.md")
    sd = tmp_path / ".superlite"
    sd.mkdir()
    script = f"import os;open({str(tmp_path / 'cwd.txt')!r},'w').write(os.getcwd());print({out!r});raise SystemExit({code})"
    cmd = f"{sys.executable} -c \"{script}\""
    (sd / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "isolate": True}), encoding="utf-8")
    git(tmp_path, "init", "-q")
    with (tmp_path / ".git" / "info" / "exclude").open("a", encoding="utf-8") as fh:
        fh.write("_sl_home/\n")  # the test's superlite home is no project file
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    return plan


def go(tmp_path, plan, *args, **fleet):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_FLEET_") and k != "SUPERLITE_STATE_DIR"}
    env.update({f"SUPERLITE_FLEET_{k}": v for k, v in fleet.items()}, PYTHONIOENCODING="utf-8")
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--plan", str(plan), *args], capture_output=True, cwd=tmp_path, env=env, timeout=120)
    cp.err = cp.stderr.decode("utf-8")
    return cp


def w(tmp_path, wid="W3", agent="package-reviewer"):
    return {"WORKER": wid, "AGENT": agent}


def cwd(tmp_path):
    return Path((tmp_path / "cwd.txt").read_text(encoding="utf-8")).resolve()


def rewrite(tmp_path, *files):
    for f in files:
        (tmp_path / f).write_text("new", encoding="utf-8")


def read(tmp_path, wid, f):
    return (tmp_path / ".superlite/trees" / f"worker-{wid}" / f).read_text(encoding="utf-8")


def test_worker_tree_name():
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "W3", "SUPERLITE_FLEET_AGENT": "fixer-sonnet"}) == "worker-W3"
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "W9", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_FLEET_AGENT": "lead"}) is None
    assert rt.worker_tree_name({}) is None
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "../x", "SUPERLITE_FLEET_AGENT": "fixer-sonnet"}) is None
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "W4", "SUPERLITE_FLEET_AGENT": "package-reviewer"}) == "worker-W4"
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "W7", "SUPERLITE_FLEET_AGENT": "superlite:implementer"}) == "worker-W7"
    assert rt.worker_tree_name({"SUPERLITE_FLEET_WORKER": "W7", "SUPERLITE_FLEET_AGENT": "superlite:implementer-haiku"}) == "worker-W7"


def test_fleet_worker_fast_run_uses_its_own_tree(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path))
    assert cp.returncode == 0, cp.err
    assert "run_tests: tree .superlite/trees/worker-W3 = base + all working-tree changes (--fast)" in cp.err
    assert cwd(tmp_path) == (tmp_path / ".superlite/trees/worker-W3").resolve()


def test_reviewer_tree_holds_unfinished_task_files(tmp_path):
    plan = repo(tmp_path)
    (tmp_path / ".superlite/progress.md").write_text("- commit T2 5e9dd8b464 x\n", encoding="utf-8")
    rewrite(tmp_path, "src/a.py", "src/b.py")
    cp = go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path))
    assert cp.returncode == 0, cp.err
    assert read(tmp_path, "W3", "src/a.py") == "base"
    assert read(tmp_path, "W3", "src/b.py") == "new"
    assert "; kept at base: 1 file of unfinished T1" in cp.err


def fleet_setup(tmp_path, extra=""):
    sd = tmp_path / ".superlite"
    (sd / "progress.md").write_text("- commit T1 5e9dd8b464 x\n- commit T2 5e9dd8b464 x\n- commit T3 5e9dd8b464 x\n", encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"workers": {
        "W3": {"state": "busy", "role": "fixer", "task": "fix-T3a"},
        "W5": {"state": "busy", "role": "fixer", "task": "fix-T3b"},
        "W6": {"state": "idle", "role": "fixer", "task": "fix-T3c"}}}), encoding="utf-8")
    (sd / "briefs").mkdir()
    (sd / "briefs/fix-T3a.md").write_text("Fix src/d.py" + extra, encoding="utf-8")
    (sd / "briefs/fix-T3b.md").write_text("Fix src/c.py and src/a.py", encoding="utf-8")
    (sd / "briefs/fix-T3c.md").write_text("Fix src/b.py", encoding="utf-8")
    rewrite(tmp_path, *FILES)


def test_busy_fixer_brief_files_kept_at_base(tmp_path):
    plan = repo(tmp_path)
    fleet_setup(tmp_path)
    assert rt.busy_held(tmp_path / ".superlite", "W3", ["src/b.py", "src/c.py", "src/d.py"]) == {"src/c.py": ["W5"]}
    cp = go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path, agent="fixer-sonnet"))
    assert cp.returncode == 0, cp.err
    assert read(tmp_path, "W3", "src/c.py") == "base"
    assert read(tmp_path, "W3", "src/d.py") == "new"
    assert read(tmp_path, "W3", "src/b.py") == "new"
    assert "of busy W5" in cp.err
    (tmp_path / ".superlite/briefs/fix-T3a.md").write_text("Fix src/d.py and src/c.py", encoding="utf-8")
    cp = go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path, agent="fixer-sonnet"))
    assert read(tmp_path, "W3", "src/c.py") == "new"


def test_two_workers_get_separate_trees(tmp_path):
    plan = repo(tmp_path)
    go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path, "W3"))
    first = cwd(tmp_path)
    go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path, "W4"))
    assert (tmp_path / ".superlite/trees/worker-W3/.git").exists()
    assert (tmp_path / ".superlite/trees/worker-W4/.git").exists()
    assert cwd(tmp_path) != first


def test_lead_and_plain_runs_stay_in_root(tmp_path):
    plan = repo(tmp_path)
    for fleet in ({"WORKER": "W9", "ROLE": "lead", "AGENT": "lead"}, {}):
        cp = go(tmp_path, plan, "--fast", "src/b.py", **fleet)
        assert cp.returncode == 0, cp.err
        assert "run_tests: tree" not in cp.err
        assert cwd(tmp_path) == tmp_path.resolve()
        assert not (tmp_path / ".superlite/trees/worker-W9").exists()


def test_task_flag_keeps_task_tree(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--task", "T2", **w(tmp_path, agent="implementer"))
    assert ".superlite/trees/T2" in cp.err
    assert ".superlite/trees/worker-W3" not in cp.err


def test_full_run_by_worker_stays_in_root(tmp_path):
    plan = repo(tmp_path)
    go(tmp_path, plan, "--full", **w(tmp_path, agent="fixer-sonnet"))
    assert cwd(tmp_path) == tmp_path.resolve()
    assert not (tmp_path / ".superlite/trees/worker-W3").exists()


def test_red_worker_run_names_held_files(tmp_path):
    plan = repo(tmp_path, out=RED, code=1)
    rewrite(tmp_path, "src/a.py")
    cp = go(tmp_path, plan, "--fast", "src/b.py", **w(tmp_path))
    assert cp.returncode == 1, cp.err
    assert "1 changed file(s) not in worker-W3's tree: src/a.py; kept at base while their task or worker is busy" in cp.err
    assert "--also" not in cp.err


def test_fleet_doc_names_worker_tree():
    text = (Path(__file__).resolve().parents[2] / "docs/fleet.md").read_text(encoding="utf-8")
    assert ".superlite/trees/worker-Wn" in text
    assert "fixers may run at once" in text
    assert "one fixer at a time per run root" in text
    assert "fleet-off (Agent) workers test in the run root" in text
