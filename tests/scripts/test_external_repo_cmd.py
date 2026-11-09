"""plan_tools external (#332): the tree, test, commit and done steps of an external repository task."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from test_plan_tools import PLAN_TOOLS, run
from test_stable_split import DISPATCH

CHECK = '''import os, sys
fleet = sorted(k for k in os.environ if k.startswith("SUPERLITE_FLEET_"))
print("fleet:", fleet)
print("cwd:", os.getcwd())
sys.exit(int(os.environ.get("CHECK_EXIT", "0")) or (3 if fleet else 0))
'''
PY = shlex.quote(sys.executable)


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *map(str, args)], capture_output=True, text=True,
                          check=True).stdout.strip()


def shared_repo(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "src").mkdir()
    (root / "src" / "helper.py").write_text("X = 1\n", encoding="utf-8")
    (root / "check.py").write_text(CHECK, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def plan_file(tmp_path, root, test=f"{PY} check.py", ship="maxapp ship -C {tree}"):
    plans = tmp_path / "proj" / "docs" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    p = plans / "2026-11-09-shared-fix.md"
    p.write_text(
        "# Plan\n**Goal:** test.\n**Wave0:** none\n\n```mermaid\nflowchart LR\n  T1[a]\n  T2[b]\n  %% taskgraph\n"
        "  T1 --> T2\n```\n\n"
        f"### T1 shared helper · Est. time 2 min\n**Owns:** src/helper.py, tests/test_helper.py\n**Repo:** {root}\n"
        f"**Repo test:** `{test}`\n**Repo ship:** `{ship}`\n\n"
        "### T2 local · Est. time 2 min\n**Owns:** src/app.py\n\n", encoding="utf-8")
    return p


def ext(p, tid, *args, **env):
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", **env}
    return subprocess.run([sys.executable, str(PLAN_TOOLS), "external", tid, "--plan", str(p), *map(str, args)],
                          capture_output=True, text=True, env=e, timeout=120)


def tree_of(cp):
    return Path(cp.stdout.splitlines()[1][len("tree: "):])


def test_prepare_makes_tree_and_prints_lines(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    cp = ext(p, "T1")
    assert cp.returncode == 0, cp.stderr
    lines = cp.stdout.splitlines()
    tree = tree_of(cp)
    assert lines[0] == f"root: {root.resolve()}"
    assert tree.resolve() == (tmp_path / "proj" / ".superlite" / "repos" / "T1").resolve()
    assert lines[2] == "branch: superlite/shared-fix-t1"
    assert lines[3] == f"test: {PY} check.py"
    assert lines[4] == f"ship: maxapp ship -C {tree}"
    assert git(tree, "rev-parse", "--abbrev-ref", "HEAD") == "superlite/shared-fix-t1"
    assert (tree / "src" / "helper.py").read_text(encoding="utf-8") == "X = 1\n"
    rec = json.loads((tree.parent / "T1.json").read_text(encoding="utf-8"))
    assert rec["base"] == git(root, "rev-parse", "HEAD") and rec["branch"] == "superlite/shared-fix-t1"
    again = ext(p, "T1")
    assert again.returncode == 0 and again.stdout == cp.stdout


def test_test_pass_and_fleet_env_stripped(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    cp = ext(p, "T1", "--test", SUPERLITE_FLEET_ROLE="lead", SUPERLITE_FLEET_WORKER="W3")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    out = cp.stdout.splitlines()
    assert out[-1] == "external T1 test: PASS"
    assert "fleet: []" in out
    assert any(ln.startswith("cwd: ") and ln.endswith(os.path.join(".superlite", "repos", "T1")) for ln in out)


def test_test_fail_exit_code(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    cp = ext(p, "T1", "--test", CHECK_EXIT="5")
    assert cp.returncode == 1
    assert cp.stdout.splitlines()[-1] == "external T1 test: FAIL (exit 5)"


def test_test_timeout(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path), test=f"{PY} -c 'import time; time.sleep(3)'")
    cp = ext(p, "T1", "--test", "--timeout", "0.5")
    assert cp.returncode == 1
    assert cp.stdout.splitlines()[-1] == "external T1 test: FAIL (timeout after 0.5s)"


def test_commit_owned_files_only(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "helper.py").write_text("X = 2\n", encoding="utf-8")
    (tree / "tests").mkdir()
    (tree / "tests" / "test_helper.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (tree / "notes.txt").write_text("scratch\n", encoding="utf-8")
    cp = ext(p, "T1", "--commit")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    sha = git(tree, "rev-parse", "HEAD")
    out = cp.stdout.splitlines()
    assert out[0] == f"T1 {sha[:10]}"
    assert out[1] == f"ship: maxapp ship -C {tree}"
    assert out[2] == f"then: plan_tools external T1 --plan {p} --done"
    assert "left uncommitted (outside Owns): notes.txt" in cp.stderr
    assert git(tree, "show", "--name-only", "--format=%s", "HEAD").splitlines() == [
        "shared helper (T1)", "", "src/helper.py", "tests/test_helper.py"]
    assert git(tree, "status", "--porcelain") == "?? notes.txt"
    assert json.loads((tree.parent / "T1.json").read_text(encoding="utf-8"))["sha"] == sha


def test_commit_nothing_and_no_tree(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    cp = ext(p, "T1", "--commit")
    assert cp.returncode == 2 and "T1: no tree at" in cp.stderr and "run plan_tools external T1 --plan" in cp.stderr
    assert ext(p, "T1").returncode == 0
    cp = ext(p, "T1", "--commit")
    assert cp.returncode == 1 and "nothing to commit for T1" in cp.stderr


def test_done_records_once_and_releases_pool(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "helper.py").write_text("X = 2\n", encoding="utf-8")
    assert ext(p, "T1", "--commit").returncode == 0
    sha = git(tree, "rev-parse", "HEAD")
    led, pool = tmp_path / "progress.md", tmp_path / "pool.json"
    pool.write_text(json.dumps({"agents": [{"id": "W1", "busy": True, "current": "T1", "tasks": []}]}), encoding="utf-8")
    cp = ext(p, "T1", "--done", "--ledger", led, "--pool", pool)
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout.splitlines()[0] == f"T1 {sha[:10]} recorded"
    assert led.read_text(encoding="utf-8").splitlines()[-1] == f"- commit T1 {sha[:10]} shared helper (repo {root.resolve()})"
    ag = json.loads(pool.read_text(encoding="utf-8"))["agents"][0]
    assert ag["busy"] is False and "current" not in ag and ag["tasks"] == ["T1"]
    again = ext(p, "T1", "--done", "--ledger", led, "--pool", pool)
    assert again.returncode == 0 and again.stdout.strip() == "T1: already recorded"
    assert led.read_text(encoding="utf-8").count("- commit T1 ") == 1
    d = run(DISPATCH, "--plan", p, "--pool", tmp_path / "pool2.json", "--ledger", led, cwd=p.parent)
    assert "T2" in {t for ln in d.out.splitlines() if ln.strip() for t in ln.split()[0].split(",")}, d.out + d.err


def test_done_needs_a_commit_and_a_known_sha(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    led, pool = tmp_path / "progress.md", tmp_path / "pool.json"
    cp = ext(p, "T1", "--done", "--ledger", led, "--pool", pool)
    assert cp.returncode == 2 and "T1: no commit recorded; run --commit first or pass --sha" in cp.stderr
    cp = ext(p, "T1", "--done", "--sha", "deadbeef", "--ledger", led, "--pool", pool)
    assert cp.returncode == 2 and "T1: commit deadbeef not found in" in cp.stderr
    head = git(root, "rev-parse", "HEAD")
    cp = ext(p, "T1", "--done", "--sha", head, "--ledger", led, "--pool", pool)
    assert cp.returncode == 0 and f"- commit T1 {head[:10]} " in led.read_text(encoding="utf-8")


def test_local_and_unknown_task_refused(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    cp = ext(p, "T2")
    assert cp.returncode == 2 and "T2 is not an external repo task (no **Repo:** line); use commit_task" in cp.stderr
    cp = ext(p, "T9")
    assert cp.returncode == 2 and "unknown task T9" in cp.stderr


def test_reuses_branch_after_tree_removed(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "helper.py").write_text("X = 3\n", encoding="utf-8")
    assert ext(p, "T1", "--commit").returncode == 0
    sha = git(tree, "rev-parse", "HEAD")
    git(root, "worktree", "remove", "--force", tree)
    cp = ext(p, "T1")
    assert cp.returncode == 0, cp.stderr
    assert git(tree, "rev-parse", "HEAD") == sha


def test_stale_folder_refused(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    tree = tmp_path / "proj" / ".superlite" / "repos" / "T1"
    tree.mkdir(parents=True)
    (tree / "x").write_text("", encoding="utf-8")
    cp = ext(p, "T1")
    assert cp.returncode == 2 and "exists but is no worktree; remove it" in cp.stderr
