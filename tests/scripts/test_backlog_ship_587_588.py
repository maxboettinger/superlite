"""#587 (pushed branch merges, done only cleans up) and #588 (queue place, bare --wait, healthy waits) of sl backlog ship."""
import json, sys
import pytest
from test_backlog_ship import sh, ship, b1, locked, AG, B2  # noqa: F401
from test_backlog_ship_from_main import fm, go, setb, SHIPPED  # noqa: F401
from test_backlog_ship_done import dn  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import backlog_ship as bsh  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402

PUSHED = {"git rev-parse --abbrev-ref HEAD": (0, "superlite/b1\n"), "git branch -r --list origin/superlite/b1": (0, "  origin/superlite/b1\n"),
          "git symbolic-ref": (0, "origin/main\n")}


def pr(state="OPEN", merge="BEHIND", rollup=None, n=12):
    roll = [{"status": "IN_PROGRESS", "conclusion": ""}, {"status": "QUEUED", "conclusion": ""}] if rollup is None else rollup
    return (0, json.dumps({"number": n, "state": state, "mergeStateStatus": merge, "statusCheckRollup": roll}))


def test_pushed_branch_merges_not_rebases(sh, capsys):
    sh.replies = dict(PUSHED)
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and out == "B1 merged origin/main into superlite/b1 (on origin: no rebase)\nB1 lock held\n"
    i, j = sh.calls.index(["git", "merge", "--no-edit", "origin/superlite/b1"]), sh.calls.index(["git", "merge", "--no-edit", "origin/main"])
    assert i < j and not any(c[:2] == ["git", "rebase"] for c in sh.calls)


def test_unpushed_branch_still_rebases(sh, capsys):
    sh.replies = {"git rev-parse --abbrev-ref HEAD": (0, "superlite/b1\n"), "git branch -r --list": (0, ""), "git symbolic-ref": (0, "origin/main\n")}
    assert ship(capsys, "B1", "lock") == (0, "B1 lock held\n")
    assert ["git", "rebase", "origin/main"] in sh.calls and not any(c[:2] == ["git", "merge"] for c in sh.calls)


def test_merge_conflict_keeps_lock(sh, capsys):
    sh.replies = {"git merge --no-edit origin/main": (1, "CONFLICT"), "git diff --name-only --diff-filter=U": (0, "a.py\n"), **PUSHED}
    assert ship(capsys, "B1", "lock") == (5, "CONFLICT: a.py; lock held: resolve with fixers, git commit, then run lock again\n")
    assert ship_lock.holder(sh.lock)["batch"] == "B1" and ["git", "merge", "--abort"] not in sh.calls


def test_from_main_merge_conflict_aborts(fm, capsys):
    sh = fm
    sh.replies = {"git merge --no-edit origin/main": (1, "CONFLICT"), "git diff --name-only --diff-filter=U": (0, "a.py\n"), **PUSHED, "maxapp ship -C": (0, SHIPPED)}
    assert go(capsys) == (5, "CONFLICT: a.py; merge aborted; lock released, B1 parked: sl backlog start B1 resumes its lead to fix it\n")
    assert ["git", "merge", "--abort"] in sh.calls and ship_lock.holder(sh.lock) is None and b1(sh)["state"] == "parked"
    assert not any(c[:2] == ["git", "rebase"] for c in sh.calls)


def test_from_main_pushed_merge_succeeds(fm, capsys):
    sh = fm
    sh.replies.update(PUSHED)
    rc, out = go(capsys)
    assert rc == 0 and out.startswith("B1 merged origin/main into superlite/b1 (on origin: no rebase)\n")


