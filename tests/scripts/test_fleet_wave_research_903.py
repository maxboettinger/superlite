# tests/scripts/test_fleet_wave_research_903.py: research findings end no wave (#903)
import json
import pytest
from test_fleet_wait_wave_683 import fleet, stop, FINDINGS, _sleep  # noqa: F401
from test_fleet_io import world, io  # noqa: F401


def set_role(world, wids, role):
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text())
    for w in wids:
        d["workers"][w]["role"] = role
    p.write_text(json.dumps(d))


@pytest.mark.parametrize("r,want", [
    ({"status": "DONE", "findings": 3, "role": "research"}, False),
    ({"status": "DONE", "findings": 3, "role": "writer"}, False),
    ({"status": "DONE", "findings": 3, "role": "package-reviewer"}, True),
    ({"status": "DONE", "findings": 3}, True),
    ({"status": "BLOCKED", "findings": 0, "role": "research"}, True),
    ({"status": "APPROVED", "findings": 0, "partial": True, "role": "final-reviewer"}, True),
])
def test_wave_failure_examples(r, want):
    assert io.wave_failure(r) is want


def test_finish_result_carries_role(world, tmp_path):
    fleet(world, 2)
    set_role(world, ["W1"], "research")
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]
    assert io._finish(world.sd, "W1", w["W1"], "Status: DONE", "transcript")["role"] == "research"
    assert io._finish(world.sd, "W2", w["W2"], "Status: DONE", "transcript")["role"] == "implementer"


def test_wave_waits_for_both_research_workers(world, tmp_path):
    fleet(world, 2)
    set_role(world, ["W1", "W2"], "research")
    stop(world, tmp_path, "W1", 10, FINDINGS)
    stop(world, tmp_path, "W2", 40, "Status: DONE")
    out = io.wait(world.sd, None, 600000, wave=True)
    assert [r["id"] for r in out] == ["W1", "W2"] and out[0]["findings"] == 2
