import json
import sys
from pathlib import Path
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_io  # noqa: E402
import fleet_lead as fl  # noqa: E402
import machine_load  # noqa: E402
import state  # noqa: E402
import trees  # noqa: E402

SL = str(Path(fl.__file__).resolve().parent / "sl")


@pytest.fixture
def env(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        (d / ".git").mkdir(parents=True)
    (a / ".superlite").mkdir()
    (a / ".superlite" / "fleet.json").write_text(json.dumps({"on": True, "workers": {}}))
    plan = b / "docs" / "plans" / "p.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("%% taskgraph\n# p\n")
    calls = {"spawn": [], "send": [], "stop": []}

    def spawn(sd, wt, **kw):
        calls["spawn"].append((sd, wt, kw))
        return {"id": "W2", "lead_sd": str(b / ".superlite")}

    monkeypatch.setattr(fl, "spawn_lead", spawn)
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a: calls["send"].append(a))
    monkeypatch.setattr(fleet, "stop", lambda *a, **k: calls["stop"].append(a))
    monkeypatch.setattr(machine_load, "gate", lambda *a, **k: None)
    monkeypatch.setattr(trees, "disk_gate", lambda p: ("ok", "disk: fine"))
    return type("E", (), {"a": a, "b": b, "sd": a / ".superlite", "plan": plan, "calls": calls})


def _workers(env, ws):
    (env.sd / "fleet.json").write_text(json.dumps({"on": True, "workers": ws}))


def test_plan_brief_names_plan_and_steps():
    t = fl.plan_brief(Path("/r/b/docs/plans/p.md"), Path("/r/b"), "/s/sl")
    for s in ("/r/b/docs/plans/p.md", "`/s/sl orchestrator set ai --plan .superlite`, then `/s/sl fleet on --plan .superlite`",
              "Status: NEEDS_DECISION", "Never push, merge", "/s/sl fleet wait --wave", "/r/b/.superlite/simulators.txt"):
        assert s in t
    assert "backlog ship" not in t


def test_lead_argv_without_ship():
    a = fl.lead_argv("/s/sl", "opus", ship=False)
    assert "--allowedTools" not in a and "Bash(maxapp ship *)" not in a and "Bash(/s/sl backlog ship *)" not in a
    b = fl.lead_argv("/s/sl", "opus")
    assert "--allowedTools" in b and "Bash(maxapp ship *)" in b and "Bash(/s/sl backlog ship *)" in b


def test_start_refuses_missing_plan(env, capsys):
    assert fl.start_plan_lead(env.sd, str(env.a / ".." / "nope.md")) == (2, None)
    err = capsys.readouterr().err
    assert "error: --role lead --plan" in err and "not found" in err
    assert not env.calls["spawn"]


def test_start_refuses_outside_git(env, capsys, monkeypatch):
    monkeypatch.setattr(state, "git_root", lambda p: None)
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (2, None)
    assert "not inside a git checkout" in capsys.readouterr().err


def test_start_refuses_own_worktree(env, capsys):
    p = env.a / "docs" / "plans" / "x.md"
    p.parent.mkdir(parents=True)
    p.write_text("x")
    assert fl.start_plan_lead(env.sd, str(p)) == (2, None)
    assert "this run's own worktree" in capsys.readouterr().err


def test_start_refuses_second_live_lead(env, capsys):
    w = {"role": "lead", "state": "busy", "lead_sd": str(env.b / ".superlite")}
    _workers(env, {"W1": w})
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (2, None)
    assert f"error: W1 already leads {env.b}; stop it first: sl fleet stop W1" in capsys.readouterr().err
    _workers(env, {"W1": {**w, "state": "stopped"}})
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (0, "W2")


def test_start_refuses_non_plan_without_brief(env, capsys):
    assert fl.start_plan_lead(env.sd, str(env.b)) == (2, None)
    assert "pass a plan file, or --brief F" in capsys.readouterr().err


def test_start_blocked_by_gate_writes_nothing(env, capsys, monkeypatch):
    monkeypatch.setattr(machine_load, "gate", lambda *a, **k: "memory pressure high")
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (3, None)
    assert f"BLOCKED: lead for {env.b} not started: memory pressure high; rerun, or --over-limit" in capsys.readouterr().out
    assert not (env.b / ".superlite" / "briefs" / "lead.md").exists() and not env.calls["spawn"]
    monkeypatch.setattr(trees, "disk_gate", lambda p: ("refuse", "disk: 12 GB free"))
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (3, None)
    assert f"BLOCKED: lead for {env.b} not started: 12 GB free" in capsys.readouterr().out
    assert not (env.b / ".superlite" / "briefs" / "lead.md").exists() and not env.calls["spawn"]


def test_start_writes_brief_and_sends(env, capsys):
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (0, "W2")
    brief = env.b / ".superlite" / "briefs" / "lead.md"
    assert brief.read_text() == fl.plan_brief(env.plan.resolve(), env.b.resolve(), SL)
    _, _, kw = env.calls["spawn"][0]
    assert kw["plan"] == env.plan.resolve() and kw["ship"] is False
    assert env.calls["send"] == [(env.sd, "W2", str(brief), "lead-b")]
    b = env.b
    assert (f"W2 lead {b}: progress: sl fleet status; run state: sl status --plan {b}/.superlite; wait: sl fleet wait W2 "
            "(returns at DONE, NEEDS_DECISION or BLOCKED); answer: sl fleet send W2 --text T") in capsys.readouterr().out


def test_start_with_brief_sends_it_unchanged(env, tmp_path):
    f = tmp_path / "brief.md"
    f.write_text("do it")
    assert fl.start_plan_lead(env.sd, str(env.b), brief=str(f)) == (0, "W2")
    assert env.calls["send"][0][2] == str(f.resolve())
    assert not (env.b / ".superlite" / "briefs" / "lead.md").exists()


def test_start_brief_not_sent_stops_lead(env, capsys, monkeypatch):
    def boom(*a):
        raise fleet.hc.HerdrError("x", "pane gone")
    monkeypatch.setattr(fleet_io, "send_brief", boom)
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (3, None)
    assert env.calls["stop"] == [(env.sd, ["W2"])]
    assert "BLOCKED: W2 lead-b not sent (pane gone); lead stopped" in capsys.readouterr().out


def test_start_spawn_blocked_passes_exit(env, monkeypatch):
    def boom(*a, **k):
        raise SystemExit(3)
    monkeypatch.setattr(fl, "spawn_lead", boom)
    assert fl.start_plan_lead(env.sd, str(env.plan)) == (3, None)


@pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")
def test_spawn_lead_records_plan(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"
    wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"}, plan="/r/b/p.md", ship=False)
    rec = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert rec["plan"] == str(Path("/r/b/p.md").resolve())
    assert "--allowedTools" not in rec["launch"]["argv"]
