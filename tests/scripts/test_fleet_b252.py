"""B252 fleet.py: choose_account(avoid=) takes a set, pick passes its signed-out pairs, a sign-in skip names only the account (#966); _follow prints follow's line (#786)."""
import time
import pytest
from test_fleet import world, acc  # noqa: F401
from test_fleet_signed_out_782 import two  # noqa: F401
from test_fleet_placement_signed_out_932 import env, WHY  # noqa: F401
import fleet
import fleet_placement as fp
import fleet_remote_account as fra


def test_choose_account_avoids_a_set(two):
    assert fleet.choose_account(two.sd, "sonnet", {})[0] == "a1"
    assert fleet.choose_account(two.sd, "sonnet", {}, avoid={"a1"})[0] == "a2"
    assert fleet.choose_account(two.sd, "sonnet", {}, avoid=set())[0] == "a1"
    with pytest.raises(SystemExit) as e:
        fleet.choose_account(two.sd, "sonnet", {}, avoid={"a1", "a2"})
    assert e.value.code == 3


def test_choose_account_str_avoid_is_one_name(two):
    assert fleet.choose_account(two.sd, "sonnet", {}, avoid="a1")[0] == "a2"


def test_retry_account_avoids_the_first_try(two):
    assert fleet._retry_account(two.sd, "sonnet", {}, "a1")[0] == "a2"


def test_pick_passes_signed_out_pairs_as_avoid(env, monkeypatch):
    fp.skip(env.sd, "box", WHY, now=time.time())
    seen = []
    def choose(sd, model, e, avoid=None, lead=False):
        seen.append(set(avoid or ()))
        a = "claude1" if "claude2" in (avoid or ()) else "claude2"
        return a, "/Users/u/.claude-" + a, a
    monkeypatch.setattr(fleet, "choose_account", choose)
    orig = fleet.signed_out_accounts
    e = {"HOME": "/Users/u"}
    assert fra.pick(env.sd, "box", "sonnet", e, "/home/u", "/Users/u")[0] == "claude1@box"
    assert fra.pick(env.sd, "other", "sonnet", e, "/home/u", "/Users/u")[0] == "claude2@other"
    assert seen == [{"claude2"}, set()] and fleet.signed_out_accounts is orig


def test_unavailable_sign_in_names_only_the_account(env, capsys):
    fleet._unavailable(env.sd, "box", "BLOCKED: fleet spawn: machine box: W3 not sent: account claude2 is not signed in on box; run /login for it there")
    assert capsys.readouterr().out.strip() == "placement: account claude2 skipped on box (not signed in there); local"
    assert fp.signed_out_pairs(env.sd, "box") == {"claude2"}


def test_unavailable_other_reason_unchanged(env, capsys):
    fleet._unavailable(env.sd, "box", "unreachable: ssh refused")
    assert capsys.readouterr().out.strip() == "placement: box unavailable (unreachable: ssh refused); local"


def test_follow_prints_the_line_follow_returns(monkeypatch, tmp_path, capsys):
    sd = tmp_path / "r" / ".superlite"; sd.mkdir(parents=True)
    monkeypatch.setattr(fleet.fs, "follow", lambda d, named=False: {"from": "/a", "to": str(d), "home": "/h", "workers": 2, "line": "fleet: L1\nfleet: L2"})
    fleet._follow(str(sd))
    assert capsys.readouterr().err == "fleet: L1\nfleet: L2\n"
