# tests/scripts/test_fleet_account_weekly_761.py
import json, sys
import pytest
from test_accounts import acc
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_lead  # noqa: E402


def _setup(tmp_path, monkeypatch, usage, entries=("a1", "a2"), workers=None, cap=90):
    home = tmp_path / "home"; home.mkdir()
    if cap is not None:
        (home / "machine.json").write_text(json.dumps({"lead_weekly_max": cap}))
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    sd = tmp_path / "sd"; sd.mkdir()
    ws = {f"W{i}": {"account": a, "state": "busy"} for i, a in enumerate(workers or [], 1)}
    (sd / "fleet.json").write_text(json.dumps({"accounts": list(entries), "workers": ws}))
    listing = {"accounts": [{"name": n, "dir": f"/u/.{n}"} for n in ("a1", "a2")]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": usage})
    monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)
    monkeypatch.setattr(fleet.hc, "agents", lambda: [])
    return sd


def _pick(sd, **kw):
    return fleet.choose_account(sd, None, {"HOME": "/u"}, **kw)[0]


def test_lead_pick_skips_over_weekly_max(tmp_path, monkeypatch):
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=95), acc("a2", 2, weekly_all=40)], workers=["a2"])
    assert _pick(sd, lead=True) == "a2"
    assert _pick(sd, lead=False) == "a1"


def test_lead_role_env_gates_worker_pick(tmp_path, monkeypatch):
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=95), acc("a2", 2, weekly_all=40)], workers=["a2"])
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead")
    assert _pick(sd, lead=False) == "a2"


def test_at_limit_counts_as_over(tmp_path, monkeypatch):
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=90), acc("a2", 2, weekly_all=40)], workers=["a2"])
    assert _pick(sd, lead=True) == "a2"


def test_all_over_falls_back(tmp_path, monkeypatch, capsys):
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=95), acc("a2", 2, weekly_all=92)], workers=["a2"])  # a2 holds a worker: the plain pick is a1
    assert _pick(sd, lead=True) == "a1"
    assert "a1: weekly_all 95% >= lead_weekly_max 90%; no account under it" in capsys.readouterr().err


def test_unknown_entry_before_over_limit(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=95)], entries=("a1", str(cfg)))
    assert _pick(sd, lead=True) == "cfg"


def test_no_weekly_max_plain_pick(tmp_path, monkeypatch):
    sd = _setup(tmp_path, monkeypatch, [acc("a1", 1, weekly_all=95), acc("a2", 2, weekly_all=40)], workers=["a2"], cap=None)
    assert _pick(sd, lead=True) == "a1"


def test_retry_account_passes_lead(tmp_path, monkeypatch):
    calls = []
    def fake(sd, model, env, avoid=None, lead=False):
        calls.append(lead)
        raise SystemExit(3)
    monkeypatch.setattr(fleet, "choose_account", fake)
    with pytest.raises(SystemExit):
        fleet._retry_account(tmp_path, None, {}, "a1", lead=True)
    assert calls == [True, True]


def test_spawn_lead_asks_lead_pick(tmp_path, monkeypatch):
    seen = []
    def fake(*a, **kw):
        seen.append(kw)
        raise SystemExit(3)
    monkeypatch.setattr(fleet, "choose_account", fake)
    rc = {"lead": {"model": "opus"}}
    with pytest.raises(SystemExit):
        fleet_lead._spawn_lead(tmp_path / "sd", tmp_path / "wt", "opus", {}, None, rc)
    assert seen and seen[0].get("lead") is True
