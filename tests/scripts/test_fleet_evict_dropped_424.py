"""#424: `fleet spawn --for-dispatch` also stops the ready implementers an earlier dispatch dropped from pool.json."""
import json, os
import pytest
from test_fleet import world  # noqa: F401
from test_fleet_for_dispatch import dwld, _go, FRESH  # noqa: F401
import fleet
import pool
REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")


def drop(sd, *ids):
    """What dispatch.drop_evicted does in an earlier `commit_task --dispatch`: the ids leave pool.json, their panes stay."""
    p = sd / "pool.json"
    data = pool.load(p)
    for i in ids:
        pool.remove(data, i)
    pool.save(p, data)


def workers(sd):
    return json.loads((sd / "fleet.json").read_text())["workers"]


def spawn(w, n):
    for _ in range(n):
        fleet.spawn(w.sd, w.plan, "sonnet", w.proj)


def exits(w):
    return [c[1] for c in w.fh.calls if c[0] == "exit_agent"]


def test_ready_workers_an_earlier_dispatch_dropped_are_stopped(dwld, capsys):
    fleet.main(["on"]); spawn(dwld, 3); capsys.readouterr()
    drop(dwld.sd, "W1", "W2")
    dwld.lines = [("T3", "agent=W3 tier=sonnet")]; dwld.fh.calls.clear()
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["stopped W1", "stopped W2", "W3 T3 sent"]
    ws = workers(dwld.sd)
    assert ws["W1"]["state"] == "stopped" and ws["W2"]["state"] == "stopped" and ws["W3"]["state"] != "stopped"
    assert exits(dwld) == [fleet.fs.agent_name(dwld.sd, "W1"), fleet.fs.agent_name(dwld.sd, "W2")]


def test_busy_and_starting_workers_outside_the_pool_are_kept(dwld, capsys):
    fleet.main(["on"]); spawn(dwld, 2); capsys.readouterr()
    fleet.fs.set_state(dwld.sd, "W1", "busy"); fleet.fs.set_state(dwld.sd, "W2", "starting")
    drop(dwld.sd, "W1", "W2"); dwld.lines = []; dwld.fh.calls.clear()
    assert _go(dwld) == 0
    assert capsys.readouterr().out == "" and exits(dwld) == []
    ws = workers(dwld.sd)
    assert ws["W1"]["state"] == "busy" and ws["W2"]["state"] == "starting"


def test_ready_worker_of_another_role_is_kept(dwld, capsys):
    fleet.main(["on"]); fleet.spawn(dwld.sd, dwld.plan, None, dwld.proj, role="research"); spawn(dwld, 1); capsys.readouterr()
    dwld.lines = []; dwld.fh.calls.clear()
    assert _go(dwld) == 0
    assert capsys.readouterr().out == "" and exits(dwld) == []
    assert workers(dwld.sd)["W1"]["state"] == "ready"


def test_this_rounds_evict_and_an_earlier_drop_stop_each_worker_once(dwld, capsys):
    fleet.main(["on"]); spawn(dwld, 2); capsys.readouterr()
    drop(dwld.sd, "W1"); dwld.evict = {"W1": "context over 80k", "W2": "context over 80k"}; dwld.lines = []
    dwld.fh.calls.clear()
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["stopped W1", "stopped W2"]
    assert len(exits(dwld)) == 2


def test_no_pool_file_stops_nothing(dwld, capsys):
    fleet.main(["on"]); spawn(dwld, 1); (dwld.sd / "pool.json").unlink(); capsys.readouterr()
    dwld.lines = []; dwld.fh.calls.clear()
    assert _go(dwld) == 0
    assert capsys.readouterr().out == "" and workers(dwld.sd)["W1"]["state"] == "ready"


def test_spawn_writes_the_pool_entry_before_the_worker_reads_ready(world, monkeypatch):
    fleet.main(["on"]); seen = []
    orig = fleet.fs.set_state
    def spy(sd, wid, state, task=None):
        if state == "ready":
            p = fleet.Path(sd) / "pool.json"
            seen.append([a["id"] for a in pool.load(p).get("agents") or []] if p.exists() else [])
        return orig(sd, wid, state, task)
    monkeypatch.setattr(fleet.fs, "set_state", spy)
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert seen == [["W1"]]
