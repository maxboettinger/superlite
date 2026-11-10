# tests/scripts/test_fleet_lead_b87.py: #464 autocompact window, #454-style slow start retry, #514 trust dialog for a lead
import json
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="scripted herdr replies need the in-process fake")


def test_main_window(tmp_path):
    assert fl.main_window({"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300000"}, "opus") == 300000
    d = tmp_path / "cfg"; d.mkdir()
    (d / "settings.json").write_text(json.dumps({"autoCompactWindow": 250000}))
    assert fl.main_window({"CLAUDE_CONFIG_DIR": str(d)}, "opus") == 250000
    (d / "settings.json").write_text(json.dumps({"modelSettings": {"claude-opus-5-5": {"autoCompactWindow": 350000}}}))
    assert fl.main_window({"CLAUDE_CONFIG_DIR": str(d)}, "opus") == 350000
    (d / "settings.json").write_text(json.dumps({"autoCompactWindow": True}))
    assert fl.main_window({"CLAUDE_CONFIG_DIR": str(d)}, "opus") == 400000
    (d / "settings.json").write_text("{not json")
    assert fl.main_window({"CLAUDE_CONFIG_DIR": str(d)}, "opus") == 400000
    h = tmp_path / "home"; (h / ".claude").mkdir(parents=True)
    (h / ".claude" / "settings.json").write_text(json.dumps({"autoCompactWindow": 200000}))
    assert fl.main_window({"HOME": str(h)}, "opus") == 200000
    assert fl.main_window({"HOME": str(tmp_path / "none")}, "opus") == 400000


def test_lead_argv_window():
    base = fl.lead_argv("/p/sl", "opus")
    assert fl.lead_argv("/p/sl", "opus", 400000) == base + ["--autocompact", "400k"]
    assert fl.lead_argv("/p/sl", "opus", 123456) == base + ["--autocompact", "123456"]
    assert fl.lead_argv("/p/sl", "opus", None) == base


def _lead(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    fleet.main(["on", "--accounts", "claude1,claude3"])
    return tmp_path / "wt"


def test_slow_start_retried_on_another_account(world, tmp_path, monkeypatch, capsys):
    wt = _lead(world, tmp_path, monkeypatch)
    world.fh.start_error = "timeout"
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert (r["id"], r["account"]) == ("W2", "claude1")
    assert "W1 account claude3 startup: READY; retrying on account claude1" in capsys.readouterr().err
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "blocked"


def test_second_slow_start_blocks(world, tmp_path, monkeypatch, capsys):
    wt = _lead(world, tmp_path, monkeypatch)
    def always(name, pane_id, argv, timeout_ms=90000):
        raise world.fh.HerdrError("timeout", "blocked during startup")
    world.fh.start_agent = always
    with pytest.raises(SystemExit) as e:
        fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert e.value.code == 3
    out = capsys.readouterr().out
    assert "BLOCKED:" in out and out.strip().endswith("; retried after W1 on claude3")


def test_other_start_error_not_retried(world, tmp_path, monkeypatch):
    wt = _lead(world, tmp_path, monkeypatch)
    world.fh.start_error = "agent_not_ready"; world.fh.screen = "Select login method\n"
    with pytest.raises(SystemExit) as e:
        fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert e.value.code == 3
    assert sum(1 for c in world.fh.calls if c[0] == "start_agent") == 1


def test_trust_dialog_after_start_accepted(world, tmp_path, monkeypatch):
    wt = _lead(world, tmp_path, monkeypatch)
    world.fh.screen = "Quick safety check\n > No, exit\n   Yes, I trust this folder\n"
    fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    name = fleet.fs.agent_name(world.sd, "W1")
    assert ("send_keys", name, ["Down", "Enter"]) in world.fh.calls
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"


def test_ready_screen_sends_no_keys(world, tmp_path, monkeypatch):
    wt = _lead(world, tmp_path, monkeypatch)
    world.fh.screen = "Yes, I trust this folder\nREADY\n"
    fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert not any(c[0] == "send_keys" for c in world.fh.calls)
