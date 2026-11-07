import sys, types
import pytest
from test_backlog_ship import sh, ship, b1, AG  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402


@pytest.fixture
def dn(sh, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_ROLE", raising=False)
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    sh.stops = []
    monkeypatch.setitem(sys.modules, "fleet", types.SimpleNamespace(stop=lambda sd, ids: sh.stops.append(("stop", ids))))
    def run(cmd, cwd, timeout=None):
        sh.calls.append(cmd); return (0, "")
    monkeypatch.setattr(backlog_run, "_run", run)
    return sh


def setb(sh, **kw):
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update(kw))


def test_done_records_a_hand_shipped_batch(dn, capsys):
    sh = dn
    setb(sh, state="parked", reason="merge denied", version="1.5.20")
    ship_lock.acquire(sh.lock, {"batch": "B1", "lead": "W1", "agent": AG, "repo": "o/r"}, None, 9_000)
    sh.replies = {"gh pr view": (0, "MERGED\n")}
    assert ship(capsys, "B1", "done", "--pr", "262") == (0, f"B1 shipped PR #262 1.5.20 summary={sh.sd / 'backlog' / 'B1.md'}\n")
    r = b1(sh)
    assert (r["state"], r["pr"], r["merged"], r["version"], r["open_issues"]) == ("shipped", 262, True, "1.5.20", [])
    assert ship_lock.holder(sh.lock) is None
    assert ("stop", ["W1"]) in sh.stops
    assert any(c[:3] == ["maxapp", "ship", "-C"] for c in sh.calls)
    assert (sh.sd / "backlog" / "B1.md").is_file()


def test_done_is_main_only_and_needs_a_merged_pr(dn, capsys, monkeypatch):
    sh = dn
    def check(expect):
        out = ship(capsys, *expect[0])
        if isinstance(expect[1], tuple):
            assert out == expect[1]
        else:
            assert out[0] == 3 and out[1].startswith("BLOCKED: cannot read PR #262")
        assert b1(sh)["merged"] is False or not b1(sh).get("merged")
        assert sh.stops == []
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    check((("B1", "done", "--pr", "262"), (2, "refused: sl backlog ship B1 done runs only in the main session\n")))
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER")
    check((("B1", "done"), (2, "refused: done needs --pr N\n")))
    sh.replies = {"gh pr view": (0, "OPEN\n")}
    check((("B1", "done", "--pr", "262"), (2, "refused: PR #262 is OPEN, not merged\n")))
    sh.replies = {"gh pr view": (1, "no such PR")}
    check((("B1", "done", "--pr", "262"), None))
    setb(sh, state="planned")
    check((("B1", "done", "--pr", "262"), (2, "refused: B1 is planned, not running or parked\n")))


def test_done_takes_the_version_flag_and_names_open_issues(dn, capsys):
    sh = dn
    sh.replies = {"gh pr view": (0, "MERGED\n"), "gh issue view": (0, "OPEN\n")}
    rc, out = ship(capsys, "B1", "done", "--pr", "262", "--version", "1.6.0")
    assert rc == 0
    assert f"B1 shipped PR #262 1.6.0 summary={sh.sd / 'backlog' / 'B1.md'}" in out.splitlines()
    assert "B1 OPEN #5" in out.splitlines()
    r = b1(sh)
    assert r["version"] == "1.6.0" and r["open_issues"] == [5]
