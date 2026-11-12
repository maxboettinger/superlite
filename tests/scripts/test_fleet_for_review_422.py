# tests/scripts/test_fleet_for_review_422.py
"""`fleet spawn --for-review Tn.. | --package X` (#422): brief file, package-reviewer worker, send, review list; `--for-dispatch` prints `review:` hints."""
import json, sys
import pytest
from test_fleet import FakeHerdr, world  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as fio  # noqa: E402
import fleet_state as fs  # noqa: E402

PLAN = """# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T3 --> T4
```

## cli

### T3 first · Complexity 3 (O-1) · Est. context 40k
**Owns:** src/a.py

## Core lib

### T4 second · Complexity 3 (O-1) · Est. context 40k
**Owns:** src/b.py
"""
PLAN2 = PLAN.replace("## cli", "## Core lib", 1).replace("## Core lib\n\n### T4", "## other\n\n### T4")  # T3 and T4 in different sections


@pytest.fixture
def rw(world, monkeypatch, capsys):
    """Plan with sections, T3 committed; spawn and send_brief faked."""
    plan = world.proj / "rplan.md"; plan.write_text(PLAN)
    fleet.main(["on"]); capsys.readouterr()
    sd = world.sd
    (sd / "progress.md").write_text("- commit T3 abc1234 first\n")
    r = type("R", (), {})(); r.sd, r.plan, r.spawns, r.sends, r.err, r.briefs = sd, plan, [], [], None, []; r.gates = []
    def spawn(sd_, plan_, tier, project, cfg=None, env=None, role="implementer", over=False, machine_wait=100.0):
        r.spawns.append(role); r.gates.append((over, machine_wait))
        with fs.locked(sd_):
            d = fs.load(sd_); d["workers"]["W4"] = {"id": "W4", "role": role, "state": "ready"}; fs.save(sd_, d)
        return {"id": "W4"}
    def send_brief(sd_, wid, brief, label=""):
        if r.err: raise r.err
        r.sends.append((sd_, wid, brief, label)); return label
    monkeypatch.setattr(fleet, "spawn", spawn); monkeypatch.setattr(fio, "send_brief", send_brief)
    def fake_brief(sd_, plan_, tasks, sl, root, package=None):
        r.briefs.append((list(tasks), package)); return f"BRIEF {tasks} {package}\n"
    monkeypatch.setattr(fio, "review_brief", fake_brief)
    r.world = world
    return r


def _go(r, *args):
    return fleet.main(["spawn", *args, "--plan", str(r.plan)])


def test_for_review_passes_machine_flags(rw):
    assert _go(rw, "--for-review", "T3", "--over-limit", "--machine-wait", "7") == 0
    assert rw.gates == [(True, 7.0)]


def test_for_review_spawns_a_package_reviewer_and_sends_the_brief(rw, capsys):
    assert _go(rw, "--for-review", "T3") == 0
    assert rw.spawns == ["package-reviewer"]
    f = rw.sd / "briefs" / "review-T3.md"
    assert f.read_text() == "BRIEF ['T3'] None\n"
    assert rw.sends == [(rw.sd, "W4", str(f), "review-T3")]
    assert rw.sd.resolve() == rw.sends[0][0].resolve()


def test_for_review_ids_by_comma_and_space(rw):
    (rw.plan).write_text(PLAN)
    (rw.sd / "progress.md").write_text("- commit T3 abc1234 a\n- commit T4 bcd2345 b\n")
    assert _go(rw, "--for-review", "T3,T4") == 0
    assert _go(rw, "--for-review", "T3", "T4") == 0
    assert [b[0] for b in rw.briefs] == [["T3", "T4"], ["T3", "T4"]]
    assert [s[3] for s in rw.sends] == ["review-T3,T4"] * 2
    assert (rw.sd / "briefs" / "review-T3-T4.md").is_file()


