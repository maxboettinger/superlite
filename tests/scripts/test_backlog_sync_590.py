import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_backlog_cli import bk, cli  # noqa: F401  bk is the CLI fixture
from test_backlog_plan_proposal_297 import write
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import backlog_state as bs  # noqa: E402

BATCH = {"id": "B1", "topic": "t", "issues": [1, 2], "files": ["a.py"], "depends": [], "decisions": []}
TAIL = "; triage reads the local files"


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def commit(cwd, name, text="x"):
    (Path(cwd) / name).write_text(text)
    git(cwd, "add", name)
    git(cwd, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", name)


@pytest.fixture
def repos(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    o = tmp_path / "o.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(o)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(o), str(seed)], check=True, capture_output=True)
    git(seed, "checkout", "-q", "-b", "main")
    commit(seed, "a.txt", "a")
    git(seed, "push", "-q", "origin", "main")
    root, other = tmp_path / "root", tmp_path / "other"
    for d in (root, other):
        subprocess.run(["git", "clone", "-q", str(o), str(d)], check=True, capture_output=True)
    for d in (root, other):
        git(d, "config", "user.name", "t")
        git(d, "config", "user.email", "t@t")

    def push(n):
        for i in range(n):
            commit(other, f"n{i}.txt", str(i))
        git(other, "push", "-q", "origin", "main")
    return type("R", (), {"root": root, "other": other, "o": o, "tmp": tmp_path, "push": staticmethod(push)})


def test_behind_and_clean_fast_forwards(repos):
    repos.push(2)
    out = backlog_run.sync_main(repos.root)
    assert len(out) == 1 and re.match(r"^sync: main checkout fast-forwarded [0-9a-f]{7}\.\.[0-9a-f]{7} to origin/main \(2 new\)$", out[0])
    assert git(repos.root, "rev-parse", "HEAD") == git(repos.root, "rev-parse", "origin/main")


def test_up_to_date_prints_nothing(repos):
    head = git(repos.root, "rev-parse", "HEAD")
    assert backlog_run.sync_main(repos.root) == [] and git(repos.root, "rev-parse", "HEAD") == head


def test_dirty_tracked_file_is_left_alone(repos):
    repos.push(1)
    head = git(repos.root, "rev-parse", "HEAD")
    (repos.root / "a.txt").write_text("edited")
    assert backlog_run.sync_main(repos.root) == ["sync: main checkout is 1 behind origin/main and has uncommitted changes; not fast-forwarded" + TAIL]
    assert git(repos.root, "rev-parse", "HEAD") == head and (repos.root / "a.txt").read_text() == "edited"


def test_untracked_file_does_not_block(repos):
    repos.push(1)
    (repos.root / "new.txt").write_text("u")
    out = backlog_run.sync_main(repos.root)
    assert len(out) == 1 and out[0].endswith("to origin/main (1 new)") and (repos.root / "new.txt").exists()


def test_other_branch_and_detached_head(repos):
    repos.push(1)
    head = git(repos.root, "rev-parse", "HEAD")
    git(repos.root, "switch", "-q", "-c", "feature")
    assert backlog_run.sync_main(repos.root) == ["sync: main checkout is on feature, not main; not fast-forwarded" + TAIL]
    git(repos.root, "checkout", "-q", "--detach")
    assert backlog_run.sync_main(repos.root) == ["sync: main checkout is on a detached HEAD, not main; not fast-forwarded" + TAIL]
    assert git(repos.root, "rev-parse", "HEAD") == head


def test_diverged_checkout(repos):
    repos.push(1)
    commit(repos.root, "l1.txt")
    commit(repos.root, "l2.txt")
    head = git(repos.root, "rev-parse", "HEAD")
    assert backlog_run.sync_main(repos.root) == ["sync: main checkout is 1 behind and 2 ahead of origin/main; not fast-forwarded" + TAIL]
    assert git(repos.root, "rev-parse", "HEAD") == head


def test_fetch_failure(repos):
    git(repos.root, "remote", "set-url", "origin", str(repos.tmp / "gone.git"))
    out = backlog_run.sync_main(repos.root)
    assert len(out) == 1 and out[0].startswith("sync: git fetch origin main failed (") and out[0].endswith(")" + TAIL)


def test_no_origin_is_silent(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    subprocess.run(["git", "init", "-q", str(tmp_path / "r")], check=True)
    commit(tmp_path / "r", "a.txt")
    assert backlog_run.sync_main(tmp_path / "r") == []


def test_origin_head_unset(repos):
    git(repos.root, "remote", "set-head", "origin", "-d")
    assert backlog_run.sync_main(repos.root) == ["sync: origin/HEAD is not set; not fast-forwarded (git remote set-head origin --auto sets it)"]


def test_fleet_worker_is_silent(repos, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W3")
    repos.push(1)
    head = git(repos.root, "rev-parse", "HEAD")
    assert backlog_run.sync_main(repos.root) == [] and git(repos.root, "rev-parse", "HEAD") == head


def test_ship_lock_holder_blocks(repos, monkeypatch):
    import ship_lock
    monkeypatch.setattr(ship_lock, "holder", lambda p: {"batch": "B7"})
    monkeypatch.setattr(ship_lock, "lock_path", lambda repo, home=None: repos.tmp / "x.lock")
    repos.push(1)
    head = git(repos.root, "rev-parse", "HEAD")
    assert backlog_run.sync_main(repos.root, "o/r") == ["sync: B7 holds the ship lock; not fast-forwarded (its merge fast-forwards the checkout)"]
    assert git(repos.root, "rev-parse", "HEAD") == head
    out = backlog_run.sync_main(repos.root, "")
    assert len(out) == 1 and "fast-forwarded" in out[0]


def test_plan_prints_sync_lines_before_its_output(bk, capsys, monkeypatch):
    monkeypatch.setattr(backlog_run, "sync_main", lambda root, repo="": ["sync: X"])
    f = write(bk, {"batches": [BATCH]})
    rc, out = cli(capsys, "plan", "--proposal", f)
    assert rc == 0 and out.splitlines()[0] == "sync: X"
    rc, out = cli(capsys, "plan", "--proposal", f)
    assert rc == 2 and "sync:" not in out


def test_ship_lock_error_never_raises(repos, monkeypatch):
    import ship_lock

    def boom(p):
        raise OSError("lock dir unwritable")
    monkeypatch.setattr(ship_lock, "holder", boom)
    repos.push(1)
    out = backlog_run.sync_main(repos.root, "o/r")
    assert len(out) == 1 and out[0].startswith("sync: ")


def test_undecodable_git_output_never_raises(repos, monkeypatch):
    def boom(*a, **k):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    monkeypatch.setattr(backlog_run.subprocess, "run", boom)
    assert backlog_run.sync_main(repos.root, "o/r") == []
