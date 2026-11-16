# tests/scripts/test_telemetry_stopped_remote_939.py: a remote fleet worker stopped on purpose writes one agent_stop STOPPED line (#939)
import contextlib, sys
from test_fleet_remote_worker import world, started, Routed  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402
import fleet_state as fs  # noqa: E402
import telemetry  # noqa: E402

SID = "5d6e7f80-9a1b-4c2d-8e3f-405162738495"


def lines(kind): return [e for e in telemetry.read_events() if e["kind"] == kind]


def with_session(w, wid="W1"):
    with fs.locked(w.sd):
        d = fs.load(w.sd); d["workers"][wid]["session"] = SID; fs.save(w.sd, d)


def test_kind_agent_stop_stopped_remote_once(world):
    started(world); with_session(world)
    rw.stop(world.sd, "W1")
    with contextlib.suppress(Exception):
        rw.stop(world.sd, "W1")
    fleet.stop(world.sd, ["W1"])
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == []
    assert (e["status"], e["role"], e["machine"], e["agent_session"]) == ("STOPPED", "research", "box", SID)


def test_kind_agent_stop_stopped_remote_via_fleet_stop(world):
    started(world); with_session(world)
    assert fleet.stop(world.sd, ["W1"]) == ["W1"]
    (e,) = lines("agent_stop")
    assert telemetry.validate(e) == [] and (e["status"], e["machine"], e["agent_session"]) == ("STOPPED", "box", SID)
