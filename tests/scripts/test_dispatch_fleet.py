# tests/scripts/test_dispatch_fleet.py
import json, os, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS, run, make_plan
from test_stable_split import DISPATCH
sys.path.insert(0, str(SCRIPTS))
import dispatch as dp  # noqa: E402

@pytest.fixture(autouse=True)
def fleet_module(tmp_path_factory, monkeypatch):
    """Fake fleet_state on PYTHONPATH by default; the real module (scripts dir wins on sys.path) when SUPERLITE_REAL=1."""
    if os.environ.get("SUPERLITE_REAL") == "1":
        return
    d = tmp_path_factory.mktemp("fakefleet")
    (d / "fleet_state.py").write_text("from pathlib import Path\ndef is_on(sd):\n    return (Path(sd) / 'fleet.json').exists()\n")
    monkeypatch.setenv("PYTHONPATH", str(d))
    monkeypatch.setattr(dp, "fleet_state", __import__("types").SimpleNamespace(is_on=lambda sd: (Path(sd) / "fleet.json").exists()))

def test_resolve_poll_examples():
    pool = {"agents": [{"id": "A", "context_k": 40}, {"id": "B", "context_k": 25}]}
    assert dp.resolve_poll("poll A,B", pool) == "agent=B"
    assert dp.resolve_poll("poll A,B", {"agents": [{"id": "A", "context_k": 30}, {"id": "B", "context_k": 30}]}) == "agent=A"
    assert dp.resolve_poll("agent=A", pool) == "agent=A" and dp.resolve_poll("fresh", pool) == "fresh"

def tied_world(tmp_path, fleet_on):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"}])
    sd = tmp_path / ".superlite"; sd.mkdir(exist_ok=True)
    (sd / "pool.json").write_text(json.dumps({"agents": [
        {"id": "A", "tier": "sonnet", "tasks": ["T9"], "files": ["src/z.py"], "context_k": 40, "idle_min": 1, "busy": False},
        {"id": "B", "tier": "sonnet", "tasks": ["T8"], "files": ["src/y.py"], "context_k": 25, "idle_min": 1, "busy": False}]}))
    if fleet_on:
        (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}, "next": 1, "accounts": [], "workspace_id": None, "root_pane": None, "label": "sl:x"}))
    return plan, sd

def go(plan, sd, tmp_path, batch="1"):
    return run(DISPATCH, "--plan", str(plan), "--pool", str(sd / "pool.json"), "--ledger", str(sd / "ledger.md"), "--batch", batch, cwd=tmp_path).out

def test_no_fleet_mode_keeps_poll(tmp_path):
    plan, sd = tied_world(tmp_path, False)
    assert "poll" in go(plan, sd, tmp_path)

def test_fleet_mode_replaces_poll_with_lowest_context(tmp_path):
    plan, sd = tied_world(tmp_path, True)
    out = go(plan, sd, tmp_path)
    assert "poll" not in out and "agent=B" in out

def test_fleet_mode_no_agent_twice(tmp_path):
    plan, sd = tied_world(tmp_path, True)
    out = go(plan, sd, tmp_path)
    agents = [tok.split("=")[1] for line in out.splitlines() for tok in line.split() if tok.startswith("agent=")]
    assert len(agents) == len(set(agents)) and "poll" not in out
