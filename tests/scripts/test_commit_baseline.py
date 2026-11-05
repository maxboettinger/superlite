"""commit_task: an out-of-scope file is labelled by the stable.json baseline_dirty list."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import ENV, make_repo, run, write  # noqa: E402


def setup(tmp_path, stable, dirty):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    for f in dirty:
        write(repo, f, "x\n")
    sl = repo / ".superlite"
    sl.mkdir(exist_ok=True)
    if stable is not None:
        (sl / "stable.json").write_text(stable if isinstance(stable, str) else json.dumps(stable), encoding="utf-8")
    return repo


def commit(repo):
    return run("commit_task", "T1", "--plan", "plan.md", cwd=repo, env=ENV)


def test_baseline_file_labelled_dirty_before(tmp_path):
    repo = setup(tmp_path, {"baseline_dirty": ["notes.txt"]}, ["notes.txt"])
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope notes.txt (dirty before the run)" in r.stdout
    assert "dirty before the run" in (repo / ".superlite" / "incidents.jsonl").read_text(encoding="utf-8")


def test_new_foreign_file_labelled_during_run(tmp_path):
    repo = setup(tmp_path, {"baseline_dirty": ["notes.txt"]}, ["other.py"])
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope other.py (changed during the run, not by a task)" in r.stdout


def test_no_baseline_key_keeps_plain_line(tmp_path):
    repo = setup(tmp_path, {"other": 1}, ["other.py"])
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope other.py\n" in r.stdout


@pytest.mark.parametrize("stable", [None, "{"])
def test_missing_or_broken_stable_json_keeps_plain_line(tmp_path, stable):
    repo = setup(tmp_path, stable, ["other.py"])
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope other.py\n" in r.stdout
    assert "Traceback" not in r.stderr


def test_empty_baseline_list_labels_foreign_file_during_run(tmp_path):
    repo = setup(tmp_path, {"baseline_dirty": []}, ["other.py"])
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope other.py (changed during the run, not by a task)" in r.stdout
