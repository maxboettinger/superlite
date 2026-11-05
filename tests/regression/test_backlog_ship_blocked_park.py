"""F-T12-1 / F-T12-2: BLOCKED exits 3 (docstring), and release --park leaves a state the runner's round can see."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
from test_backlog_ship import sh, ship, b1, locked  # noqa: F401
import backlog_state as bs


def test_blocked_maxapp_outcomes_exit_3(sh, capsys):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (0, "shipped without a number\n")}
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 3 and out.startswith("BLOCKED: maxapp ship gave no merged PR number")
    sh.replies = {"maxapp ship": (1, "boom\n")}
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 3 and out.startswith("BLOCKED: maxapp ship failed")


def test_release_park_records_state_reason_and_time(sh, capsys):
    locked(sh, capsys)
    assert ship(capsys, "B1", "release", "--park", "conflict in a.py")[0] == 0
    b = b1(sh)
    assert (b["state"], b["reason"], b["parked_at"]) == ("parked", "conflict in a.py", 10_000)
    assert b["lead"] == "W1" and b["agent"]  # the runner still finds the lead to stop
