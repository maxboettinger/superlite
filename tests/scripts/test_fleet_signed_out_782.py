"""#782: a worker that stands on Claude Code's sign-in screen marks its account signed out; spawn retries once on another account."""
import json, os
import pytest
from test_fleet import world, acc  # noqa: F401
import fleet
REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted screens need the in-process fake")
SIGN_IN = " Select login method:\n\n ❯ 1. Claude account with subscription\n"
PASTE = "│ Paste code here if prompted >  │\n"
PROMPT = "> \n"
MARKS = ("Select login method:", "Paste code here if prompted")


@pytest.fixture(autouse=True)
def detector(monkeypatch):
    """T1's detector as its e.g. lines state it, so the tests hold before and after T1 commits."""
    def fake(screen):
        return any(l.strip(" \t│┃╭╮╰╯─❯>").startswith(MARKS) for l in screen.splitlines())
    monkeypatch.setattr(fleet.ac, "sign_in_screen", fake, raising=False)


@pytest.fixture
def two(world, monkeypatch):
    """Accounts a1 (usage prefers it) and a2."""
    world.usage["accounts"][:] = [acc("a1", 1, weekly_all=3), acc("a2", 2, weekly_all=64)]
    listing = {"accounts": [{"name": "a1", "dir": "/u/.claude-a1"}, {"name": "a2", "dir": "/u/.claude-a2"}]}
    monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)
    fleet.main(["on", "--accounts", "a1,a2"])
    return world


def nm(w, wid):
    return fleet.fs.agent_name(w.sd, wid)


def screens(w, scripted):
    """read_screen answers each worker from its list (the last entry repeats); other workers keep the fake's screen."""
    orig, seen = w.fh.read_screen, {}
    lists = {nm(w, k): v for k, v in scripted.items()}
    def read(name, lines=40, source="visible"):
        if name not in lists:
            return orig(name, lines, source)
        i = seen.get(name, 0)
        seen[name] = i + 1
        return lists[name][min(i, len(lists[name]) - 1)]
    w.fh.read_screen = read


def data(w):
    return json.loads((w.sd / "fleet.json").read_text())


def test_one_turn_signed_out_retries_other_account(two, capsys):
    capsys.readouterr()
    screens(two, {"W1": [SIGN_IN], "W2": [PROMPT]})
    w = fleet.spawn(two.sd, two.plan, "sonnet", two.proj, role="research")
    assert (w["id"], w["account"]) == ("W2", "a2")
    cap = capsys.readouterr()
    assert "W1 account a1 signed out: Claude Code sign-in screen; retrying on account a2" in cap.err.splitlines()
    d = data(two)
    assert d["workers"]["W1"]["state"] == "blocked" and "a1" in d["signed_out"]
    assert ("close_pane", d["workers"]["W1"]["pane_id"]) in two.fh.calls
    assert not [c for c in two.fh.calls if c[0] == "prompt" and c[1] == nm(two, "W1")]


def test_prime_signed_out_retries_other_account(two, capsys):
    capsys.readouterr()
    screens(two, {"W1": [PROMPT, PASTE], "W2": ["READY\n"]})
    w = fleet.spawn(two.sd, two.plan, "sonnet", two.proj)
    assert (w["id"], w["account"]) == ("W2", "a2")
    cap = capsys.readouterr()
    assert f"W2 account=a2 pane={w['pane_id']}" in cap.out
    assert "W1 account a1 signed out: Claude Code sign-in screen; retrying on account a2" in cap.err
    assert "a1" in data(two)["signed_out"]


def test_only_account_signed_out_blocks(world, monkeypatch, capsys):
    world.usage["accounts"][:] = [acc("a1", 1, weekly_all=3)]
    monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: {"accounts": [{"name": "a1", "dir": "/u/.claude-a1"}]})
    fleet.main(["on", "--accounts", "a1"]); capsys.readouterr()
    screens(world, {"W1": [SIGN_IN]})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj, role="research")
    out = capsys.readouterr().out
    assert e.value.code == 3
    assert "BLOCKED: no account with headroom" in out and "a1: signed out (Claude Code sign-in screen)" in out
    assert "account=" not in out


def test_signed_out_retry_also_signed_out(two, capsys):
    capsys.readouterr()
    screens(two, {"W1": [SIGN_IN], "W2": [SIGN_IN]})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(two.sd, two.plan, "sonnet", two.proj, role="research")
    assert e.value.code == 3
    last = capsys.readouterr().out.splitlines()[-1]
    assert last == ("BLOCKED: W2 account a2 signed out: Claude Code sign-in screen; sign in once "
                    "(CLAUDE_CONFIG_DIR=/u/.claude-a2 claude, then /login), then rerun; retried after W1 on a1")
    assert set(data(two)["signed_out"]) == {"a1", "a2"}


def test_choose_account_skips_marked_within_ttl(two, monkeypatch):
    fleet.mark_signed_out(two.sd, "a1")
    stamp = data(two)["signed_out"]["a1"]
    assert fleet.SIGNED_OUT_TTL_MS == 900000
    assert fleet.signed_out_accounts(two.sd, stamp + 60000) == {"a1"}
    assert fleet.signed_out_accounts(two.sd, stamp + 960000) == set()
    monkeypatch.setattr(fleet.time, "time", lambda: (stamp + 60000) / 1000)
    assert fleet.choose_account(two.sd, "sonnet", {})[0] == "a2"
    monkeypatch.setattr(fleet.time, "time", lambda: (stamp + 960000) / 1000)
    assert fleet.choose_account(two.sd, "sonnet", {})[0] == "a1"


def test_normal_screen_marks_nothing(two):
    screens(two, {"W1": [PROMPT]})
    assert fleet.spawn(two.sd, two.plan, "sonnet", two.proj, role="research")["id"] == "W1"
    assert not data(two).get("signed_out")