def test_for_review_package_reviews_its_committed_tasks(rw):
    rw.plan.write_text(PLAN.replace("## cli", "## Core lib", 1).replace("## Core lib\n\n### T4", "## other\n\n### T4"))
    assert _go(rw, "--package", "Core lib") == 0
    assert _go(rw, "--for-review", "--package", "Core lib") == 0
    assert rw.briefs == [(["T3"], "Core lib")] * 2
    assert rw.sends[0][3] == "review-core-lib" and rw.sends[0][2].endswith("review-core-lib.md")


def test_for_review_refuses_unknown_and_uncommitted(rw, capsys):
    capsys.readouterr()
    assert _go(rw, "--for-review", "T9") == 2
    assert "error: unknown task T9" in capsys.readouterr().err
    assert _go(rw, "--package", "nope") == 2
    assert "error: unknown package nope (packages: cli, Core lib)" in capsys.readouterr().err
    assert _go(rw, "--for-review", "T4") == 3
    assert "BLOCKED: T4 has no commit line in progress.md; run commit_task T4 first" in capsys.readouterr().out
    assert _go(rw, "--package", "Core lib") == 3
    assert "BLOCKED: no committed task in package Core lib" in capsys.readouterr().out
    assert rw.spawns == [] and rw.sends == []


def test_for_review_takes_ids_or_package_not_both(rw, capsys):
    capsys.readouterr()
    assert _go(rw, "--for-review", "T3", "--package", "cli") == 2
    assert "error: --for-review takes task ids or --package, not both" in capsys.readouterr().err
    assert _go(rw, "--for-review") == 2
    assert "error: --for-review needs task ids or --package" in capsys.readouterr().err
    assert rw.spawns == []


def test_for_review_records_the_reviewed_tasks_after_the_send(rw, capsys, monkeypatch):
    monkeypatch.setattr(fleet, "stop", lambda *a, **k: None)
    assert _go(rw, "--for-review", "T3") == 0
    assert json.loads((rw.sd / "fleet.json").read_text())["workers"]["W4"]["review"] == ["T3"]
    d = fs.load(rw.sd); d["workers"].pop("W4"); fs.save(rw.sd, d)
    rw.err = fio.hc.HerdrError("agent_prompt_stalled", "stalled")
    capsys.readouterr()
    assert _go(rw, "--for-review", "T3") == 3
    assert "BLOCKED: review-T3 not sent (stalled)" in capsys.readouterr().out
    assert "review" not in json.loads((rw.sd / "fleet.json").read_text())["workers"]["W4"]


def test_for_review_stops_the_reviewer_when_the_send_fails(rw, capsys, monkeypatch):
    stopped = []
    monkeypatch.setattr(fleet, "stop", lambda sd_, ids=None, *a, **k: stopped.append(list(ids)))
    rw.err = fio.hc.HerdrError("agent_prompt_stalled", "stalled")
    capsys.readouterr()
    assert _go(rw, "--for-review", "T3") == 3
    assert "BLOCKED: review-T3 not sent (stalled)" in capsys.readouterr().out
    assert stopped == [["W4"]]
    assert "review" not in json.loads((rw.sd / "fleet.json").read_text())["workers"]["W4"]


def test_for_dispatch_prints_review_hints(rw, capsys, monkeypatch):
    import dispatch
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: ([], {}))
    monkeypatch.setattr(fio, "review_hints", lambda sd, plan: [("T3", ["Complexity 6", "seam T1↔T3"])])
    capsys.readouterr()
    assert _go(rw, "--for-dispatch") == 0
    sl = str(fio.HERE / "sl")
    assert f"review: T3 (Complexity 6; seam T1↔T3); run {sl} fleet spawn --for-review T3 --plan {rw.plan}" in capsys.readouterr().out
    def bad(sd, plan): raise ValueError("bad")
    monkeypatch.setattr(fio, "review_hints", bad)
    assert _go(rw, "--for-dispatch") == 0
    assert "warning: no review hints (bad)" in capsys.readouterr().err
