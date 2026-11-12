# tests/scripts/test_fleet_status_579.py: fleet status shows reported and dead workers; report reads an uncollected turn (#579)
import json, sys
from pathlib import Path
from test_fleet import world, fleet  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))


def put(sd, workers, pool_ids=()):
    (sd / "fleet.json").write_text(json.dumps({"on": True, "accounts": [], "workers": workers}))
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": i, "tier": "sonnet", "state": "busy"} for i in pool_ids]}))


def wk(name, **kw):
    return {"name": name, "pane_id": "w6:p1", "account": "claude3", "agent": "superlite:implementer", "tier": "sonnet", "state": "ready", "task": None, **kw}


def stop_line(sd, t, wid="W1", **kw):
    with (sd / "metrics.jsonl").open("a") as f:
        f.write(json.dumps({"ev": "stop", "t": t, "agent_id": wid, **kw}) + "\n")


def fj(sd):
    return json.loads((sd / "fleet.json").read_text())["workers"]


def test_agent_gone_true_on_agent_not_found(world):
    world.fh.gone = {"sl-a"}
    assert fleet.agent_gone("sl-a") is True
    assert fleet.agent_gone("sl-b") is False
    world.fh.state_error = "timeout"
    assert fleet.agent_gone("sl-b") is False
    other = type(world.fh)(); other.gone = {"sl-z"}
    assert fleet.agent_gone("sl-z", other) is True and fleet.agent_gone("sl-a", other) is False


def test_mark_dead_stops_and_drops_from_pool(world):
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3")}, ["W1"])
    fleet.mark_dead(world.sd, "W1")
    w = fj(world.sd)["W1"]
    assert (w["state"], w["dead"], w["task"], w["last_task"]) == ("stopped", True, None, "T3")
    assert not [a for a in json.loads((world.sd / "pool.json").read_text())["agents"] if a["id"] == "W1"]
    assert not [c for c in world.fh.calls if c[0] == "close_pane"]


def test_respawn_hint_shapes(world):
    import pytest
    sd = Path("/r/.superlite")
    ws = {"W5": {"role": "fixer", "tier": "2", "brief": "/r/.superlite/briefs/fix-1.md"}, "W1": {"role": "implementer", "tier": "sonnet"},
          "W7": {"role": "final-reviewer", "tier": "opus", "brief": "/r/.superlite/review-packet.md"}}
    (world.sd / "fleet.json").write_text(json.dumps({"on": True, "workers": ws}))
    sd = world.sd
    assert fleet.respawn_hint(sd, "W5") == f"sl fleet spawn --role fixer --tier 2 --brief /r/.superlite/briefs/fix-1.md --plan {sd}"
    assert fleet.respawn_hint(sd, "W1") == f"sl fleet spawn --tier sonnet --plan {sd}"
    assert fleet.respawn_hint(sd, "W7", ".superlite") == "sl fleet spawn --role final-reviewer --brief /r/.superlite/review-packet.md --plan .superlite"
    with pytest.raises(KeyError):
        fleet.respawn_hint(sd, "W9")


def test_status_shows_dead_and_persists(world, capsys):
    put(world.sd, {"W1": wk("sl-a")}, ["W1"]); world.fh.gone = {"sl-a"}
    assert fleet.main(["status"]) == 0
    out = capsys.readouterr().out
    assert any(l.startswith("W1 dead account=") for l in out.splitlines())
    assert f"dead: W1 (its agent is gone); start a fresh one: sl fleet spawn --tier sonnet --plan {world.sd}" in out.splitlines()
    w = fj(world.sd)["W1"]
    assert w["state"] == "stopped" and w["dead"] is True
    fleet.main(["status"])
    assert "W1" not in capsys.readouterr().out
    fleet.main(["status", "--all"])
    assert "W1 dead" in capsys.readouterr().out


def test_status_shows_reported_for_ended_turn(world, capsys):
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3", sent=5000)}); stop_line(world.sd, 5010, last="Status: DONE")
    fleet.main(["status"])
    out = capsys.readouterr().out
    assert any(l.startswith("W1 reported account=") for l in out.splitlines())
    assert f"reported: W1; collect: sl fleet wait W1 --plan {world.sd}" in out.splitlines()
    assert fj(world.sd)["W1"]["state"] == "busy"


def test_status_busy_without_stop_stays_busy(world, capsys):
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3", sent=5000)})
    fleet.main(["status"])
    out = capsys.readouterr().out
    assert "W1 busy account=" in out and "reported:" not in out


def test_status_herdr_error_keeps_stored_state(world, capsys):
    put(world.sd, {"W1": wk("sl-a")}); world.fh.state_error = "timeout"
    before = (world.sd / "fleet.json").read_text()
    fleet.main(["status"])
    assert "W1 ready account=" in capsys.readouterr().out
    assert (world.sd / "fleet.json").read_text() == before


def test_status_does_not_probe_layer_or_starting(world, capsys):
    put(world.sd, {"W2": wk("sl-b", role="layer", state="busy"), "W3": wk("sl-c", state="starting")}); world.fh.gone = {"sl-b", "sl-c"}
    fleet.main(["status"])
    ws = fj(world.sd)
    assert ws["W2"]["state"] == "busy" and ws["W3"]["state"] == "starting" and not ws["W2"].get("dead") and not ws["W3"].get("dead")


def test_report_reads_an_uncollected_turn(world, capsys):
    tr = world.sd / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Status: DONE\nFiles: a.py"}]}}) + "\n")
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3", sent=5000)}); stop_line(world.sd, 5010, transcript=str(tr))
    assert fleet.main(["report", "W1"]) == 0
    c = capsys.readouterr()
    assert c.out == "Status: DONE\nFiles: a.py\n"
    assert "W1 T3: turn ended, not collected yet" in c.err
    assert not list((world.sd / "fleet" / "reports").glob("*")) if (world.sd / "fleet" / "reports").exists() else True
    assert fj(world.sd)["W1"]["state"] == "busy"


def test_report_busy_still_working_refuses(world, capsys):
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3", sent=5000)})
    assert fleet.main(["report", "W1"]) == 1
    assert "is busy on T3" in capsys.readouterr().err


def test_report_dead_worker_prints_last_report(world, capsys):
    put(world.sd, {"W1": wk("sl-a", state="busy", task="T3")}, ["W1"])
    fleet.mark_dead(world.sd, "W1")
    (world.sd / "fleet" / "reports").mkdir(parents=True); (world.sd / "fleet" / "reports" / "T3.md").write_text("Status: DONE\n")
    assert fleet.main(["report", "W1"]) == 0
    assert capsys.readouterr().out == "Status: DONE\n"
