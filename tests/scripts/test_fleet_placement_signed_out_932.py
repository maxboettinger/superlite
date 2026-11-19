# tests/scripts/test_fleet_placement_signed_out_932.py
import json, socket, sys
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_placement as fp  # noqa: E402
import fleet_remote_account as fra  # noqa: E402
import herdr_client as hc  # noqa: E402

ROOM = str(FIXTURES / "fleet" / "room")
READY = {"machines": [{"name": "host1", "state": "ready", "room": 4}, {"name": "box", "state": "ready", "room": 12}]}
WHY = "account claude2 is not signed in on box"
LINE = ("placement: account claude2 is signed out on box; box stays in placement with its other accounts; "
        "sign claude2 in there once (claude, then /login)")


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("FAKE_ROOM_LOG", str(tmp_path / "log"))
    monkeypatch.setenv("FAKE_ROOM_JSON", json.dumps(READY))
    monkeypatch.delenv("FAKE_ROOM_EXIT", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "host1.local")
    monkeypatch.setattr(hc, "machines", lambda: [{"label": "box", "enabled": True}])
    (home / "machine.json").write_text(json.dumps({"remote_room": [ROOM], "remote_tree": ["x"]}))
    return type("E", (), {"home": home, "proj": proj, "sd": sd})


def test_signed_out_account_parse():
    assert fra.signed_out_account("W3 not sent: account claude2 is not signed in on box; run /login for it there") == "claude2"
    assert fra.signed_out_account("BLOCKED: no account with headroom") is None
    assert fra.signed_out_account(None) is None
    assert fra.signed_out_account("") is None
    assert fra.signed_out_account(WHY) == "claude2"


def test_signed_out_skip_keeps_machine(env):
    fp.skip(env.sd, "box", WHY, now=1000.0)
    assert fp.choose(env.sd, "research", env.proj, now=1001.0) == "box"
    fp.skip(env.sd, "box", "startup: timeout", now=1000.0)
    assert fp.choose(env.sd, "research", env.proj, now=1001.0) is None


def test_pair_named_once(env, capsys):
    fp.skip(env.sd, "box", WHY, now=1000.0)
    assert capsys.readouterr().err.strip() == LINE
    fp.skip(env.sd, "box", WHY, now=1001.0)
    fp.skip(env.sd, "box", WHY, now=5000.0)
    assert capsys.readouterr().err == ""
    fp.skip(env.sd, "box", "account claude3 is not signed in on box", now=5001.0)
    err = capsys.readouterr().err
    assert "account claude3 is signed out on box" in err and err.count("\n") == 1


def test_signed_out_pairs_ttl(env):
    fp.skip(env.sd, "box", WHY, now=1000.0)
    assert fp.signed_out_pairs(env.sd, "box", now=1001.0) == {"claude2"}
    assert fp.signed_out_pairs(env.sd, "box", now=1901.0) == set()
    assert fp.signed_out_pairs(env.sd, "other", now=1001.0) == set()


def test_machine_skip_keeps_pairs(env):
    fp.skip(env.sd, "box", WHY, now=1000.0)
    fp.skip(env.sd, "box", "startup: timeout", now=1000.0)
    assert fp.signed_out_pairs(env.sd, "box", now=1001.0) == {"claude2"}
    assert fp.choose(env.sd, "research", env.proj, now=1001.0) is None
    assert fp.choose(env.sd, "research", env.proj, now=1000.0 + 601) == "box"


def test_pick_skips_signed_out_pair(env, monkeypatch):
    import time
    fp.skip(env.sd, "box", WHY, now=time.time())

    def choose(sd, model, e, avoid=None, lead=False):
        a = "claude1" if "claude2" in (avoid or ()) else "claude2"
        return a, "/Users/u/.claude-" + a, a
    monkeypatch.setattr(fleet, "choose_account", choose)
    e = {"HOME": "/Users/u"}
    assert fra.pick(env.sd, "box", "sonnet", e, "/home/u", "/Users/u")[0] == "claude1@box"
    assert fra.pick(env.sd, "other", "sonnet", e, "/home/u", "/Users/u")[0] == "claude2@other"
