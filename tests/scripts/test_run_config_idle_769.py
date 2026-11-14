"""#769: run config key lead.idle_minutes (minutes of lead silence before backlog wait re-prompts; 0 turns the check off)."""
import json
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import run_config as rc  # noqa: E402


@pytest.mark.parametrize("v", [None, 0, 10, 1440])
def test_idle_minutes_takes_null_or_0_to_1440(v):
    rc._lead("t", "x", {"idle_minutes": v})


@pytest.mark.parametrize("v", [-1, 1441, True, 2.5, "10"])
def test_idle_minutes_refuses_other_values(v):
    with pytest.raises(rc.ConfigError, match="lead.idle_minutes"):
        rc._lead("t", "x", {"idle_minutes": v})


def test_builtin_configs_leave_idle_minutes_out_so_config_ids_stay():
    d = json.loads(rc.BUILTIN.read_text(encoding="utf-8"))
    leads = [(c or {}).get("lead") or {} for c in (d.get("configs") or {}).values()]
    assert all("idle_minutes" not in x for x in leads)
    assert "idle_minutes" in d["_comment"]
