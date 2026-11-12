# tests/scripts/test_fleet_dead_send_579.py: wait ends a dead worker, send refuses a finished one (#579)
import json, sys
from test_fleet_io import world, FakeHerdr  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402


def fj(w): return json.loads((w.sd / "fleet.json").read_text())["workers"]


def pool_ids(w): return [a["id"] for a in json.loads((w.sd / "pool.json").read_text())["agents"]]


def set_worker(w, wid, **kw):
    d = json.loads((w.sd / "fleet.json").read_text()); d["workers"][wid].update(kw)
    (w.sd / "fleet.json").write_text(json.dumps(d))


def test_wait_ends_a_dead_worker(world, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    world.fh.states = [{"sl-proj-w2": "working"}]; world.fh.gone = {"sl-proj-w1"}
    out = io.wait(world.sd, ["W1"], 60000)
    assert [r["status"] for r in out] == ["DEAD"]
    assert capsys.readouterr().out.splitlines()[-1].startswith("W1 T3 DEAD (its agent is gone; no report); start a fresh one: sl fleet spawn --tier sonnet --plan ")
    assert fj(world)["W1"]["state"] == "stopped" and fj(world)["W1"]["dead"] is True
    assert "W1" not in pool_ids(world)


def test_live_unlisted_worker_keeps_waiting(world, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    world.fh.states = [{"sl-proj-w2": "working"}]
    io.wait(world.sd, ["W1"], 5000)
    assert capsys.readouterr().out.splitlines()[-1].startswith("TIMEOUT W1")
    probes = [c for c in world.fh.calls if c[0] == "agent_state"]
    assert len(probes) <= 1
    world.fh.calls.clear()
    io.wait(world.sd, ["W1"], 25000)
    assert len([c for c in world.fh.calls if c[0] == "agent_state"]) <= 3


def test_listing_failure_is_no_death(world, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    world.fh.gone = {"sl-proj-w1"}
    def boom(): raise world.fh.HerdrError("x", "down")
    world.fh.agent_states = boom
    io.wait(world.sd, ["W1"], 5000)
    assert not [c for c in world.fh.calls if c[0] == "agent_state"]
    assert capsys.readouterr().out.splitlines()[-1].startswith("TIMEOUT W1")


def test_send_records_the_brief(world, tmp_path):
    b = tmp_path / "b.md"; b.write_text("do it")
    io.send_brief(world.sd, "W1", b)
    assert fj(world)["W1"]["brief"] == str(b.resolve())


def stopped_fixer(w, **kw):
    set_worker(w, "W1", role="fixer", tier="2", state="stopped", last_task="FX1", brief="/b/fix.md", **kw)


def test_send_to_stopped_fixer_names_fresh_spawn(world, capsys, tmp_path):
    stopped_fixer(world)
    want = f"error: W1 is stopped (fixer, last task FX1); start a fresh one: sl fleet spawn --role fixer --tier 2 --brief /b/fix.md --plan {io.state.resolve()}"
    b = tmp_path / "x.md"; b.write_text("x")
    for argv in (["send", "W1", "--text", "hi"], ["send", "W1", "--brief", str(b)], ["send", "W1", "T3"], ["keys", "W1", "Enter"]):
        assert io.main(argv) == 2
        assert capsys.readouterr().err.strip() == want
    assert not [c for c in world.fh.calls if c[0] in ("prompt", "send_keys")]


def test_send_to_dead_names_dead(world, capsys):
    stopped_fixer(world, dead=True)
    assert io.main(["send", "W1", "--text", "hi"]) == 2
    assert capsys.readouterr().err.startswith("error: W1 is dead (its agent is gone; last task FX1)")


def test_send_agent_not_found_marks_dead(world, capsys):
    def gone(name, text, until, timeout_ms): raise world.fh.HerdrError("agent_not_found", "gone")
    world.fh.prompt = gone
    assert io.main(["send", "W1", "--text", "hi"]) == 2
    assert capsys.readouterr().err.startswith("error: W1 is dead (its agent is gone")
    assert fj(world)["W1"]["state"] == "stopped" and fj(world)["W1"]["dead"] is True
