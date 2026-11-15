"""run_archive: where runs go (the main checkout's archive), how readers find them, the size rule."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import run_archive  # noqa: E402


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x")
    git(main, "add", "f")
    git(main, "commit", "-qm", "c")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    return main, wt


def test_archive_dir_of_a_worktree_is_main(repo):
    main, wt = repo
    want = (main / ".superlite" / "runs").resolve()
    assert run_archive.archive_dir(wt / ".superlite") == want
    assert run_archive.archive_dir(main / ".superlite") == want


def test_archive_dir_outside_git(tmp_path):
    sd = tmp_path / "x" / ".superlite"
    assert run_archive.archive_dir(sd) == sd / "runs"


def test_new_run_names_and_clash(repo, monkeypatch):
    main, wt = repo
    sd = wt / ".superlite"
    a = run_archive.new_run(sd, "B222")
    assert a.is_dir() and a.parent == (main / ".superlite" / "runs").resolve()
    assert re.fullmatch(r"\d{8}-\d{6}-B222", a.name)
    monkeypatch.setattr(time, "strftime", lambda *_a: "20261114-235958")
    b = run_archive.new_run(sd, "B222")
    c = run_archive.new_run(sd, "B222")
    assert b.name == "20261114-235958-B222" and c.name == "20261114-235958-B222-2"
    assert b.is_dir() and c.is_dir()
    assert run_archive.new_run(sd, "a b/c").name == "20261114-235958-a-b-c"
    assert run_archive.new_run(sd, "x" * 60).name == "20261114-235958-" + "x" * 40
    monkeypatch.undo()
    assert re.fullmatch(r"\d{8}-\d{6}", run_archive.new_run(sd).name)


def test_new_run_falls_back_when_archive_unwritable(tmp_path, monkeypatch):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        monkeypatch.setattr(run_archive, "archive_dir", lambda sd: ro / "sub" / "runs")
        sd = tmp_path / "wt" / ".superlite"
        r = run_archive.new_run(sd, "L")
        assert r.parent == sd / "runs" and r.is_dir()
    finally:
        ro.chmod(0o700)


def test_manifest_round_trip(tmp_path):
    run = tmp_path / "r"
    run.mkdir()
    p = run_archive.write_manifest(run, {"id": "x", "batch": None})
    assert p == run / "run.json"
    assert run_archive.read_manifest(run) == {"id": "x", "batch": None}
    p.write_text("{nope")
    assert run_archive.read_manifest(run) == {}
    p.write_text("[1]")
    assert run_archive.read_manifest(run) == {}
    p.unlink()
    assert run_archive.read_manifest(run) == {}


def test_runs_newest_first(tmp_path):
    arch = tmp_path / "runs"
    (arch / "20261101-120000").mkdir(parents=True)
    new = arch / "20261114-235958-B1"
    new.mkdir()
    run_archive.write_manifest(new, {"batch": "B1"})
    (arch / "stray.txt").write_text("x")
    got = run_archive.runs(arch)
    assert [r["id"] for r in got] == ["20261114-235958-B1", "20261101-120000"]
    assert got[0]["batch"] == "B1" and got[0]["dir"] == new
    assert set(got[1]) == {"id", "dir"}
    assert run_archive.runs(tmp_path / "missing") == []


def test_run_dirs_matches_checkout(repo, tmp_path):
    main, wt = repo
    arch = main / ".superlite" / "runs"
    mine = arch / "20261114-000000"
    other = arch / "20261114-000001"
    for d, w in ((mine, wt.resolve()), (other, tmp_path / "elsewhere")):
        d.mkdir(parents=True)
        run_archive.write_manifest(d, {"worktree": str(w)})
    legacy = wt / ".superlite" / "runs" / "20261101-120000"
    legacy.mkdir(parents=True)
    assert run_archive.run_dirs(wt / ".superlite") == [legacy, mine.resolve()]
    assert run_archive.run_dirs(tmp_path / "nowhere" / ".superlite") == []


def test_prune_keeps_ledgers(tmp_path):
    arch = tmp_path / "runs"
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me")
    names = ["20261101-000000", "20261102-000000", "20261103-000000"]
    for n in names:
        r = arch / n
        (r / "briefs").mkdir(parents=True)
        for f in ("run.json", "progress.md", "metrics.jsonl", "test-summary-1.json", "build-report.json", "plan.md"):
            (r / f).write_text("{}")
        (r / "briefs" / "x.md").write_text("b")
        (r / "lnk").symlink_to(outside)
    assert run_archive.prune(arch, keep=1) == 2
    new = arch / names[2]
    assert (new / "plan.md").exists() and (new / "briefs" / "x.md").exists() and (new / "lnk").is_symlink()
    for n in names[:2]:
        left = sorted(p.name for p in (arch / n).iterdir())
        assert left == ["build-report.json", "metrics.jsonl", "progress.md", "run.json", "test-summary-1.json"]
    assert outside.read_text() == "keep me"
    assert run_archive.prune(arch, keep=1) == 0


def test_trim_survives_a_vanished_run_folder(tmp_path):
    assert run_archive._trim(tmp_path / "gone") is False


def test_module_does_not_import_backlog_state(repo):
    src = (SCRIPTS / "run_archive.py").read_text()
    assert "backlog_state" not in src
    main, wt = repo
    assert run_archive.archive_dir(wt / ".superlite") == (main / ".superlite" / "runs").resolve()


def test_run_dirs_skips_other_worktrees_in_main_archive(repo):
    main, wt = repo
    arch = main / ".superlite" / "runs"
    mine, theirs, legacy = arch / "20261114-000000", arch / "20261114-000001", arch / "20261101-120000"
    for d, w in ((mine, main.resolve()), (theirs, wt.resolve())):
        d.mkdir(parents=True)
        run_archive.write_manifest(d, {"worktree": str(w)})
    legacy.mkdir()
    got = run_archive.run_dirs(main / ".superlite")
    assert [p.name for p in got] == [legacy.name, mine.name]


def test_every_code_line_has_complexity_comment():
    lines = (SCRIPTS / "run_archive.py").read_text().splitlines()
    start = lines.index("import json  # O(1)")
    bad = [(i, s) for i, s in enumerate(lines[start:], start + 1)
           if s.strip() and not s.strip().startswith("#") and "O(" not in s
           and not s.strip().startswith('"build-report')]
    assert bad == []
