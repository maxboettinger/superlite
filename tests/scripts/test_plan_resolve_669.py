"""One plan resolution (#669): stable.json, then pool.json, then plan.md, through plan_tools."""
import json, sys
import pytest
from test_fleet import world  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
import dispatch  # noqa: E402
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import next_tasks as nt  # noqa: E402
import orchestrator  # noqa: E402
import state  # noqa: E402

HEAD = "# Plan\n**Goal:** test.\n\nGlobal constraints:\n- Every check runs on the build machine.\n\n"
TASKS = "### T1 first · Complexity 3 (O-1) · Est. context 40k\n**Owns:** src/a.py\n"
SECTION = "\n## Global constraints\n\nGlobal constraints:\n- Every check runs on the build machine.\n"


@pytest.fixture
def run(tmp_path):
    sd = tmp_path / "proj" / ".superlite"; sd.mkdir(parents=True)
    a = tmp_path / "a.md"; b = tmp_path / "b.md"
    a.write_text(HEAD + TASKS); b.write_text(HEAD + TASKS)
    (sd / "stable.json").write_text(json.dumps({"plan": str(a)}))
    (sd / "pool.json").write_text(json.dumps({"plan": str(b), "agents": []}))
    return sd, a, b


def _record(monkeypatch):
    got = []
    monkeypatch.setattr(orchestrator, "require", lambda plan, tool="": got.append(str(plan)) or 3)
    return got


def test_for_dispatch_default_prefers_stable_json(run, monkeypatch):
    sd, a, _ = run
    got = _record(monkeypatch)
    assert fleet.for_dispatch(sd, None, sd.parent) == 3
    assert got == [str(a)]


def test_for_review_default_prefers_stable_json(run, monkeypatch):
    sd, a, _ = run
    got = []
    def stop(plan, *args, **kw):
        got.append(str(plan)); raise SystemExit(0)
    monkeypatch.setattr(fleet_io, "review_brief", lambda sd_, plan, *a_, **k: stop(plan))
    (sd / "progress.md").write_text("- commit T1 abc1234 first\n")
    monkeypatch.setattr(fleet, "spawn", lambda *a_, **k: {"id": "W9"})
    with pytest.raises(SystemExit):
        fleet.for_review(sd, None, sd.parent, ["T1"])
    assert got == [str(a)]


def test_dispatch_default_prefers_stable_json(run, monkeypatch):
    sd, a, _ = run
    monkeypatch.setattr(state, "resolve", lambda *x, **k: sd)
    got = _record(monkeypatch)
    dispatch.main(["--pool", str(sd / "pool.json")])
    assert got == [str(a)]


def test_assign_default_prefers_stable_json(run, monkeypatch):
    sd, a, _ = run
    got = []
    def graph(plan):
        got.append(str(plan)); raise SystemExit(0)
    monkeypatch.setattr(nt, "taskgraph", graph)
    monkeypatch.setattr(nt, "parse_plan", lambda plan: {})
    with pytest.raises(SystemExit):
        assign.main(["--task", "T1", "--pool", str(sd / "pool.json")])
    assert got == [str(a)]


def test_dispatch_plan_md_fallback(tmp_path, monkeypatch):
    sd = tmp_path / "proj" / ".superlite"; sd.mkdir(parents=True)
    (sd / "plan.md").write_text(HEAD + TASKS)
    monkeypatch.setattr(state, "resolve", lambda *x, **k: sd)
    got = _record(monkeypatch)
    dispatch.main(["--pool", str(sd / "pool.json")])
    assert got == [str(sd / "plan.md")]


def test_dispatch_run_folder_without_plan_exits_2(tmp_path, capsys):
    sd = tmp_path / "empty" / ".superlite"; sd.mkdir(parents=True)
    assert dispatch.main(["--plan", str(sd)]) == 2
    assert "is a run folder with no plan file" in capsys.readouterr().err


def test_fleet_has_no_own_plan_file():
    assert not hasattr(fleet, "plan_file")


def test_brief_constraints_use_run_plan(world, monkeypatch):
    for n in ("stable.json", "pool.json"):
        (world.sd / n).unlink(missing_ok=True)
    (world.sd / "plan.md").write_text(HEAD + TASKS)
    fleet.main(["on"])
    for n in ("stable.json", "pool.json"):
        (world.sd / n).unlink(missing_ok=True)
    sent = []
    monkeypatch.setattr(fleet_io, "send_brief", lambda sd, wid, brief, label="", full=False, preface="": sent.append(open(brief).read()) or label)
    brief = world.proj / "b.md"; brief.write_text("do it\n")
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(world.sd)]) == 0
    assert sent == ["do it\n" + SECTION]
