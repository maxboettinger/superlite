"""#596: commit_task takes **Also-touches:** files and owned symlinks' targets; --claim names its next step; `### T1: Title` titles."""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_scope_batch import RULING, commit, entries  # noqa: E402
from test_run_scripts import SCRIPTS, git, make_repo, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402
import next_tasks as nt  # noqa: E402

PLAN = """# Plan

### T1: enum payload · Complexity 2 · Est. context 20k

**Owns:** `src/a.py`, `src/link.py`
**Also-touches:** `src/b.py`

### T2 · user of the enum · Complexity 2 · Est. context 20k

**Owns:** `src/b.py`

### T3 — dashed · Complexity 1 · Est. context 20k

**Owns:** `src/c.py`
"""


def repo_with(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "plan.md", PLAN)
    write(repo, "src/a.py", "A = 0\n")
    write(repo, "src/b.py", "B = 0\n")
    write(repo, "lib/real.py", "R = 0\n")
    try:
        os.symlink("../lib/real.py", repo / "src" / "link.py")
    except OSError:
        pytest.skip("no symlinks here")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def owns_after(repo, monkeypatch):
    monkeypatch.chdir(repo)
    info = nt.parse_plan(str(repo / "plan.md"))
    commit_task.add_also_owns(info, str(repo / ".superlite" / "progress.md"))
    return info


def test_add_also_owns_adds_plan_field_and_link_targets(tmp_path, monkeypatch):
    info = owns_after(repo_with(tmp_path), monkeypatch)
    assert info["T1"]["owns"] == ["src/a.py", "src/link.py", "src/b.py", "lib/real.py"]
    assert info["T2"]["owns"] == ["src/b.py"]


def test_link_outside_the_repo_adds_nothing(tmp_path, monkeypatch):
    repo = repo_with(tmp_path)
    (tmp_path / "outside.py").write_text("O = 0\n", encoding="utf-8")
    os.remove(repo / "src" / "link.py")
    os.symlink(str(tmp_path / "outside.py"), repo / "src" / "link.py")
    assert owns_after(repo, monkeypatch)["T1"]["owns"] == ["src/a.py", "src/link.py", "src/b.py"]


def test_also_touches_file_commits_with_its_task(tmp_path):
    repo = repo_with(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(entries(repo)[-1]["files"]) == ["src/a.py", "src/b.py"]
    assert git(repo, "log", "-1", "--format=%s", r.stdout.strip().splitlines()[-1]) == "T1: enum payload"


def test_owned_symlink_target_commits_with_its_task(tmp_path):
    repo = repo_with(tmp_path)
    (repo / "src" / "link.py").write_text("R = 1\n", encoding="utf-8")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert entries(repo)[-1]["files"] == ["lib/real.py"]
    assert "outside every Owns" not in r.stderr and "out-of-scope" not in r.stdout


def test_claim_names_its_next_step(tmp_path):
    repo = repo_with(tmp_path)
    r = commit(repo, "T2", "--claim", "src/a.py", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[-2:] == [
        "T2 claimed src/a.py", "next: commit_task T2 --plan plan.md (a claim commits nothing; it records the ruling)"]


def test_claim_with_several_tasks_names_also(tmp_path):
    repo = repo_with(tmp_path)
    r = commit(repo, "T1", "T2", "--claim", "x.md", "--ruling", RULING)
    assert r.returncode == 2
    assert ("error: --claim takes one task and commits nothing; to commit x.md with T1 and commit T2 in one call: "
            "commit_task T1 T2 --also x.md --ruling TEXT") in r.stderr


def test_heading_separators_leave_the_title(tmp_path):
    info = nt.parse_plan(str(repo_with(tmp_path) / "plan.md"))
    assert [info[t]["title"] for t in ("T1", "T2", "T3")] == ["enum payload", "user of the enum", "dashed"]


def test_link_target_in_a_dot_dot_prefixed_folder_is_owned(tmp_path, monkeypatch):
    repo = repo_with(tmp_path)
    write(repo, "..hid/real.py", "H = 0\n")
    os.remove(repo / "src" / "link.py")
    os.symlink("../..hid/real.py", repo / "src" / "link.py")
    assert owns_after(repo, monkeypatch)["T1"]["owns"] == ["src/a.py", "src/link.py", "src/b.py", "..hid/real.py"]
