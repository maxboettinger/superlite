import sys, types
import pytest
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
import ship_lock


@pytest.fixture
def sk(bk, monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    ns = types.SimpleNamespace(stops=[], rels=[], stop_exc=None, bk=bk)
    def stop(sd, ids=None, **kw):
        if ns.stop_exc:
            raise ns.stop_exc
        ns.stops.append((sd, ids))
    monkeypatch.setitem(sys.modules, "fleet", types.SimpleNamespace(stop=stop))
    monkeypatch.setitem(sys.modules, "ship_lock", types.SimpleNamespace(lock_path=ship_lock.lock_path, release=lambda p, b: ns.rels.append((p, b))))
    return ns


def park(sk, issues):
    def up(d):
        d["repo"] = "o/r"
        d["batches"] = [{"id": "B2", "state": "parked", "issues": issues, "files": [], "depends": [], "decisions": [], "worktree": "/w/b2", "lead": "W4"}]
    bs.update(bs.path(sk.bk.root), up)


def test_skip_parked_cli(sk, capsys):
    park(sk, [2, 5])
    assert cli(capsys, "skip", "2") == (0, "skipped #2 (B2 keeps #5)\n")
    assert sk.stops == [] and sk.rels == []


def test_skip_parked_last_stops_lead(sk, capsys):
    park(sk, [5])
    assert cli(capsys, "skip", "5") == (0, "skipped #5 (B2 dropped; its worktree /w/b2 stays)\nB2 lead W4 stopped\n")
    assert sk.stops == [(sk.bk.root / ".superlite", ["W4"])]
    assert sk.rels == [(ship_lock.lock_path("o/r"), "B2")]


def test_skip_stop_failure_swallowed(sk, capsys):
    park(sk, [5])
    sk.stop_exc = SystemExit(1)
    assert cli(capsys, "skip", "5") == (0, "skipped #5 (B2 dropped; its worktree /w/b2 stays)\n")


def test_skip_running_refused_cli(sk, capsys):
    def up(d):
        d["batches"] = [{"id": "B1", "state": "running", "issues": [1], "files": [], "depends": [], "decisions": []}]
    bs.update(bs.path(sk.bk.root), up)
    assert cli(capsys, "skip", "1") == (2, "refused: #1 is in B1, which is running\n")
