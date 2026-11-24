"""#1074: a lock rerun after a resolved CONFLICT compares the tree before the first sync; #1075: merge retries a transient GitHub error once."""
import os
import subprocess
import pytest
from test_backlog_ship import sh, ship, b1, locked  # noqa: F401
from test_backlog_ship_tree_639 import real, g, put  # noqa: F401
import backlog_ship as bsh
import backlog_state as bs

GQL = "gh pr merge 201 failed: GraphQL: Something went wrong while executing your query. (mergePullRequest)"
RETRY = "maxapp ship hit a transient GitHub error; retried once after 15 s"


def seq(sh, monkeypatch, trees=(), ships=()):
    """Wrap the sh fixture's _run: HEAD^{tree} answers pop from trees, maxapp ship answers pop from ships."""
    base, trees, ships = bsh._run, list(trees), list(ships)
    sleeps = []

    def run(cmd, cwd, timeout=None):
        if cmd[:2] == ["git", "rev-parse"] and cmd[-1] == "HEAD^{tree}" and trees:
            sh.calls.append(cmd)
            return 0, trees.pop(0)
        if cmd[:2] == ["maxapp", "ship"] and ships:
            sh.calls.append(cmd)
            return ships.pop(0)
        return base(cmd, cwd, timeout)
    monkeypatch.setattr(bsh, "_run", run)
    monkeypatch.setattr(bsh, "_sleep", sleeps.append)
    return sleeps


def test_transient():
    assert bsh.transient(GQL)
    assert bsh.transient("HTTP 502: Bad Gateway (https://api.github.com/graphql)")
    assert bsh.transient("was submitted too quickly")
    assert bsh.transient("Service Unavailable")
    assert not bsh.transient("gh pr merge 201 failed: Pull request is not mergeable")
    assert not bsh.transient("")


def test_transient_ignores_a_bare_timeout():
    assert not bsh.transient("gh pr merge 201 failed: context deadline exceeded (timeout)")
    assert bsh.transient("504 Gateway Timeout")


def test_conflict_rerun_names_the_rebased_tree(real, capsys):
    put(real.seed, "f.txt", "origin\n")
    g(real.seed, "push", "origin", "main")
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 5 and out.startswith("CONFLICT: f.txt")
    (real.wt / "f.txt").write_text("both\n")
    g(real.wt, "add", "f.txt")
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "rebase", "--continue"], cwd=str(real.wt), check=True, capture_output=True, env={**env, "GIT_EDITOR": "true"})
    rc, out = ship(capsys, "B1", "lock")
    first = out.splitlines()[0]
    assert rc == 0 and first.startswith("TREE: changed by the sync (") and first.endswith("run the full suite once (sl run_tests --full) before bump")
    assert b1(real).get("sync_before_tree") is None


def test_second_conflict_keeps_the_first_tree(sh, capsys, monkeypatch):
    seq(sh, monkeypatch, trees=["t1", "t2"])
    sh.replies = {"git rebase": (1, "CONFLICT"), "git diff --name-only --diff-filter=U": (0, "a.py\n")}
    assert ship(capsys, "B1", "lock")[0] == 5 and b1(sh)["sync_before_tree"] == "t1"
    assert ship(capsys, "B1", "lock")[0] == 5 and b1(sh)["sync_before_tree"] == "t1"


def test_clean_rerun_uses_and_clears_the_stored_tree(sh, capsys, monkeypatch):
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"sync_before_tree": "t1"}))
    seen = []
    monkeypatch.setattr(bsh, "tree_line", lambda wt, before: seen.append(before))
    seq(sh, monkeypatch, trees=["t2"])
    assert ship(capsys, "B1", "lock")[0] == 0
    assert seen == ["t1"] and b1(sh).get("sync_before_tree") is None


def test_release_clears_the_stored_tree(sh, capsys):
    locked(sh, capsys)
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"sync_before_tree": "t1"}))
    assert ship(capsys, "B1", "release")[0] == 0
    assert b1(sh).get("sync_before_tree") is None


def merge(sh, capsys, monkeypatch, ships):
    locked(sh, capsys)
    sleeps = seq(sh, monkeypatch, ships=ships)
    body = sh.wt / "b.md"
    body.write_text("Batch B1.\n")
    rc, out = ship(capsys, "B1", "merge", "--title", "B1: leads", "--body-file", str(body))
    return rc, out, sleeps, len([c for c in sh.calls if c[:2] == ["maxapp", "ship"]])


def test_merge_retries_a_graphql_error_once(sh, capsys, monkeypatch):
    rc, out, sleeps, n = merge(sh, capsys, monkeypatch, [(1, GQL), (0, "merged #201 as abc\n")])
    assert rc == 0 and RETRY in out and "B1 shipped PR #201" in out and sleeps == [15] and n == 2
    assert out.splitlines()[0] == RETRY


def test_merge_blocks_after_a_second_transient_error(sh, capsys, monkeypatch):
    rc, out, sleeps, n = merge(sh, capsys, monkeypatch, [(1, GQL), (1, GQL)])
    lines = out.splitlines()
    assert rc == 3 and lines[0] == RETRY and lines[-1].startswith("BLOCKED: maxapp ship failed (") and lines[-1].endswith("); lock held") and n == 2


def test_merge_never_retries_a_real_refusal(sh, capsys, monkeypatch):
    rc, out, sleeps, n = merge(sh, capsys, monkeypatch, [(1, "gh pr merge 201 failed: Pull request is not mergeable")])
    assert rc == 3 and n == 1 and sleeps == [] and RETRY not in out


@pytest.mark.parametrize("code", [3, 4])
def test_merge_never_retries_red_or_timeout(sh, capsys, monkeypatch, code):
    rc, out, sleeps, n = merge(sh, capsys, monkeypatch, [(code, "Something went wrong")])
    assert n == 1 and sleeps == [] and RETRY not in out and rc in (4, 6, 3)
    if code == 3:
        assert rc == 6 and out.startswith("RED:")
