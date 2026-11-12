# tests/scripts/test_fleet_lead_record_577.py
import json
from pathlib import Path
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")


def _spawn(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"; wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    return wt, json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]


def test_lead_records_launch(world, tmp_path, monkeypatch):
    wt, w = _spawn(world, tmp_path, monkeypatch)
    name = w["name"]
    argv = next(c for c in world.fh.calls if c[0] == "start_agent" and c[1] == name)[2]
    env = next(c for c in world.fh.calls if c[0] == "create_workspace")[2]
    assert w["launch"] == {"argv": argv, "env": env, "cwd": str(wt.resolve())}


def test_lead_records_session(world, tmp_path, monkeypatch):
    monkeypatch.setattr(world.fh, "agent_session", lambda name: "sid-9", raising=False)
    wt, w = _spawn(world, tmp_path, monkeypatch)
    assert w["session"] == "sid-9"


def test_lead_without_agent_session_still_starts(world, tmp_path, monkeypatch):
    wt, w = _spawn(world, tmp_path, monkeypatch)
    assert w["state"] == "ready" and w.get("session") is None
