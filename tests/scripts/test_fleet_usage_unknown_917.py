"""#917: an account whose usage cannot be read is unknown, not out of headroom: it takes its last good reading while that
of any age, else the coordinator's own account goes ahead; BLOCKED only when every account is known full."""
import json
import time

import pytest
from test_fleet import world  # noqa: F401
from test_accounts import acc
import fleet

REAL_READ_USAGE = fleet.ac.read_usage  # the world fixture replaces it; these tests run the real fallback
ERR = "not signed in with a Claude subscription (run {} auth login)"
DIRS = {"claude1": "/u/.claude-account1", "claude3": "/u/.claude-account3"}


def unreadable(name, n):
    a = acc(name, n)
    a["error"], a["limits"] = ERR.format(name), []
    return a


@pytest.fixture
def usage(world, monkeypatch):
    """Serve `report` through the real read_usage; the coordinator runs on claude3 unless a test says otherwise."""
    box = {"report": {"accounts": []}}
    monkeypatch.setattr(fleet.ac, "_run", lambda sub, env: box["report"])
    monkeypatch.setattr(fleet.ac, "read_usage", REAL_READ_USAGE)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", DIRS["claude3"])
    fleet.main(["on", "--accounts", "claude1,claude3"])
    return box


def remember(name, minutes_ago, **limits):
    f = fleet.ac._store()
    f.parent.mkdir(parents=True, exist_ok=True)
    last = json.loads(f.read_text()) if f.exists() else {}
    stored = acc(name, int(name[-1]), **limits)
    for x in stored["limits"]:
        x["resets_at"] = "2999-01-01T00:00:00+00:00"  # a limit whose window has not reset yet
    last[name] = {"at": time.time() - minutes_ago * 60, "account": stored}
    f.write_text(json.dumps(last))


def test_every_usage_unreadable_starts_on_the_coordinators_account(world, usage, capsys):
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    w = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert w["account"] == "claude3" and any(c[0] == "start_agent" for c in world.fh.calls)
    cap = capsys.readouterr()
    assert "BLOCKED" not in cap.out
    assert f"claude3: usage unreadable ({ERR.format('claude3')}), no stored reading; usable as the coordinator's own account" in cap.err.splitlines()


def test_a_recent_reading_stands_in_and_ranks_before_the_unknown_account(world, usage, capsys):
    remember("claude1", 10, weekly_all=5)
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude1"
    assert f"claude1: usage unreadable ({ERR.format('claude1')}); using its reading from 10 min ago" in capsys.readouterr().err.splitlines()


def test_a_recent_reading_over_its_limit_still_skips_the_account(world, usage):
    remember("claude1", 10, session=99)
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude3"


def test_an_old_reading_stands_in_whatever_its_age(world, usage, monkeypatch, capsys):
    remember("claude1", 40, weekly_all=5)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/u/.claude-elsewhere")
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude1"
    assert "using its reading from 40 min ago" in capsys.readouterr().err


def test_no_stored_reading_and_a_foreign_coordinator_block(world, usage, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/u/.claude-elsewhere")
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    out = capsys.readouterr().out
    assert e.value.code == 3 and f"claude1: usage unreadable: {ERR.format('claude1')}" in out.splitlines() and not world.fh.calls


def test_the_coordinators_account_signed_out_in_the_listing_gets_no_fallback(world, usage, monkeypatch):
    listing = {"accounts": [{"name": "claude1", "dir": DIRS["claude1"]}, {"name": "claude3", "dir": DIRS["claude3"], "signed_in": False}]}
    monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)
    usage["report"] = {"accounts": [unreadable("claude1", 1), unreadable("claude3", 3)]}
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3


def test_unreadable_coordinator_account_beats_one_known_over_its_limit(world, usage):
    usage["report"] = {"accounts": [acc("claude1", 1, session=99), unreadable("claude3", 3)]}
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude3"


def test_every_account_known_over_its_limit_still_blocks(world, usage, capsys):
    usage["report"] = {"accounts": [acc("claude1", 1, session=99), acc("claude3", 3, weekly_all=100)]}
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "BLOCKED: no account with headroom" in capsys.readouterr().out and not world.fh.calls


def test_a_good_reading_is_remembered_and_passes_unchanged(world, usage):
    good = {"accounts": [acc("claude1", 1, weekly_all=7), acc("claude3", 3, weekly_all=3)]}
    usage["report"] = good
    assert fleet.ac.read_usage() == good
    last = json.loads(fleet.ac._store().read_text())
    assert set(last) == {"claude1", "claude3"} and last["claude1"]["account"]["limits"] == good["accounts"][0]["limits"]


def test_an_account_with_a_reading_ranks_before_an_unknown_one_with_fewer_workers():
    u = {"accounts": [acc("claude1", 1, weekly_all=80), {**acc("claude3", 3), "unknown": True}]}
    assert fleet.ac.pick_account(u, ["claude1", "claude3"], running={"claude1": 4}) == "claude1"


def test_parallel_writers_keep_every_reading_and_leave_no_temp_file():
    import threading
    names = [f"claude{i}" for i in range(1, 9)]
    def write(name):
        for _ in range(15):
            fleet.ac._remember({"accounts": [acc(name, int(name[-1]), weekly_all=1)]}, time.time())
    threads = [threading.Thread(target=write, args=(n,)) for n in names]
    for t in threads: t.start()
    for t in threads: t.join()
    store = fleet.ac._store()
    assert set(json.loads(store.read_text())) == set(names)
    assert not list(store.parent.glob(store.name + ".*.tmp"))
