"""#880: a lead start that lands on Claude Code's sign-in screen marks the account signed out and retries once on another."""
import json
import pytest
from test_fleet import REAL, _three_accounts, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="scripted screens need the in-process fake")
SIGN_IN = " Select login method:\n\n ❯ 1. Claude account with subscription\n"
READY = "READY\n"


def lead(world, tmp_path, monkeypatch, screens, errors=()):
    """Accounts claude1, claude2; the screen read after start number n is screens[n-1]; start n raises HerdrError(errors[n-1]) when set."""
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    _three_accounts(world, monkeypatch)
    fleet.main(["on", "--accounts", "claude1,claude2"])
    n = [0]
    orig = world.fh.start_agent

    def start(*a, **k):
        n[0] += 1
        err = errors[n[0] - 1] if n[0] <= len(errors) else None
        if err:
            world.fh.calls.append(("start_agent", a[0], a[2]))
            raise world.fh.HerdrError(err, "blocked during startup")
        return orig(*a, **k)
    world.fh.start_agent = start
    world.fh.read_screen = lambda name, lines=40, source="visible": screens[min(max(n[0], 1), len(screens)) - 1]
    wt = tmp_path / "wt"; wt.mkdir(exist_ok=True)
    return wt


def workers(world):
    return json.loads((world.sd / "fleet.json").read_text())["workers"]


def run(world, wt):
    return fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})


def test_lead_signed_out_retries_on_another_account(world, tmp_path, monkeypatch, capsys):
    wt = lead(world, tmp_path, monkeypatch, [SIGN_IN, READY]); capsys.readouterr()
    r = run(world, wt)
    out, err = capsys.readouterr()
    assert r["account"] == "claude2" and "BLOCKED" not in out
    assert "W1 account claude1 signed out: Claude Code sign-in screen; retrying on account claude2" in err
    assert fleet.signed_out_accounts(world.sd) == {"claude1"}
    assert (workers(world)["W1"]["state"], workers(world)["W2"]["state"]) == ("blocked", "ready")
    assert ("close_pane", "w6:p1") in world.fh.calls


def test_lead_signed_out_twice_blocked_with_hint(world, tmp_path, monkeypatch, capsys):
    wt = lead(world, tmp_path, monkeypatch, [SIGN_IN, SIGN_IN]); capsys.readouterr()
    with pytest.raises(SystemExit) as e:
        run(world, wt)
    lines = [x for x in capsys.readouterr().out.splitlines() if x.startswith("BLOCKED: ")]
    assert e.value.code == 3 and len(lines) == 1
    assert lines[0].startswith("BLOCKED: W2 account claude2 signed out: Claude Code sign-in screen; sign in once (")
    assert "claude, then /login), then rerun" in lines[0] and lines[0].endswith("; retried after W1 on claude1")
    assert fleet.signed_out_accounts(world.sd) == {"claude1", "claude2"}


def test_lead_sign_in_screen_on_start_error(world, tmp_path, monkeypatch, capsys):
    wt = lead(world, tmp_path, monkeypatch, [SIGN_IN, READY], errors=["agent_not_ready"]); capsys.readouterr()
    r = run(world, wt)
    out, err = capsys.readouterr()
    assert r["account"] == "claude2" and "startup:" not in out + err
    assert "W1 account claude1 signed out: Claude Code sign-in screen; retrying on account claude2" in err
    assert fleet.signed_out_accounts(world.sd) == {"claude1"}


def test_lead_quoted_mark_is_not_signed_out(world, tmp_path, monkeypatch, capsys):
    wt = lead(world, tmp_path, monkeypatch, ["see the docs: Select login method: ...\nREADY\n"]); capsys.readouterr()
    r = run(world, wt)
    assert r["id"] == "W1" and workers(world)["W1"]["state"] == "ready"
    assert fleet.signed_out_accounts(world.sd) == set()
