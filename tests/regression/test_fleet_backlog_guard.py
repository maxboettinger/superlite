"""F-T10-1: a fleet worker or lead cannot run sl backlog decide|answer|start|plan, however the command is spelled
(env -u included): hooks/block-coordinator-edits judges it from the session's own environment."""
import json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
from test_fleet_hooks import run_hook  # noqa: E402


def call(sd, cmd, tool="Bash", **env):
    e = {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(sd), **env}
    return run_hook("block-coordinator-edits", json.dumps({"session_id": "s", "tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(sd.parent)}), e, sd.parent)


@pytest.fixture
def sd(tmp_path):
    d = tmp_path / "proj" / ".superlite"; d.mkdir(parents=True); return d


@pytest.mark.parametrize("cmd", [
    "env -u SUPERLITE_FLEET_WORKER sl backlog decide --file f",
    "env -u SUPERLITE_FLEET_WORKER -u SUPERLITE_FLEET_ROLE /abs/scripts/sl backlog answer --batch B1",
    "$SL backlog start B1", "${SL} backlog   plan --reset", 'bash -c "sl backlog decide --print"',
    "bash -c 'sl backlog start B2'", "python3 /x/scripts/backlog.py decide --file f", "sl 'backlog' \"decide\"",
    "sl back\\log decide", "sl\tbacklog\tdecide", "SL BACKLOG PLAN",
])
def test_lead_and_worker_cannot_run_the_main_session_subcommands(sd, cmd):
    for role in ("lead", "implementer"):
        r = call(sd, cmd, SUPERLITE_FLEET_ROLE=role)
        assert r.returncode == 2 and "main session" in r.stderr, (role, cmd, r.stderr)
    assert call(sd, cmd, tool="PowerShell").returncode == 2


@pytest.mark.parametrize("cmd", ["sl backlog status", "sl backlog wait", "sl backlog ship B1", "ls", "echo planning backlog", "sl backlog planner"])
def test_status_wait_ship_stay_allowed(sd, cmd):
    assert call(sd, cmd).returncode == 0


def test_the_main_session_is_not_judged(sd):
    r = call(sd, "sl backlog decide --file f", SUPERLITE_FLEET_WORKER="")
    assert r.returncode == 0
