"""orchestrator resume (#459): a checkpointed task's files are compared with its own checkpoint, the sha its
drop hint restores from, and each task with leftover edits gets the last test run that named its files."""
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

PLAN = """# Plan

**Goal:** g

### T1 one
**Owns:** src/a.py, tests/test_a.py
**Tests:** fast

### T2 two
**Owns:** src/b.py, tests/test_b.py
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


def age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def hms(path):
    return datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%H:%M:%S")


def repo(tmp_path):
    """T1 checkpointed at c1 (src/a.py a1, tests/test_a.py); T2 at c2 on top (src/b.py b1, tests/test_b.py and
    src/a.py a1b, claimed with --also); the chain head is c2 and the working tree holds c2's files."""
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
    put(root, "tests/test_a.py", "ta\n")
    git(root, "add", "src/a.py", "tests/test_a.py")
    git(root, "commit", "-qm", "T1: one")
    c1 = git(root, "rev-parse", "HEAD")
    put(root, "src/a.py", "a1b\n")
    put(root, "src/b.py", "b1\n")
    put(root, "tests/test_b.py", "tb\n")
    git(root, "add", "src/a.py", "src/b.py", "tests/test_b.py")
    git(root, "commit", "-qm", "T2: two")
    c2 = git(root, "rev-parse", "HEAD")
    git(root, "reset", "-q", base)
    plan = root / "docs" / "plans" / "p.md"
    sd = root / ".superlite"
    put(root, ".superlite/checkpoints.json", json.dumps({"plan": autocommit.plan_key(str(plan)), "base": base, "head": base,
        "entries": [{"task": "T1", "sha": c1, "title": "T1: one", "files": ["src/a.py", "tests/test_a.py"]},
                    {"task": "T2", "sha": c2, "title": "T2: two", "files": ["src/b.py", "tests/test_b.py", "src/a.py"]}]}))
    put(root, ".superlite/progress.md", f"- start {base}\n- commit T1 {c1[:10]} one\n- commit T2 {c2[:10]} two\n")
    return root, plan, sd, base, c1, c2


def head_line(plan, c2):
    return (f"resume: plan {plan}; checkpointed tasks compared with their own checkpoint, "
            f"the others with the chain head {c2[:7]} (T2)")


def test_checkpointed_task_compares_with_its_own_checkpoint(tmp_path):
    root, plan, sd, base, c1, c2 = repo(tmp_path)
    assert orchestrator.resume_lines(sd, plan) == [
        head_line(plan, c2),
        f"T1 checkpointed {c1[:7]}: edited after the checkpoint: src/a.py; keep: sl commit_task T1 --plan {plan}; "
        f"drop: git restore --source {c1[:7]} -- src/a.py",
        "T1 last test run: none covers its files",
        "checkpointed, nothing edited after: T2",
        "no changes: T3",
        f"last test run: none in {sd}",
    ]


def test_drop_hint_restores_what_the_report_compared(tmp_path):
    root, plan, sd, base, c1, c2 = repo(tmp_path)
    git(root, "restore", "--source", c1[:7], "--", "src/a.py")
    lines = orchestrator.resume_lines(sd, plan)
    assert not any(ln.startswith("T1 ") for ln in lines)
    assert "checkpointed, nothing edited after: T1" in lines
    assert lines[1] == (f"T2 checkpointed {c2[:7]}: edited after the checkpoint: src/a.py; keep: sl commit_task T2 --plan {plan}; "
                        f"drop: git restore --source {c2[:7]} -- src/a.py")


def test_ledger_shas_without_a_chain(tmp_path):
    root, plan, sd, base, c1, c2 = repo(tmp_path)
    (sd / "checkpoints.json").unlink()
    lines = orchestrator.resume_lines(sd, plan)
    assert lines[0] == (f"resume: plan {plan}; no checkpoint chain; checkpointed tasks compared with their own checkpoint, "
                        f"the others with HEAD {base[:7]}")
    assert lines[1] == (f"T1 checkpointed {c1[:7]}: edited after the checkpoint: src/a.py; keep: sl commit_task T1 --plan {plan}; "
                        f"drop: git restore --source {c1[:7]} -- src/a.py")


def test_gone_checkpoint_uses_head_for_both(tmp_path):
    root, plan, sd, base, c1, c2 = repo(tmp_path)
    gone = "deadbeef" * 5
    ck = json.loads((sd / "checkpoints.json").read_text(encoding="utf-8"))
    ck["entries"][0]["sha"] = gone
    (sd / "checkpoints.json").write_text(json.dumps(ck), encoding="utf-8")
    lines = orchestrator.resume_lines(sd, plan)
    assert lines[1] == (f"T1 checkpointed deadbee (gone; compared with HEAD {base[:7]}): edited after the checkpoint: "
                        f"src/a.py, tests/test_a.py; keep: sl commit_task T1 --plan {plan}; "
                        f"drop: git restore --source {base[:7]} -- src/a.py tests/test_a.py")
    assert orchestrator.compare_ref(root, gone) == base
    assert orchestrator.compare_ref(root, c1) == c1


