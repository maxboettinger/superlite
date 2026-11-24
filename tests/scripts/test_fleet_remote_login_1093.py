"""A remote account whose login expired is skipped after its first brief turn and reported BLOCKED-UI in fleet wait (#1093)."""
import json
import sys
import time
import pytest
from test_fleet_remote_worker import world, started, record  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import accounts  # noqa: E402
import fleet  # noqa: E402
import fleet_io as fio  # noqa: E402
import fleet_placement as fp  # noqa: E402
import fleet_remote_account as fra  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402
import herdr_client as hc  # noqa: E402

LOGIN = "Login reached its time limit · Please run /login"


def patch_record(world, **kw):
    p = world.sd / "fleet.json"; d = json.loads(p.read_text()); d["workers"]["W1"].update(kw); p.write_text(json.dumps(d))


def stop(world, last, t=None):
    mirror = str(world.sd / "remote" / "W1")
    import os
    os.makedirs(mirror, exist_ok=True)
    with open(f"{mirror}/metrics.jsonl", "a") as f:
        f.write(json.dumps({"ev": "stop", "agent_id": "W1", "t": t or int(time.time() * 1000) + 600000, "last": last}) + "\n")


def brief(world):
    b = world.sd / "briefs" / "q.md"; b.write_text("question"); return str(b)


def busy(world, sent=1000):
    started(world)
    patch_record(world, state="busy", sent=sent, task="Q1")
    world.fh.agent_map = {record(world)["name"]: "idle"}


def test_signed_out_stop_examples():
    assert fra.signed_out_stop({"last": LOGIN}) is True
    assert fra.signed_out_stop({"last": "Not logged in · Please run /login"}) is True
    assert fra.signed_out_stop({"last": "Invalid API key · Please run /login"}) is True
    assert fra.signed_out_stop({"last": "Status: DONE; the pane said Not logged in · run /login"}) is False
    assert fra.signed_out_stop({"last": "Not logged in\nStatus: DONE /login"}) is False
    assert fra.signed_out_stop(None) is False


def test_login_screen_new_marks():
    assert fra.login_screen("Not logged in · run /login") and fra.login_screen("  ⎿  " + LOGIN)


def test_sign_in_screen_new_marks():
    assert accounts.sign_in_screen("> Read q.md\n  ⎿  " + LOGIN + "\n")
    assert accounts.sign_in_screen("Not logged in · Please run /login")
    assert not accounts.sign_in_screen("The pane said Not logged in · run /login")


def test_first_brief_on_logged_out_account_raises(world):
    started(world)
    stop(world, LOGIN)
    with pytest.raises(world.fh.HerdrError) as e:
        rw.send_brief(world.sd, "W1", brief(world), "Q1")
    assert e.value.code == "account_signed_out" and e.value.message == "account claude1 is not signed in on box; run /login for it there"
    assert len([c for c in world.fh.calls if c[0] == "prompt"]) == 1


def test_first_brief_report_is_not_signed_out(world):
    started(world)
    stop(world, "Status: DONE")
    assert rw.send_brief(world.sd, "W1", brief(world), "Q1") == "Q1"


def test_states_blocks_logged_out_busy_worker(world, monkeypatch, capsys):
    busy(world)
    monkeypatch.setattr(rw.fr, "sync", lambda sd, wid: 0)
    stop(world, "Not logged in · Please run /login", t=2000)
    name = record(world)["name"]
    assert rw.states(world.sd) == {name: "blocked"}
    assert "claude1" in (world.sd / "room-skip.json").read_text()
    assert "claude1 is signed out on box" in capsys.readouterr().err
    assert rw.states(world.sd) == {name: "blocked"} and capsys.readouterr().err == ""


def test_states_leaves_working_and_reported_alone(world, monkeypatch):
    busy(world)
    monkeypatch.setattr(rw.fr, "sync", lambda sd, wid: 0)
    name = record(world)["name"]
    stop(world, "Not logged in · Please run /login", t=2000)
    world.fh.agent_map = {name: "working"}
    assert rw.states(world.sd) == {name: "working"}
    world.fh.agent_map = {name: "idle"}
    patch_record(world, sent=5000)  # the stop is before the send
    assert rw.states(world.sd) == {name: "idle"}
    patch_record(world, sent=1000)
    stop(world, "Status: DONE", t=3000)
    assert rw.states(world.sd) == {name: "idle"}


def test_wait_reports_blocked_ui_signed_out(world, monkeypatch, capsys):
    busy(world)
    monkeypatch.setattr(rw.fr, "sync", lambda sd, wid: 0)
    stop(world, LOGIN, t=2000)
    world.fh.screen = "> Read q.md\n  ⎿  " + LOGIN + "\n"
    out = fio.wait(world.sd, ["W1"], 60000)
    text = capsys.readouterr().out
    assert [r["status"] for r in out] == ["BLOCKED-UI"]
    assert "BLOCKED-UI" in text and "(signed out: account" in text and "ASKED" not in text


def test_placed_spawn_goes_local_on_logged_out_brief(world, capsys, monkeypatch):
    skips, local = [], []
    fleet.main(["on"]); capsys.readouterr()
    monkeypatch.setattr(fp, "enabled", lambda sd: True)
    monkeypatch.setattr(fp, "choose", lambda sd, role, project, now=None, brief=None: "box")
    monkeypatch.setattr(fp, "skip", lambda sd, label, why, minutes=10.0, now=None: skips.append((label, why)))
    real = fleet.spawn

    def spawn(sd, plan, tier, project, *a, **k):
        if k.get("machine"):
            return real(sd, plan, tier, project, *a, **k)
        local.append(k.get("role")); print("W2 local")
        return {"id": "W2"}
    monkeypatch.setattr(fleet, "spawn", spawn)
    sent, real_send = [], fio.send_brief
    monkeypatch.setattr(fio, "send_brief", lambda sd, wid, b, label="", **k: sent.append(wid) or (real_send(sd, wid, b, label, **k) if wid == "W1" else label))
    stop(world, LOGIN)  # W1's first brief turn ends on the sign-in stop
    assert fleet.main(["spawn", "--role", "research", "--brief", brief(world)]) == 0
    out = capsys.readouterr().out
    assert "placement: account claude1 skipped on box (not signed in there); local" in out and "W2 local" in out
    assert local == ["research"] and sent == ["W1", "W2"] and skips and "claude1 is not signed in on box" in skips[0][1]


def test_docs_name_1093():
    text = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "(#1093)" in text and "BLOCKED-UI" in text and "Login reached its time limit" in text
