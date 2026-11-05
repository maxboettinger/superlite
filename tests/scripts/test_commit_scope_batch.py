"""commit_task: recorded --also files stay accepted, deleted files, docs.md of an owned folder."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (SCRIPTS, ENV, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

CP = {**ENV, "SUPERLITE_AUTOCOMMIT": "0"}  # checkpoint mode
RULING = "needed"
DOCS_PLAN = """# Docs plan

## 9. Implementation plan

### T1 · one · Complexity 3 · Est. context 20k · Est. time 1 min

**Owns:** `src/pkg/a.py`
**Produces:** none

### T2 · two · Complexity 3 · Est. context 20k · Est. time 1 min

**Owns:** `src/pkg/docs.md`
**Produces:** none
"""


def commit(repo, *args, env=CP):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=env)


def entries(repo):
    return json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))["entries"]


def setup(tmp_path, *extra):
    repo = make_repo(tmp_path)
    for rel in extra:
        write(repo, rel, "base\n")
    if extra:
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "more")
    return repo


def recorded(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "x.md", "x\n")
    r = commit(repo, "T1", "--also", "x.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    write(repo, "src/b.py", "B = 1\n")
    return repo


def test_also_file_stays_accepted(tmp_path):
    repo = recorded(tmp_path)
    r = commit(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout
    assert entries(repo)[-1]["files"] == ["src/b.py"]


def test_also_file_changed_again_commits_with_owner(tmp_path):
    repo = recorded(tmp_path)
    write(repo, "x.md", "changed again\n")
    r = commit(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "x.md" not in entries(repo)[-1]["files"]
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "x.md" in entries(repo)[-1]["files"]


def test_also_deleted_file_accepted(tmp_path):
    repo = setup(tmp_path, "x.md")
    write(repo, "src/a.py", "A = 1\n")
    (repo / "x.md").unlink()
    r = commit(repo, "T1", "--also", "x.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    write(repo, "src/b.py", "B = 1\n")
    r = commit(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout


def test_deleted_file_not_recorded_blocks(tmp_path):
    repo = setup(tmp_path, "x.md")
    write(repo, "src/b.py", "B = 1\n")
    (repo / "x.md").unlink()
    r = commit(repo, "T2")
    assert r.returncode == 1
    assert "out-of-scope x.md" in r.stdout


def test_also_several_files_one_flag(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "x.md", "x\n")
    write(repo, "y.md", "y\n")
    r = commit(repo, "T1", "--also", "x.md", "y.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    led = (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
    assert led.count("Ruling: T1 also commits") == 2


def test_also_repeated_flag_still_works(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "x.md", "x\n")
    write(repo, "y.md", "y\n")
    r = commit(repo, "T1", "--also", "x.md", "--also", "y.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert {"x.md", "y.md"} <= set(entries(repo)[-1]["files"])


def docs_repo(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "plan.md").write_text(DOCS_PLAN, encoding="utf-8")
    write(repo, "src/pkg/a.py", "A = 1\n")
    return repo


def test_folder_docs_md_joins_task(tmp_path):
    repo = docs_repo(tmp_path)
    for p in ("docs.md", "src/docs.md"):
        write(repo, p, "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert {"docs.md", "src/docs.md"} <= set(entries(repo)[-1]["files"])


def test_folder_docs_md_three_files_unowned(tmp_path):
    repo = docs_repo(tmp_path)
    (repo / "plan.md").write_text(DOCS_PLAN.replace("`src/pkg/docs.md`", "`src/pkg/other.py`").replace("`src/pkg/a.py`", "`src/pkg/a.py`"), encoding="utf-8")
    for p in ("docs.md", "src/docs.md", "src/pkg/docs.md"):
        write(repo, p, "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert {"docs.md", "src/docs.md", "src/pkg/docs.md"} <= set(entries(repo)[-1]["files"])


def test_also_flag_before_task_id(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "x.md", "x\n")
    r = commit(repo, "--also", "x.md", "T1", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "x.md" in entries(repo)[-1]["files"]


def test_also_directory_entry_recorded(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "fx/one.txt", "1\n")
    write(repo, "fx/two.txt", "2\n")
    r = commit(repo, "T1", "--also", "fx/", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    write(repo, "src/b.py", "B = 1\n")
    r = commit(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout


def test_tracked_tests_docs_md_takes_shared_test_path(tmp_path):
    repo = setup(tmp_path, "tests/docs.md")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "tests/docs.md", "changed\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "shared-test tests/docs.md" in r.stderr
    assert "tests/docs.md" in entries(repo)[-1]["files"]


def test_unowned_docs_folder_md_never_joins(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "docs/docs.md", "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "docs/docs.md" not in entries(repo)[-1]["files"]


def test_docs_md_joins_with_glob_owns(tmp_path):
    repo = make_repo(tmp_path)
    txt = (repo / "plan.md").read_text(encoding="utf-8")
    (repo / "plan.md").write_text(txt.replace("`src/a.py`", "`src/pkg/**/*.py`", 1), encoding="utf-8")
    write(repo, "src/pkg/a.py", "A = 1\n")
    write(repo, "src/pkg/docs.md", "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "src/pkg/docs.md" in entries(repo)[-1]["files"]


def test_other_folder_docs_md_blocks(tmp_path):
    repo = docs_repo(tmp_path)
    write(repo, "lib/docs.md", "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 1
    assert "out-of-scope lib/docs.md" in r.stdout


def test_docs_md_owned_by_other_left_alone(tmp_path):
    repo = docs_repo(tmp_path)
    write(repo, "src/pkg/docs.md", "d\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "src/pkg/docs.md" not in entries(repo)[-1]["files"]


def test_blocked_incident_resolved_by_later_commit(tmp_path):
    import finish
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray.py", "S = 1\n")
    r = commit(repo, "T1")
    assert r.returncode == 1
    log = repo / ".superlite" / "incidents.jsonl"
    assert [e["file"] for e in finish.open_incidents(log)] == ["stray.py"]
    r = commit(repo, "T1", "--also", "stray.py", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert finish.open_incidents(log) == []


def test_commit_mode_unchanged(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray.txt", "S\n")
    r = commit(repo, "T1", env=ENV)
    assert r.returncode == 1
    assert "out-of-scope stray.txt" in r.stdout


def kinds(log):
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_resolved_entry_only_for_blocked_no_duplicate(tmp_path):
    repo = setup(tmp_path)
    log = repo / ".superlite" / "incidents.jsonl"
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray.py", "S = 1\n")
    assert commit(repo, "T1").returncode == 1
    r = commit(repo, "T1", "--also", "stray.py", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    n = len([e for e in kinds(log) if e.get("file") == "stray.py"])
    write(repo, "src/b.py", "B = 1\n")
    assert commit(repo, "T2").returncode == 0
    assert len([e for e in kinds(log) if e.get("file") == "stray.py"]) == n
    assert not [e for e in kinds(log) if e.get("file") == "src/b.py"]


def test_failed_commit_writes_no_resolved_entry(tmp_path):
    repo = setup(tmp_path)
    log = repo / ".superlite" / "incidents.jsonl"
    write(repo, "src/a.py", "def broken(:\n")
    write(repo, "stray.py", "S = 1\n")
    assert commit(repo, "T1").returncode == 1
    r = commit(repo, "T1", "--also", "stray.py", "--ruling", RULING)
    assert r.returncode != 0
    assert [e for e in kinds(log) if e.get("resolution") == "resolved"] == []


def test_unhashable_existing_path_counts_as_changed(tmp_path, monkeypatch):
    import commit_task
    monkeypatch.chdir(tmp_path)
    (tmp_path / "u.md").write_text("u\n", encoding="utf-8")

    class R:
        stdout = ""

    monkeypatch.setattr(commit_task, "git", lambda *a, **k: R())  # ls-tree and hash-object both empty
    assert commit_task.changed_vs_parent(["u.md"]) == ["u.md"]


def test_also_counts_for_every_task_in_the_call(tmp_path):
    repo = setup(tmp_path)
    write(repo, "stray.txt", "s\n")  # blocks T1
    write(repo, "x.md", "x\n")
    write(repo, "src/b.py", "B = 1\n")
    r = commit(repo, "T1", "T2", "--also", "x.md", "--ruling", RULING)
    assert "out-of-scope x.md" not in r.stdout, r.stdout + r.stderr
    assert "T1 FAILED" in r.stdout
    assert "x.md" not in r.stdout.split("hint:")[-1]


def test_claimed_file_left_uncommitted(tmp_path):
    repo = setup(tmp_path)
    r = commit(repo, "T5", "--claim", "x.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "T5 claimed x.md" in r.stdout
    assert "Ruling: T5 also commits x.md - needed" in (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
    write(repo, "x.md", "x\n")
    write(repo, "src/main.py", "M = 1\n")
    r = commit(repo, "T6")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left uncommitted (claimed by T5): x.md" in r.stderr
    assert entries(repo)[-1]["files"] == ["src/main.py"]


def test_claim_without_ruling_exits_2(tmp_path):
    repo = setup(tmp_path)
    r = commit(repo, "T5", "--claim", "x.md")
    assert r.returncode == 2
    assert "--ruling" in r.stderr


def test_claim_accepts_task_id_after_files(tmp_path):
    repo = setup(tmp_path)
    r = commit(repo, "--claim", "x.md", "T5", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "T5 claimed x.md" in r.stdout


def test_claim_with_also_exits_2(tmp_path):
    repo = setup(tmp_path)
    r = commit(repo, "T5", "--claim", "x.md", "--also", "y.md", "--ruling", RULING)
    assert r.returncode == 2
    assert "cannot be combined" in r.stderr
