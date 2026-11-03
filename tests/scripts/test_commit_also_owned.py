"""commit_task: --also files stay owned by their task; several tasks; also_owned parsing."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_scope_batch import RULING, commit, entries, recorded, setup  # noqa: E402
from test_run_scripts import SCRIPTS, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402


def test_also_file_changed_again_commits_with_owner(tmp_path):
    repo = recorded(tmp_path)
    write(repo, "x.md", "again\n")
    assert commit(repo, "T2").returncode == 0
    assert "x.md" not in entries(repo)[-1]["files"]
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "x.md" in entries(repo)[-1]["files"]


def test_also_owned_by_other_task_not_out_of_scope(tmp_path):
    repo = recorded(tmp_path)
    write(repo, "x.md", "again\n")
    r = commit(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout


def test_also_multi_task_goes_to_first(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "x.md", "x\n")
    r = commit(repo, "T1", "T2", "--also", "x.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Ruling: T1 also commits x.md" in (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
    t1 = [e for e in entries(repo) if e["task"] == "T1"][-1]
    assert "x.md" in t1["files"]


def test_also_owned_parses_ledger(tmp_path):
    led = tmp_path / "progress.md"
    led.write_text("- Ruling: T1 also commits x.md - needed\n- Ruling: T2 also commits lib/ - shared\n- other\n", encoding="utf-8")
    assert commit_task.also_owned(str(led)) == {"x.md": "T1", "lib/": "T2"}
    assert commit_task.also_owned(str(tmp_path / "missing.md")) == {}


def test_also_dir_entry_keeps_prefix(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "lib/a.py", "1\n")
    assert commit(repo, "T1", "--also", "lib/", "--ruling", RULING).returncode == 0
    write(repo, "lib/b.py", "2\n")
    write(repo, "src/b.py", "B = 1\n")
    assert commit(repo, "T2").returncode == 0
    assert "lib/b.py" not in entries(repo)[-1]["files"]
    assert commit(repo, "T1").returncode == 0
    assert "lib/b.py" in entries(repo)[-1]["files"]


def test_ruling_for_unknown_task_ignored(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    led = repo / ".superlite" / "progress.md"
    led.parent.mkdir(exist_ok=True)
    led.write_text("- Ruling: T99 also commits src/a.py - x\n", encoding="utf-8")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr


def test_also_owned_accepts_bold_and_dash_in_ruling(tmp_path):
    led = tmp_path / "progress.md"
    led.write_text("- **Ruling:** T1 also commits a.md - x\n**Ruling:** T2 also commits b/ - why - more\n", encoding="utf-8")
    assert commit_task.also_owned(str(led)) == {"a.md": "T1", "b/": "T2"}
