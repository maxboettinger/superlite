"""#1134: lock refuses uncommitted work before it takes the lock; a sync that fails without a conflict stores no base tree."""
from test_backlog_ship import sh, ship, b1, AG  # noqa: F401
from test_backlog_ship_tree_639 import real, g  # noqa: F401
from test_backlog_ship_conflict_retry_1074_1075 import seq
import backlog_ship as bsh  # noqa: F401
import backlog_state as bs
import ship_lock

STATUS = ["git", "status", "--porcelain"]
OWNER = {"batch": "B1", "lead": "W1", "agent": AG, "repo": "o/r"}
BOOM = {"git rebase": (1, "fatal: boom"), "git diff --name-only --diff-filter=U": (0, "")}
BLOCKED = "BLOCKED: git rebase origin/main failed: fatal: boom; lock held: fix it, then run sl backlog ship B1 lock again\n"


def store(sh, tree):
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"sync_before_tree": tree}))


def test_dirty_first_lock_refused_then_clean_rerun_ships_tested_tree(real, capsys):
    (real.wt / "f.txt").write_text("changed\n")
    head = g(real.wt, "rev-parse", "HEAD")
    rc, out = ship(capsys, "B1", "lock")
    assert (rc, out) == (2, "refused: uncommitted changes in the worktree (f.txt): commit them first, then run sl backlog ship B1 lock again; lock not taken\n")
    assert ship_lock.holder(real.lock) is None and b1(real).get("sync_before_tree") is None
    assert g(real.wt, "rev-parse", "HEAD") == head
    g(real.wt, "commit", "-am", "work")
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and out.splitlines()[0] == "TREE: unchanged by the sync: the tested tree ships, no full rerun"


def test_untracked_file_refused(sh, capsys):
    sh.replies = {"git status --porcelain": (0, "?? new.txt\n")}
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 2 and "(new.txt)" in out and out.endswith("lock not taken\n")
    assert sh.calls == [STATUS] and ship_lock.holder(sh.lock) is None


def test_refusal_names_five_paths_and_the_rest(sh, capsys):
    sh.replies = {"git status --porcelain": (0, "".join(f" M {c}\n" for c in "abcdefg"))}
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 2 and "(a, b, c, d, e, +2 more)" in out


def test_dirty_while_holding_after_conflict_keeps_lock_and_tree(sh, capsys):
    ship_lock.acquire(sh.lock, OWNER, None, 9_000)
    store(sh, "t1")
    sh.replies = {"git status --porcelain": (0, "UU a.py\n")}
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 2 and out.endswith("; lock held\n")
    assert ship_lock.holder(sh.lock)["batch"] == "B1" and b1(sh)["sync_before_tree"] == "t1"
    assert not any(c[:2] == ["git", "fetch"] for c in sh.calls)


def test_failed_sync_without_conflict_blocks_and_stores_no_tree(sh, capsys, monkeypatch):
    seq(sh, monkeypatch, trees=["t1"])
    sh.replies = dict(BOOM)
    assert ship(capsys, "B1", "lock") == (3, BLOCKED)
    assert "sync_before_tree" not in b1(sh) and ship_lock.holder(sh.lock)["batch"] == "B1"


def test_failed_sync_keeps_a_stored_tree(sh, capsys, monkeypatch):
    store(sh, "t1")
    seq(sh, monkeypatch, trees=["t2"])
    sh.replies = dict(BOOM)
    assert ship(capsys, "B1", "lock") == (3, BLOCKED)
    assert b1(sh)["sync_before_tree"] == "t1"


def test_conflict_still_stores_the_tree(sh, capsys, monkeypatch):
    seq(sh, monkeypatch, trees=["t1"])
    sh.replies = {"git rebase": (1, "CONFLICT"), "git diff --name-only --diff-filter=U": (0, "a.py\n")}
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 5 and out.startswith("CONFLICT: a.py") and b1(sh)["sync_before_tree"] == "t1"
