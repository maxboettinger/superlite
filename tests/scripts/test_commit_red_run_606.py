"""#606: commit_task names a task whose report shows no red run."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import SCRIPTS, commit, git, make_repo, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# Plan

### T1 · config · Complexity 2 · Est. context 20k

**Owns:** `src/a.py`, `tests/test_a.py`
"""
NOTE = "T1: no red run (its report names no red run); its review must prove each new test can fail"


def repo_with(base, red=None):
    base.mkdir()
    repo = make_repo(base)
    write(repo, "plan.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "tests/test_a.py", "def test_a():\n    assert True\n")
    if red is not None:
        write(repo, ".superlite/fleet/reports/T1.json",
              json.dumps({"status": "DONE", "label": "T1", "role": "implementer", "red": red}))
    return repo


def test_commit_names_a_missing_red_run(tmp_path):
    r = commit(repo_with(tmp_path / "gap", red=""), "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert NOTE in r.stderr.splitlines()


def test_commit_with_a_red_run_or_no_report_is_quiet(tmp_path):
    for name, red in (("red", "tests (fast): 0 passed, 1 failed"), ("none", None)):
        r = commit(repo_with(tmp_path / name, red=red), "T1")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "no red run" not in r.stderr


def test_red_note_values(tmp_path):
    sd = tmp_path / ".superlite"
    assert commit_task.red_note(str(sd), "T1", ["src/a.py"]) is None
    d = sd / "fleet" / "reports"
    d.mkdir(parents=True)
    (d / "T1.json").write_text(json.dumps({"label": "T1", "role": "implementer", "red": "none - no test"}), encoding="utf-8")
    assert commit_task.red_note(str(sd), "T1", ["src/a.py"]) is None
    assert commit_task.red_note(str(sd), "T1", ["tests/test_a.py"]) == (
        "T1: no red run (its report says `none - no test`, but it owns test files (tests/test_a.py)); "
        "its review must prove each new test can fail")


def test_red_note_survives_a_failing_lookup(tmp_path, monkeypatch):
    import fleet_io
    sd = tmp_path / ".superlite"
    (sd / "fleet" / "reports").mkdir(parents=True)

    def boom(*a):
        raise RuntimeError("boom")

    monkeypatch.setattr(fleet_io, "red_gap", boom)
    assert commit_task.red_note(str(sd), "T1", ["tests/test_a.py"]) is None