def test_bare_wait_blocks_until_free(sh, capsys, monkeypatch):
    ship_lock.acquire(sh.lock, B2, None, 9_000); sh.live = {AG, "sl-x-w5"}
    slept = []
    def sleep(s):
        slept.append(s)
        if len(slept) == 50:
            ship_lock.release(sh.lock, "B2")
    monkeypatch.setattr(bsh, "_sleep", sleep)
    rc, out = ship(capsys, "B1", "lock", "--wait")
    assert rc == 0 and len(slept) == 50 and sum(slept) > 500 and out.endswith("B1 lock held\n")


def test_wait_line_names_queue_place(sh, capsys):
    ship_lock.acquire(sh.lock, B2, None, 9_000)
    b3 = {"batch": "B3", "lead": "W6", "agent": "sl-x-w6", "repo": "o/r"}
    sh.live = {AG, "sl-x-w5", "sl-x-w6"}
    assert ship(capsys, "B1", "lock", "--wait", "0") == (4, "WAIT: ship lock held by B2 (W5), queue place 1 of 1; run sl backlog ship B1 lock again\n")
    ship_lock.release(sh.lock, "B1")
    assert not ship_lock.acquire(sh.lock, b3, sh.live, 9_500)["acquired"]
    ship_lock.release(sh.lock, "B2")
    assert ship(capsys, "B1", "lock", "--wait", "0") == (4, "WAIT: ship lock free, B3 (W6) is first in the queue, queue place 2 of 2; run sl backlog ship B1 lock again\n")


def test_healthy_wait_not_counted(sh, capsys):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (4, "still running"), "gh pr view": pr()}
    rc, out = ship(capsys, "B1", "merge")
    assert (rc, out) == (4, "RERUN: sl backlog ship B1 merge (PR #12 BEHIND, 2 checks pending; healthy wait 1 of 30, not counted)\n")
    assert not b1(sh).get("ship_runs") and b1(sh)["ship_waits"] == 1
    assert any(c[:3] == ["gh", "pr", "view"] and "-R" in c and "number,state,mergeStateStatus,statusCheckRollup" in c for c in sh.calls)


def test_red_check_counts(sh, capsys):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (4, "x"), "gh pr view": pr(rollup=[{"status": "COMPLETED", "conclusion": "FAILURE"}])}
    assert ship(capsys, "B1", "merge") == (4, "RERUN: sl backlog ship B1 merge (run 1 of 5)\n")
    assert b1(sh)["ship_runs"] == 1 and not b1(sh).get("ship_waits")


@pytest.mark.parametrize("reply", [pr(merge="DIRTY"), pr(state="CLOSED"), (1, "boom"), (0, "not json")])
def test_dirty_or_unreadable_pr_counts(sh, capsys, reply):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (4, "x"), "gh pr view": reply}
    assert ship(capsys, "B1", "merge") == (4, "RERUN: sl backlog ship B1 merge (run 1 of 5)\n")
    assert b1(sh)["ship_runs"] == 1


def test_thirty_healthy_waits_then_counted(sh, capsys):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (4, "x"), "gh pr view": pr()}
    for k in range(1, 31):
        rc, out = ship(capsys, "B1", "merge")
        assert rc == 4 and f"healthy wait {k} of 30, not counted" in out
    assert ship(capsys, "B1", "merge") == (4, "RERUN: sl backlog ship B1 merge (run 1 of 5)\n")
    assert b1(sh)["ship_waits"] == 30 and b1(sh)["ship_runs"] == 1


def test_done_never_runs_maxapp(dn, capsys, monkeypatch):
    sh = dn
    seen = []
    monkeypatch.setattr(backlog_run, "_shipped", lambda p, sd, root, b, wt, push=True, head=None: seen.append((push, head, wt)) or ["B1 shipped"])
    sh.replies = {"gh pr view 262 -R o/r --json headRefOid": (0, "abc123\n"), "gh pr view": (0, "MERGED\n")}
    assert ship(capsys, "B1", "done", "--pr", "262") == (0, "B1 shipped\n")
    assert not any(c[:1] == ["maxapp"] for c in sh.calls)
    assert seen == [(False, "abc123", seen[0][2])]
