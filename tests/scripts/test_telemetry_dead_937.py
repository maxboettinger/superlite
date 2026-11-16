# tests/scripts/test_telemetry_dead_937.py: a fleet worker marked DEAD writes one agent_stop line with status DEAD (#937)
import json, sys
from test_fleet_io import world, FakeHerdr  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as io  # noqa: E402
import telemetry  # noqa: E402


def lines(kind): return [e for e in telemetry.read_events() if e["kind"] == kind]


def fj(w): return json.loads((w.sd / "fleet.json").read_text())["workers"]


def set_worker(w, wid, **kw):
    d = json.loads((w.sd / "fleet.json").read_text()); d["workers"][wid].update(kw)
    (w.sd / "fleet.json").write_text(json.dumps(d))


def test_kind_agent_stop_dead_in_wait(world):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    sent = world.clock.t[0]
    world.fh.states = [{"sl-proj-w2": "working"}]; world.fh.gone = {"sl-proj-w1"}
    out = io.wait(world.sd, ["W1"], 60000)
    assert [r["status"] for r in out] == ["DEAD"]
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert (e["status"], e["task"], e["role"], e["model"], e["account"], e["machine"], e["effort"]) == \
        ("DEAD", "T3", "implementer", "sonnet", "claude1", None, None)
    assert (e["tokens"], e["cost_usd"], e["tool_calls"]) == (None, None, None)
    assert 0 <= e["duration_s"] <= round((world.clock.t[0] - sent) / 1000, 1)
    assert lines("review") == []


def test_kind_agent_stop_dead_once(world):
    set_worker(world, "W1", state="busy", task="T4", sent=world.clock.t[0])
    fleet.mark_dead(world.sd, "W1")
    fleet.mark_dead(world.sd, "W1")
    assert fj(world)["W1"]["dead"] is True
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and (e["status"], e["task"], e["duration_s"]) == ("DEAD", "T4", 0.0)


def test_kind_agent_stop_dead_idle_worker(world):
    set_worker(world, "W2", role="research", last_task="R1")
    fleet.mark_dead(world.sd, "W2")
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert (e["status"], e["role"], e["task"], e["duration_s"], e["model"]) == ("DEAD", "research", None, None, "sonnet")


def test_kind_agent_stop_dead_reviewer_writes_no_review(world):
    set_worker(world, "W1", role="final-reviewer", state="busy", task="FR2", sent=world.clock.t[0] - 3000)
    fleet.mark_dead(world.sd, "W1")
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert (e["status"], e["role"], e["task"], e["duration_s"]) == ("DEAD", "final-reviewer", None, 3.0)
    assert lines("review") == []


def test_kind_agent_stop_dead_send_not_found(world, capsys):
    def gone(name, text, until, timeout_ms): raise world.fh.HerdrError("agent_not_found", "gone")
    world.fh.prompt = gone
    assert io.main(["send", "W1", "--text", "hi"]) == 2
    assert fj(world)["W1"]["dead"] is True
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and e["status"] == "DEAD" and e["role"] == "implementer"


def test_kind_agent_stop_dead_unknown_worker_writes_nothing(world):
    fleet.mark_dead(world.sd, "W9")
    assert lines("agent_stop") == []


def test_mark_dead_fails_open(world, monkeypatch):
    def boom(*a, **k): raise SystemExit(3)
    monkeypatch.setattr(telemetry, "emit", boom)
    fleet.mark_dead(world.sd, "W1")
    assert fj(world)["W1"]["state"] == "stopped" and fj(world)["W1"]["dead"] is True


def test_kind_agent_stop_dead_off_switch(world, monkeypatch):
    monkeypatch.setenv("SUPERLITE_TELEMETRY", "0")
    fleet.mark_dead(world.sd, "W1")
    assert fj(world)["W1"]["dead"] is True
    assert lines("agent_stop") == []


def test_docs_name_dead_status():
    doc = (SCRIPTS.parents[2] / "docs" / "telemetry.md").read_text(encoding="utf-8")
    assert "`DEAD` when superlite marks a fleet worker dead" in doc
    row = next(l for l in doc.splitlines() if l.startswith("| `agent_stop` |"))
    assert "`fleet_io.py`" in row and "`fleet.py`" in row
