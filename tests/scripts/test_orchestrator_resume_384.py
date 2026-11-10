"""orchestrator resume (#384): per task, what a dead coordinator left behind (checkpoint, edits after it,
uncommitted Owns files), the last test run, and a pool cleared of agents that no longer exist."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402
import orchestrator  # noqa: E402
import pool  # noqa: E402

PLAN = """# Plan

**Goal:** g

### T1 one
**Owns:** src/a.py, tests/test_a.py
**Tests:** fast

### T2 two
**Owns:** src/b.py
**Tests:** fast

### T3 three
**Owns:** src/c.py
**Tests:** fast
"""


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def put(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def repo(tmp_path, edit_after=True):
    """A checkout with a T1 checkpoint (src/a.py, tests/test_a.py), src/a.py edited after it when edit_after,
    and src/b.py (T2) changed without a checkpoint; the test summary is older than those edits."""
    root = tmp_path / "r"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    put(root, "docs/plans/p.md", PLAN)
    put(root, "src/a.py", "a0\n")
    put(root, "src/b.py", "b0\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD")
    put(root, "src/a.py", "a1\n")
    put(root, "tests/test_a.py", "t1\n")
    git(root, "add", "src/a.py", "tests/test_a.py")
    git(root, "commit", "-qm", "T1: one")
    c1 = git(root, "rev-parse", "HEAD")
    git(root, "reset", "-q", base)
    plan = root / "docs" / "plans" / "p.md"
    sd = root / ".superlite"
    put(root, ".superlite/checkpoints.json", json.dumps({"plan": autocommit.plan_key(str(plan)), "base": base, "head": base,
        "entries": [{"task": "T1", "sha": c1, "title": "T1: one", "files": ["src/a.py", "tests/test_a.py"]}]}))
    put(root, ".superlite/progress.md", f"- start {base}\n- commit T1 {c1[:10]} one\n")
    put(root, ".superlite/test-summary.json", json.dumps({"passed": 5, "failed": 0, "skipped": 0, "seconds": 1.0, "mode": "fast"}))
    old = time.time() - 100
    os.utime(sd / "test-summary.json", (old, old))
    if edit_after:
        put(root, "src/a.py", "a2\n")
    put(root, "src/b.py", "b1\n")
    return root, plan, sd, c1


def ended(sd):
    return datetime.fromtimestamp((sd / "test-summary.json").stat().st_mtime).strftime("%H:%M:%S")


def clean_env(monkeypatch, tmp_path):
    for k in [k for k in os.environ if k.startswith("SUPERLITE_")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")


def test_resume_lines_name_each_task_state(tmp_path):
    root, plan, sd, c1 = repo(tmp_path)
    assert orchestrator.resume_lines(sd, plan) == [
        f"resume: plan {plan}; checkpointed tasks compared with their own checkpoint, the others with the chain head {c1[:7]} (T1)",
        f"T1 checkpointed {c1[:7]}: edited after the checkpoint: src/a.py; keep: sl commit_task T1 --plan {plan}; "
        f"drop: git restore --source {c1[:7]} -- src/a.py",
        "T1 last test run: none covers its files",
        f"T2 not checkpointed: uncommitted Owns files: src/b.py; run its tests, then sl commit_task T2 --plan {plan}",
        "T2 last test run: none covers its files",
        "no changes: T3",
        f"last test run: fast, 5 passed, 0 failed, ended {ended(sd)}",
    ]


def test_clean_checkpoint_is_listed_once(tmp_path):
    root, plan, sd, c1 = repo(tmp_path, edit_after=False)
    lines = orchestrator.resume_lines(sd, plan)
    assert lines[3:5] == ["checkpointed, nothing edited after: T1", "no changes: T3"]
    assert not any(ln.startswith("T1 ") for ln in lines)
    assert lines[-1] == f"last test run: fast, 5 passed, 0 failed, ended {ended(sd)}"


def test_without_checkpoints_compares_with_head(tmp_path):
    root, plan, sd, c1 = repo(tmp_path)
    (sd / "checkpoints.json").unlink()
    (sd / "progress.md").write_text("", encoding="utf-8")
    head = git(root, "rev-parse", "HEAD")
    lines = orchestrator.resume_lines(sd, plan)
    assert lines[0] == f"resume: plan {plan}; no checkpoints; files compared with HEAD {head[:7]}"
    assert lines[1] == (f"T1 not checkpointed: uncommitted Owns files: src/a.py, tests/test_a.py; run its tests, "
                        f"then sl commit_task T1 --plan {plan}")


def test_checkpoints_of_another_plan_are_ignored(tmp_path):
    root, plan, sd, c1 = repo(tmp_path)
    st = json.loads((sd / "checkpoints.json").read_text(encoding="utf-8"))
    st["plan"] = str(root / "docs" / "plans" / "old.md")
    (sd / "checkpoints.json").write_text(json.dumps(st), encoding="utf-8")
    head = git(root, "rev-parse", "HEAD")
    assert orchestrator.resume_lines(sd, plan)[0] == (
        f"resume: plan {plan}; no checkpoint chain; checkpointed tasks compared with their own checkpoint, "
        f"the others with HEAD {head[:7]}")


def test_changed_since_compares_blobs(tmp_path):
    root, plan, sd, c1 = repo(tmp_path)
    files = ["src/a.py", "tests/test_a.py", "src/b.py", "src/c.py", "src"]
    assert orchestrator.changed_since(root, c1, files) == ["src/a.py", "src/b.py"]
    assert orchestrator.changed_since(root, "HEAD", files) == ["src/a.py", "src/b.py", "tests/test_a.py"]
    assert orchestrator.changed_since(root, c1, []) == []
    (root / "src" / "b.py").unlink()
    assert orchestrator.changed_since(root, "HEAD", ["src/b.py"]) == ["src/b.py"]


def test_plan_file_lookup_order(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    put(tmp_path, "docs/p.md", PLAN)
    plan = tmp_path / "docs" / "p.md"
    other = tmp_path / "other.md"
    other.write_text(PLAN, encoding="utf-8")
    assert orchestrator.plan_file(sd) is None
    (sd / "plan.md").write_text(PLAN, encoding="utf-8")
    assert orchestrator.plan_file(sd) == sd / "plan.md"
    (sd / "pool.json").write_text(json.dumps({"plan": str(other), "agents": []}), encoding="utf-8")
    assert orchestrator.plan_file(sd) == other
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan)}), encoding="utf-8")
    assert orchestrator.plan_file(sd) == plan
    assert orchestrator.plan_file(sd, str(other)) == other
    assert orchestrator.plan_file(sd, str(sd)) == plan
    (sd / "stable.json").write_text(json.dumps({"plan": str(tmp_path / "gone.md")}), encoding="utf-8")
    assert orchestrator.plan_file(sd) == other


def test_test_run_line(tmp_path):
    sd = tmp_path / ".superlite"
    assert orchestrator.test_run_line(sd) == f"last test run: none in {sd}"
    sd.mkdir()
    (sd / "test-summary.json").write_text(json.dumps({"passed": 0, "failed": 1, "skipped": 0, "mode": "full",
                                                      "error": "pytest could not start"}), encoding="utf-8")
    assert orchestrator.test_run_line(sd) == (f"last test run: full, 0 passed, 1 failed, ended {ended(sd)}, "
                                              "error: pytest could not start")
    (sd / "test-summary.json").write_text("{", encoding="utf-8")
    assert orchestrator.test_run_line(sd) == f"last test run: unreadable {sd / 'test-summary.json'}"


def test_cli_resume_prunes_first(tmp_path, monkeypatch, capsys):
    root, plan, sd, c1 = repo(tmp_path)
    clean_env(monkeypatch, tmp_path)
    seen = []
    monkeypatch.setattr(pool, "prune_file", lambda p: seen.append(p) or ["removed a1 (gone)", "pool: removed 1 of 1 agent"],
                        raising=False)
    assert orchestrator.main(["resume", "--plan", str(plan)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert seen == [str(sd / "pool.json")]
    assert out[:2] == ["removed a1 (gone)", "pool: removed 1 of 1 agent"]
    assert out[2:] == orchestrator.resume_lines(sd, plan)


import pytest  # noqa: E402


@pytest.mark.parametrize("exc,reason", [
    (SystemExit("pool.json unreadable (x): boom"), "pool.json unreadable (x): boom"),
    (AttributeError("bad"), "AttributeError: bad"),
])
def test_cli_resume_survives_a_failing_prune(tmp_path, monkeypatch, capsys, exc, reason):
    root, plan, sd, c1 = repo(tmp_path)
    clean_env(monkeypatch, tmp_path)

    def boom(path):
        raise exc

    monkeypatch.setattr(pool, "prune_file", boom, raising=False)
    assert orchestrator.main(["resume", "--plan", str(plan)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"pool: not pruned: {reason}"
    assert out[1:] == orchestrator.resume_lines(sd, plan)


def test_cli_resume_leaves_another_live_sessions_pool(tmp_path, monkeypatch, capsys):
    root, plan, sd, c1 = repo(tmp_path)
    clean_env(monkeypatch, tmp_path)
    home = tmp_path / "home"
    (sd / "session").write_text("other\n", encoding="utf-8")
    (home / "sessions").mkdir(parents=True)
    (home / "sessions" / "other").write_text(f"{sd}\n", encoding="utf-8")

    def boom(p):
        raise AssertionError("pruned another session's pool")

    monkeypatch.setattr(pool, "prune_file", boom, raising=False)
    assert orchestrator.main(["resume", "--plan", str(plan)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == (f"pool: not pruned: {sd} belongs to session other; "
                      f"take the run over first: sl orchestrator takeover --plan {sd}")
    assert out[1] == (f"resume: plan {plan}; checkpointed tasks compared with their own checkpoint, "
                      f"the others with the chain head {c1[:7]} (T1)")


def test_cli_resume_without_a_plan(tmp_path, monkeypatch, capsys):
    clean_env(monkeypatch, tmp_path)
    sd = tmp_path / ".superlite"
    sd.mkdir()
    monkeypatch.setattr(pool, "prune_file", lambda p: ["pool: no pool.json in x"], raising=False)
    assert orchestrator.main(["resume", "--plan", str(sd)]) == 2
    assert capsys.readouterr().out.splitlines() == ["pool: no pool.json in x",
                                                    f"resume: no plan found for {sd}; pass --plan <plan.md>"]


def test_cli_resume_outside_git(tmp_path, monkeypatch, capsys):
    clean_env(monkeypatch, tmp_path)
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "plan.md").write_text(PLAN, encoding="utf-8")
    monkeypatch.setattr(pool, "prune_file", lambda p: ["pool: no pool.json in x"], raising=False)
    assert orchestrator.main(["resume", "--plan", str(sd)]) == 2
    assert capsys.readouterr().out.splitlines()[-1] == f"resume: {sd} is in no git checkout"


def test_changed_since_unknown_ref_falls_back_to_head(tmp_path):
    root, plan, sd, c1 = repo(tmp_path)
    git(root, "add", "src/b.py")
    git(root, "commit", "-qm", "b")
    gone = "deadbeef" * 5
    assert orchestrator.changed_since(root, gone, ["src/b.py", "src/a.py"]) == ["src/a.py"]