def test_each_edited_task_gets_its_own_test_run(tmp_path):
    root, plan, sd, base, c1, c2 = repo(tmp_path)
    full = sd / "test-summary-20261110T100000-1-aaaaaa.json"
    full.write_text(json.dumps({"passed": 9, "failed": 1, "skipped": 0, "mode": "full",
                                "files": {"tests/test_a.py": [3, 1], "tests/test_b.py": [6, 0]}}), encoding="utf-8")
    age(full, 300)
    fast = sd / "test-summary.json"
    fast.write_text(json.dumps({"passed": 2, "failed": 0, "skipped": 0, "mode": "fast",
                                "files": {"tests/test_b.py": [2, 0]}}), encoding="utf-8")
    age(fast, 200)
    put(root, "src/b.py", "b2\n")
    age(root / "src" / "b.py", 500)
    put(root, "src/c.py", "c1\n")
    lines = orchestrator.resume_lines(sd, plan)
    assert lines == [
        head_line(plan, c2),
        f"T1 checkpointed {c1[:7]}: edited after the checkpoint: src/a.py; keep: sl commit_task T1 --plan {plan}; "
        f"drop: git restore --source {c1[:7]} -- src/a.py",
        f"T1 last test run: full, 3 passed, 1 failed in its files, ended {hms(full)}; edited after it: src/a.py",
        f"T2 checkpointed {c2[:7]}: edited after the checkpoint: src/b.py; keep: sl commit_task T2 --plan {plan}; "
        f"drop: git restore --source {c2[:7]} -- src/b.py",
        f"T2 last test run: fast, 2 passed, 0 failed in its files, ended {hms(fast)}; nothing edited after it",
        f"T3 not checkpointed: uncommitted Owns files: src/c.py; run its tests, then sl commit_task T3 --plan {plan}",
        "T3 last test run: none covers its files",
        f"last test run: fast, 2 passed, 0 failed, ended {hms(fast)}",
    ]


def test_task_test_run_picks_the_newest_summary_naming_the_files(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    old = sd / "test-summary-1.json"
    old.write_text(json.dumps({"mode": "full", "files": {"./tests/test_a.py": [3, 1], "tests/test_b.py": [6, 0]}}),
                   encoding="utf-8")
    age(old, 300)
    new = sd / "test-summary.json"
    new.write_text(json.dumps({"mode": "fast", "files": {"tests/test_b.py": [2, 0]}}), encoding="utf-8")
    age(new, 200)
    (sd / "test-summary-bad.json").write_text("{", encoding="utf-8")
    (sd / "test-summary-list.json").write_text("[]", encoding="utf-8")
    (sd / "test-summary-err.json").write_text(json.dumps({"mode": "full", "error": "boom", "files": {}}), encoding="utf-8")
    (sd / "test-summary-odd.json").write_text(json.dumps({"mode": "fast", "files": {"tests/test_a.py": "x"}}),
                                              encoding="utf-8")
    assert orchestrator.task_test_run(sd, ["src/a.py", "tests/test_a.py"]) == {
        "mode": "full", "passed": 3, "failed": 1, "ended": old.stat().st_mtime}
    assert orchestrator.task_test_run(sd, ["tests/test_b.py"]) == {
        "mode": "fast", "passed": 2, "failed": 0, "ended": new.stat().st_mtime}
    assert orchestrator.task_test_run(sd, ["src/c.py"]) is None
    assert orchestrator.task_test_run(tmp_path / "missing", ["tests/test_a.py"]) is None


def test_task_test_line(tmp_path):
    put(tmp_path, "a.py", "x\n")
    put(tmp_path, "b.py", "y\n")
    age(tmp_path / "b.py", 500)
    t = time.time() - 100
    stamp = datetime.fromtimestamp(t).strftime("%H:%M:%S")
    run = {"mode": "fast", "passed": 2, "failed": 0, "ended": t}
    assert orchestrator.task_test_line("T4", None, ["a.py"], tmp_path) == "T4 last test run: none covers its files"
    assert orchestrator.task_test_line("T4", run, ["a.py", "b.py", "gone.py"], tmp_path) == (
        f"T4 last test run: fast, 2 passed, 0 failed in its files, ended {stamp}; edited after it: a.py")
    assert orchestrator.task_test_line("T4", run, ["b.py"], tmp_path) == (
        f"T4 last test run: fast, 2 passed, 0 failed in its files, ended {stamp}; nothing edited after it")
