"""#1097: commit_task holds a changed file in a busy package-reviewer's `Files in scope:` until the reviewer is done."""
import json
import sys

import pytest

from test_run_scripts import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# P

## 9. Implementation plan

### T1 · one · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`, `src/b.py`

### T2 · two · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/c.py`, `lib/`
"""
SHARED = "tests/registry/test_x.py"
NOTE = "left uncommitted (in the review scope of busy W7 (review-T1,T2); commit_task T1 again once it is done): "


@pytest.fixture
def run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/p.md", PLAN)
    for f in ("src/a.py", "src/b.py", "src/c.py", "lib/d.py"):
        write(repo, f, "X = 0\n")
    write(repo, SHARED, "def test_x():\n    assert 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: None)
    sd = repo / ".superlite"
    sd.mkdir(exist_ok=True)
    return repo, sd, str(repo / "docs/plans/p.md")


def add_worker(sd, wid, rec):
    p = sd / "fleet.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"on": True, "workers": {}}
    data["workers"][wid] = rec
    p.write_text(json.dumps(data), encoding="utf-8")


def reviewer(sd, scope, label="review-T1,T2", wid="W7", state="busy", stored=True):
    """A package-reviewer as fleet.for_review records it; its brief file name has commas as dashes."""
    brief = sd / "briefs" / (label.replace(",", "-") + ".md")
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(f"# Review: {label}\n\nCommits:\n- commit T1 abc1234\n"
                     + (f"Files in scope: {scope}\n" if scope is not None else "") + "\nIncident hotspots: none\n",
                     encoding="utf-8")
    add_worker(sd, wid, {"state": state, "role": "package-reviewer", "task": label,
                         **({"brief": str(brief)} if stored else {})})


def checkpoint_files(sd):
    return json.loads((sd / "checkpoints.json").read_text(encoding="utf-8"))["entries"][-1]["files"]


def test_review_scope_parses_the_line():
    assert commit_task.review_scope("# R\nFiles in scope: src/a.py, `lib/`, src/c.py\n") == ["src/a.py", "lib/", "src/c.py"]
    assert commit_task.review_scope("# R\nno scope here\n") is None
    assert commit_task.review_scope("Files in scope: \n") == []


def test_in_review_scope_matches_entries_or_names():
    t = "Files in scope: src/a.py, lib/\n"
    assert commit_task.in_review_scope("lib/d.py", t)
    assert commit_task.in_review_scope("src/a.py", t)
    assert not commit_task.in_review_scope("src/b.py", t + "Hotspots: src/b.py\n")
    assert commit_task.in_review_scope("src/b.py", "# hand-written brief naming src/b.py\n")
    assert not commit_task.in_review_scope("src/b.py", "Files in scope: \nsrc/b.py\n")


def test_busy_briefs_reads_stored_path_comma_label_and_roles(run):
    repo, sd, plan = run
    reviewer(sd, "src/a.py", stored=False)
    custom = sd / "briefs" / "custom.md"
    custom.write_text("Files in scope: src/b.py\n", encoding="utf-8")
    add_worker(sd, "W8", {"state": "busy", "role": "package-reviewer", "task": "review-x", "brief": str(custom)})
    (sd / "briefs" / "fix-F-1.md").write_text("- F-1 src/a.py:1\n", encoding="utf-8")
    add_worker(sd, "W3", {"state": "busy", "role": "fixer", "task": "fix-F-1"})
    got = commit_task.busy_briefs(str(sd), None, roles=("package-reviewer",))
    assert sorted(got) == ["W7", "W8"]
    assert got["W7"][0] == "review-T1,T2" and "Files in scope: src/a.py" in got["W7"][1]
    assert got["W8"] == ("review-x", "Files in scope: src/b.py\n")
    assert sorted(commit_task.busy_briefs(str(sd), None)) == ["W3", "W7", "W8"]


def test_scope_file_held_rest_commits(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/a.py, src/c.py")
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "src/b.py", "X = 2\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert NOTE + "src/a.py" in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/b.py"]


def test_only_scope_files_fail(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/a.py, src/c.py")
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 1
    assert "T1 FAILED: nothing to commit; held for busy W7: src/a.py" in capsys.readouterr().out


def test_directory_scope_entry_holds_file_under_it(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/c.py, lib/", label="review-T2")
    write(repo, "lib/d.py", "X = 1\n")
    write(repo, "src/c.py", "X = 1\n")
    assert commit_task.main(["T2", "--plan", plan]) == 1
    assert "T2 FAILED: nothing to commit; held for busy W7: lib/d.py, src/c.py" in capsys.readouterr().out


def test_multi_task_label_found_without_stored_path(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/a.py", stored=False)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "src/b.py", "X = 2\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert NOTE + "src/a.py" in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/b.py"]


def test_file_equal_to_checkpoint_not_held(run, capsys):
    repo, sd, plan = run
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    reviewer(sd, "src/a.py")
    write(repo, "src/b.py", "X = 2\n")
    capsys.readouterr()
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert "review scope" not in capsys.readouterr().err
    assert "src/b.py" in checkpoint_files(sd)


@pytest.mark.parametrize("state, me", [("idle", None), ("stopped", None), ("busy", "W7")])
def test_idle_reviewer_or_the_caller_holds_nothing(run, monkeypatch, capsys, state, me):
    repo, sd, plan = run
    reviewer(sd, "src/a.py", state=state)
    if me:
        monkeypatch.setenv("SUPERLITE_FLEET_WORKER", me)
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert "review scope" not in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/a.py"]


def test_fixer_scope_line_does_not_hold_a_source_file(run, capsys):
    repo, sd, plan = run
    (sd / "briefs").mkdir(exist_ok=True)
    (sd / "briefs" / "fix-F-1.md").write_text("Files in scope: src/a.py\n", encoding="utf-8")
    add_worker(sd, "W3", {"state": "busy", "role": "fixer", "task": "fix-F-1"})
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert checkpoint_files(sd) == ["src/a.py"]


def test_also_file_in_scope_is_held(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/c.py")
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "src/c.py", "X = 1\n")
    assert commit_task.main(["T1", "--also", "src/c.py", "--ruling", "r", "--plan", plan]) == 0
    assert NOTE + "src/c.py" in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/a.py"]


def test_two_reviewers_named(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/a.py", label="review-T1", wid="W7")
    reviewer(sd, "src/a.py", label="review-pkg", wid="W8")
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "src/b.py", "X = 2\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert ("left uncommitted (in the review scope of busy W7 (review-T1), W8 (review-pkg); "
            "commit_task T1 again once they are done): src/a.py") in capsys.readouterr().err
    assert checkpoint_files(sd) == ["src/b.py"]


def test_shared_test_under_scope_dir_held_without_shared_line(run, capsys):
    repo, sd, plan = run
    reviewer(sd, "src/a.py, tests/")
    write(repo, SHARED, "def test_x():\n    assert 2\n")
    write(repo, "src/b.py", "X = 2\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    err = capsys.readouterr().err
    assert NOTE + SHARED in err
    assert "shared-test" not in err
    assert checkpoint_files(sd) == ["src/b.py"]


def test_read_only_roles_hold_nothing(run, capsys):
    """A busy research worker and final reviewer read files, never edit them: their briefs hold no shared test."""
    repo, sd, plan = run
    for wid, role, label, name in (("W5", "research", "R1", "research-r1.md"), ("W6", "final-reviewer", "FR1", "review-packet.md")):
        brief = sd / name
        brief.write_text(f"# {label}\n\nChanged files:\n- {SHARED}\n", encoding="utf-8")
        add_worker(sd, wid, {"state": "busy", "role": role, "task": label, "brief": str(brief)})
    assert commit_task.busy_briefs(str(sd), None) == {}
    write(repo, SHARED, "def test_x():\n    assert 2\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    err = capsys.readouterr().err
    assert "shared-test" in err
    assert "left uncommitted" not in err
    assert checkpoint_files(sd) == [SHARED]
