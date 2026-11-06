# tests/scripts/test_fleet_dispatch_round.py
"""Fleet dispatch round fixes (#203-#206): prime check before a pane, no cap, evicted idle workers stopped, baseline in the pool and status."""
import json, os, sys
import pytest
from test_fleet import FakeHerdr, world  # noqa: F401
from test_fleet_for_dispatch import dwld, _go, FRESH  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
import dispatch  # noqa: E402
import fleet  # noqa: E402
import fleet_io  # noqa: E402
REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted fakes need the in-process fake")


def _next(sd):
    return json.loads((sd / "fleet.json").read_text()).get("next")


def test_spawn_without_prime_refuses_before_pane(world, capsys):
    fleet.main(["on"]); (world.sd / "prime.md").unlink(); before = _next(world.sd); world.fh.calls.clear()
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    assert capsys.readouterr().out.splitlines() == [f"BLOCKED: no {world.sd.resolve()}/prime.md; run build_prime --plan PLAN first"]
    assert world.fh.calls == [] and _next(world.sd) == before


def test_haiku_spawn_names_prime_haiku(world, capsys):
    fleet.main(["on"]); (world.sd / "prime-haiku.md").unlink()
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "haiku", world.proj)
    assert e.value.code == 3
    assert capsys.readouterr().out.splitlines() == [f"BLOCKED: no {world.sd.resolve()}/prime-haiku.md; run build_prime --tier haiku --plan PLAN first"]


def test_for_dispatch_without_prime_blocks_each_line(dwld, capsys):
    fleet.main(["on"]); (dwld.sd / "prime.md").unlink(); dwld.fh.calls.clear()
    dwld.lines = [("T2", FRESH), ("T3", FRESH)]
    assert _go(dwld) == 3
    p = f"{dwld.sd.resolve()}/prime.md"
    assert capsys.readouterr().out.splitlines() == [f"BLOCKED: T2 not sent (no {p}; run build_prime --plan PLAN first)", f"BLOCKED: T3 not sent (no {p}; run build_prime --plan PLAN first)"]
    assert "start_agent" not in [c[0] for c in dwld.fh.calls]


def test_no_ready_names_missing_prime(world, capsys):
    fleet.main(["on"]); fh = world.fh; fh.screen = "nothing here\n"
    orig = fh.prompt
    def prompt(name, text, until, timeout_ms):
        (world.sd / "prime.md").unlink(); return orig(name, text, until, timeout_ms)
    fh.prompt = prompt
    with pytest.raises(SystemExit):
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    out = capsys.readouterr().out
    assert "no READY" in out and f"no {world.sd.resolve()}/prime.md" in out


def test_for_dispatch_passes_no_cap(dwld, monkeypatch):
    seen = {}
    def run(*a, **k):
        seen.update(k); return [], {}
    monkeypatch.setattr(dispatch, "run", run)
    assert _go(dwld) == 0
    assert seen.get("cap") == sys.maxsize


def test_for_dispatch_stops_evicted_ready_worker(dwld, capsys):
    fleet.main(["on"]); fleet.spawn(dwld.sd, dwld.plan, "sonnet", dwld.proj); fleet.spawn(dwld.sd, dwld.plan, "sonnet", dwld.proj); capsys.readouterr()
    fleet.fs.set_state(dwld.sd, "W2", "busy")
    dwld.evict = {"W1": "context over 80k", "W2": "context over 80k"}; dwld.lines = [("T3", FRESH)]
    dwld.fh.calls.clear()
    assert _go(dwld) == 0
    cap = capsys.readouterr()
    assert cap.out.splitlines() == ["stopped W1", "W3 T3 sent"]
    workers = json.loads((dwld.sd / "fleet.json").read_text())["workers"]
    assert workers["W1"]["state"] == "stopped" and workers["W2"]["state"] == "busy"
    assert [c[1] for c in dwld.fh.calls if c[0] == "exit_agent"] == [fleet.fs.agent_name(dwld.sd, "W1")]
    assert "evict=W1 context over 80k" in cap.err


def test_for_dispatch_writes_baselines_into_pool(dwld, monkeypatch):
    fleet.main(["on"]); fleet.spawn(dwld.sd, dwld.plan, "sonnet", dwld.proj); fleet.spawn(dwld.sd, dwld.plan, "sonnet", dwld.proj)
    monkeypatch.setattr(fleet_io, "baseline_k", lambda sd, wid: {"W1": 14.4}.get(wid), raising=False)
    assert _go(dwld) == 0
    ag = {a["id"]: a for a in json.loads((dwld.sd / "pool.json").read_text())["agents"]}
    assert ag["W1"]["baseline_k"] == 14.4 and "baseline_k" not in ag["W2"]


def test_status_shows_context_and_baseline(world, capsys, monkeypatch):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    fleet.spawn(world.sd, world.plan, "1", world.proj, role="fixer"); capsys.readouterr()
    p = world.sd / "pool.json"; d = json.loads(p.read_text())
    d["agents"][0]["context_k"] = 52.3; d["agents"][1].pop("context_k")  # unknown value
    p.write_text(json.dumps(d))
    monkeypatch.setattr(fleet_io, "baseline_k", lambda sd, wid: {"W1": 14.4}.get(wid), raising=False)
    fleet.main(["status"]); lines = capsys.readouterr().out.splitlines()
    w = {l.split()[0]: l for l in lines[1:]}
    assert w["W1"].endswith(" context_k=52.3 baseline_k=14.4")
    assert w["W2"].endswith(" context_k=- baseline_k=-")
    assert "context_k=" not in w["W3"]


def test_eligibility_uses_baseline():
    lim = {"max_context_k": 80}
    assert assign.eligibility({"context_k": 70, "baseline_k": 30, "tasks": [], "idle_min": 0}, 20, lim, 5.0) is None
    assert assign.eligibility({"context_k": 70, "tasks": [], "idle_min": 0}, 20, lim, 5.0) == "context over 80k"
    assert assign.eligibility({"context_k": 70, "baseline_k": None, "tasks": [], "idle_min": 0}, 20, lim, 5.0) == "context over 80k"


def test_status_and_dispatch_survive_pool_without_agents_key(world, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj); capsys.readouterr()
    (world.sd / "pool.json").write_text("{}")
    assert fleet.main(["status"]) == 0
    assert "W1" in capsys.readouterr().out
