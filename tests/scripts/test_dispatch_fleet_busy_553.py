"""#553: dispatch never offers a worker fleet.json marks busy (a `fleet send --text` answer still running)."""
import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run, make_plan
from test_stable_split import DISPATCH

sys.path.insert(0, str(SCRIPTS))
import dispatch as dp  # noqa: E402

AGENT = {"id": "W1", "tier": "sonnet", "tasks": ["T9"], "files": ["src/z.py"], "context_k": 20, "idle_min": 1, "busy": False}
ROOT = Path(__file__).resolve().parents[2]


def world(tmp_path, state, on=True):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py"}])
    sd = tmp_path / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "pool.json").write_text(json.dumps({"agents": [dict(AGENT)]}), encoding="utf-8")
    workers = {"W1": {"state": state, "task": "T9", "sent": 5, "role": "implementer"}}
    (sd / "fleet.json").write_text(json.dumps({"on": on, "workers": workers, "next": 2, "accounts": [], "workspace_id": None, "root_pane": None, "label": "sl:x"}), encoding="utf-8")
    return plan, sd


def lines(plan, sd):
    out, _ = dp.plan_dispatch(plan, json.loads((sd / "pool.json").read_text(encoding="utf-8")), [], [], 10, sl_dir=sd)
    return out


def test_fleet_busy_worker_gets_no_task(tmp_path):
    plan, sd = world(tmp_path, "busy")
    out = lines(plan, sd)
    assert [t for t, _ in out] == ["T1"]
    assert out[0][1].startswith("fresh ") and "W1" not in out[0][1]


def test_fleet_ready_worker_still_gets_the_task(tmp_path):
    plan, sd = world(tmp_path, "ready")
    out = lines(plan, sd)
    assert [t for t, _ in out] == ["T1"] and out[0][1].startswith("agent=W1 ")


def test_fleet_off_ignores_fleet_json(tmp_path):
    plan, sd = world(tmp_path, "busy", on=False)
    out = lines(plan, sd)
    assert [t for t, _ in out] == ["T1"] and "W1" in out[0][1] and not out[0][1].startswith("fresh")


def test_busy_worker_is_not_evicted(tmp_path):
    plan, sd = world(tmp_path, "busy")
    pool = json.loads((sd / "pool.json").read_text(encoding="utf-8"))
    pool["agents"][0]["context_k"] = 500
    _, evict = dp.plan_dispatch(plan, pool, [], [], 10, sl_dir=sd)
    assert "W1" not in evict


def test_cli_dispatch_skips_busy_and_leaves_pool_as_is(tmp_path):
    plan, sd = world(tmp_path, "busy")
    out = run(DISPATCH, "--plan", str(plan), "--pool", str(sd / "pool.json"), "--ledger", str(sd / "ledger.md"), cwd=tmp_path).out
    assert "T1 fresh" in out and "agent=W1" not in out
    agents = json.loads((sd / "pool.json").read_text(encoding="utf-8"))["agents"]
    assert [a["id"] for a in agents] == ["W1"] and agents[0]["busy"] is False and "current" not in agents[0]


def test_docs_name_the_rule():
    assert "#553" in (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "#553" in (ROOT / "skills" / "subagent-driven-development" / "scripts" / "fleet.py").read_text(encoding="utf-8").split('"""')[1]
