# tests/scripts/test_fleet_titles_467.py
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_io as io  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="titles are pure")


def _workers(world, **ws):
    fleet.fs.save(world.sd, {**fleet.fs.default(), "on": True, "workers": ws})


def test_pane_title_is_the_full_name_and_worker(world):
    _workers(world, W1={"name": "n", "pane_id": "w6:p1", "state": "ready"})
    assert io.pane_title(world.sd, "W1", "T3") == "sl:proj-main-T3 W1"
    assert io.pane_title(world.sd, "W1", "T3,T4", "BLOCKED-UI") == "sl:proj-main-T3,T4 W1 BLOCKED-UI"


def test_lead_title_uses_its_worktree(world, tmp_path):
    wt = tmp_path / "wt"; wt.mkdir()
    _workers(world, W2={"name": "n", "pane_id": "w6:p2", "state": "busy", "role": "lead", "worktree": str(wt)})
    assert io.pane_title(world.sd, "W2", "B102", "reported, waiting for coordinator") == "sl:wt-main-B102 W2 reported, waiting for coordinator"


def test_unknown_worker_title_uses_the_run(world):
    assert io.pane_title(world.sd, "W9", "T1") == "sl:proj-main-T1 W9"
