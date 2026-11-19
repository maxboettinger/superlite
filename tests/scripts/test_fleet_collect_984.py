# tests/scripts/test_fleet_collect_984.py: `sl fleet collect Wn` collects a BLOCKED remote write worker's saved report again (#984)
import json
import sys
from pathlib import Path

import pytest

from test_fleet_remote_collect import env, host_snapshot, frc, fs, NAME, REF  # noqa: F401
from test_fleet_remote_collect_953 import HOST_TREE
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet as fleet_mod  # noqa: E402
import fleet_io as fio  # noqa: E402

NO_RECORD = "remote worker W1 left no snapshot: no stop record of its task reached this machine within 45 s"
DONE = 'All done.\n\n```json\n{"status": "DONE", "files": ["src/a.py"], "concerns": []}\n```\n\nStatus: DONE\n'


def seed(env, state="ready", task=None, last="T1", one_turn=False, machine="box", write=True, stops=(), collected=None, md=DONE):
    remote = {"label": "box", "name": NAME, "project": str(env.proj), "start": env.start, "snapshot_ref": REF, "write": write,
              "owns": ["src/*.py"], "tree": HOST_TREE, "sd": HOST_TREE + "/.superlite"}
    rec = {"state": state, "role": "implementer", "sent": 2000, "task": task, "last_task": last, "one_turn": one_turn}
    if machine:
        rec.update(machine=machine, remote=remote)
    fs.save(env.sd, {**fs.default(), "workers": {"W1": rec}})
    d = env.sd / "remote" / "W1"
    d.mkdir(parents=True, exist_ok=True)
    (d / "metrics.jsonl").write_text("".join(json.dumps({"ev": "stop", "agent_id": "W1", **s}) + "\n" for s in stops))
    rd = env.sd / "fleet" / "reports"
    rd.mkdir(parents=True, exist_ok=True)
    if md is not None:
        (rd / "T1.md").write_text(md)
    j = {"status": "BLOCKED", "findings": [], "concerns": [NO_RECORD], "id": "W1", "label": "T1", "role": "implementer", "source": "transcript", "report": str(rd / "T1.md")}
    if collected:
        j["collected"] = collected
    (rd / "T1.json").write_text(json.dumps(j))
    return rd


@pytest.fixture
def calls(monkeypatch):
    out = {"stop": [], "worker": []}
    monkeypatch.setattr(fio, "_remote", lambda: type("R", (), {"stop": staticmethod(lambda sd, wid: out["stop"].append(wid))}))
    monkeypatch.setattr(fio, "_stop_worker", lambda sd, wid: out["worker"].append(wid))
    return out


def patch_sync(env, monkeypatch, snapshot=True):
    sha = host_snapshot(env, {"src/a.py": "two\n"}) if snapshot else None
    calls = []

    def sync(sd, wid):
        calls.append(wid)
        if snapshot and len(calls) == 1:
            with open(env.sd / "remote" / "W1" / "metrics.jsonl", "a") as fh:
                fh.write(json.dumps({"ev": "stop", "agent_id": "W1", "t": 2600, "snapshot": sha}) + "\n")
        return 0
    monkeypatch.setattr(frc.fr, "sync", sync)
    t = [100.0]
    monkeypatch.setattr(frc, "now_s", lambda: t[0])
    monkeypatch.setattr(frc, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    return sha, calls


def test_collect_brings_late_snapshot_home(env, monkeypatch, calls, capsys):
    rd = seed(env)
    sha, sync_calls = patch_sync(env, monkeypatch)
    md = (rd / "T1.md").read_text()
    assert fio.recollect(env.sd, "W1") == 0
    assert capsys.readouterr().out == f"W1 T1 DONE findings=0 {rd}/T1.json\n"
    j = json.loads((rd / "T1.json").read_text())
    assert j["status"] == "DONE" and "concerns" not in j or not j.get("concerns")
    assert j["collected"]["sha"] == sha
    assert fs.load(env.sd)["workers"]["W1"]["remote"]["collected"] == sha
    assert calls["stop"] == ["W1"] and (rd / "T1.md").read_text() == md


def test_collect_still_blocked_exit_3(env, monkeypatch, calls, capsys):
    rd = seed(env)
    patch_sync(env, monkeypatch, snapshot=False)
    assert fio.recollect(env.sd, "W1") == 3
    assert capsys.readouterr().out == f"W1 T1 BLOCKED findings=0 concerns=1 {rd}/T1.json\n"
    j = json.loads((rd / "T1.json").read_text())
    assert len(j["concerns"]) == 1 and "no stop record of its task" in j["concerns"][0] and "sl fleet collect W1" in j["concerns"][0]
    assert calls["stop"] == [] and calls["worker"] == []


def test_collect_already_collected(env, monkeypatch, calls, capsys):
    rd = seed(env, collected={"applied": [], "skipped": [], "sha": "abc"})
    sha, sync_calls = patch_sync(env, monkeypatch)
    assert fio.recollect(env.sd, "W1") == 0
    assert capsys.readouterr().out == f"W1 T1 already collected: {rd}/T1.json\n"
    assert sync_calls == [] and calls["stop"] == []


def test_collect_one_turn_worker_stopped(env, monkeypatch, calls, capsys):
    seed(env, one_turn=True)
    patch_sync(env, monkeypatch)
    assert fio.recollect(env.sd, "W1") == 0
    assert calls["worker"] == ["W1"]


@pytest.mark.parametrize("kw,wid,msg", [
    ({}, "W9", "error: unknown worker W9"),
    ({"machine": None}, "W1", "error: W1 is not a remote write worker: nothing to collect"),
    ({"state": "busy", "task": "T1"}, "W1", "error: W1 is busy on T1; run sl fleet wait W1 first"),
    ({"state": "stopped"}, "W1", "error: W1 is stopped: its remote tree is gone"),
    ({"last": None}, "W1", "error: W1 has no collected report; run sl fleet wait W1 first"),
    ({"md": None}, "W1", "error: W1 T1: no report file in {rd}"),
    ({"md": "Need more.\n\nStatus: NEEDS_CONTEXT\n"}, "W1", "error: W1 T1 is NEEDS_CONTEXT: nothing to collect"),
])
def test_collect_refusals(env, monkeypatch, calls, capsys, kw, wid, msg):
    rd = seed(env, **kw)
    before = {p.name: p.read_text() for p in rd.iterdir()}
    sha, sync_calls = patch_sync(env, monkeypatch)
    assert fio.recollect(env.sd, wid) == 2
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err == msg.format(rd=rd) + "\n"
    assert {p.name: p.read_text() for p in rd.iterdir()} == before
    assert sync_calls == [] and calls["stop"] == []


def test_fleet_cli_collect(env, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(fio, "recollect", lambda sd, wid: seen.append(wid) or 3)
    seed(env)
    assert fleet_mod.main(["collect", "W1", "--plan", str(env.sd)]) == 3
    assert seen == ["W1"]
    with pytest.raises(SystemExit):
        fleet_mod.main(["--help"])
    assert "collect" in capsys.readouterr().out


def test_docs_name_fleet_collect():
    fleet = (Path(__file__).resolve().parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "`fleet collect Wn [--plan P]`" in fleet
    assert "(on, off, status, spawn, placement, stop, name, report, collect, send, keys, wait, run, restore, resume)" in fleet
