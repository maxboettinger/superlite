# tests/scripts/test_plan_folder_668.py: --plan <run folder> resolves to the run's plan file (#668)
import json, sys, types
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402
import orchestrator  # noqa: E402
import next_tasks  # noqa: E402
import fleet_io  # noqa: E402


@pytest.fixture
def run(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    plan = make_plan(proj, [{"id": "T1", "title": "a", "owns": "src/a.py"}])
    monkeypatch.chdir(proj)
    return types.SimpleNamespace(proj=proj, sd=sd, plan=plan)


def test_run_plan_order(run, tmp_path, monkeypatch):
    sd = run.sd
    assert plan_tools.run_plan(sd) is None
    (sd / "plan.md").write_text("x")
    assert plan_tools.run_plan(sd) == sd / "plan.md"
    other = run.proj / "pool-plan.md"; other.write_text("p")
    (sd / "pool.json").write_text(json.dumps({"plan": str(other)}))
    assert plan_tools.run_plan(sd) == other
    (sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    assert plan_tools.run_plan(sd) == run.plan
    (sd / "stable.json").write_text(json.dumps({"plan": "gone.md"}))  # missing: skipped
    assert plan_tools.run_plan(sd) == other
    rel = run.proj / "docs" / "plans" / "p.md"; rel.parent.mkdir(parents=True); rel.write_text("q")
    (sd / "stable.json").write_text(json.dumps({"plan": "docs/plans/p.md"}))
    monkeypatch.chdir(tmp_path)  # cwd lacks it: resolves against sd.parent
    assert plan_tools.run_plan(sd) == rel


def test_resolve_plan_file_folder_missing(run):
    assert plan_tools.resolve_plan(str(run.plan)) == Path(str(run.plan))
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    assert plan_tools.resolve_plan(str(run.sd)) == run.plan
    with pytest.raises(plan_tools.PlanError) as e:
        plan_tools.resolve_plan("nope.md")
    assert str(e.value) == "plan not found: nope.md"


def test_plan_load_folder(run):
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    assert plan_tools.Plan.load(str(run.sd)).path == run.plan


@pytest.mark.parametrize("eq", [False, True])
def test_review_commands_get_file(run, monkeypatch, eq):
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    import pt_review
    seen = []
    monkeypatch.setattr(pt_review, "main", lambda argv: seen.append(argv) or 0)
    args = [f"--plan={run.sd}"] if eq else ["--plan", str(run.sd)]
    assert plan_tools.main(["packet", *args]) == 0
    assert seen == [["packet", "--plan", str(run.plan)]]


def test_cli_folder_without_plan_exits_2(tmp_path, capsys):
    sd = tmp_path / ".superlite"; sd.mkdir()
    assert plan_tools.main(["taskgraph", "--plan", str(sd)]) == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1 and err.startswith("error: --plan ")


def test_orchestrator_plan_file_unchanged(run):
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    other = run.proj / "o.md"; other.write_text("o")
    assert orchestrator.plan_file(run.sd, str(other)) == other
    assert orchestrator.plan_file(run.sd) == run.plan


def test_next_tasks_default_plan(run, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(run.sd))
    assert next_tasks.default_plan() == ".superlite/plan.md"
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan), "stable": ["T1"]}))
    assert next_tasks.default_plan() == str(run.plan)
    next_tasks.main([])
    assert "T1" in capsys.readouterr().out


def test_fleet_send_folder_plan(run, monkeypatch, capsys):
    (run.sd / "stable.json").write_text(json.dumps({"plan": str(run.plan)}))
    (run.sd / "fleet.json").write_text(json.dumps({"on": True, "label": "sl:x", "workspace_id": "w6", "root_pane": "w6:p1", "accounts": ["claude1"], "next": 2,
        "workers": {"W1": {"name": "sl-proj-w1", "pane_id": "w6:p1", "account": "claude1", "agent": "superlite:implementer", "tier": "sonnet", "state": "ready", "task": None, "started": 1000}}}))
    sent = []
    monkeypatch.setattr(fleet_io, "_prompt", lambda name, msg: sent.append(msg))
    monkeypatch.setattr(fleet_io, "pane_label", lambda *a, **k: None)
    assert fleet_io.main(["send", "W1", "T1", "--plan", str(run.sd)]) == 0
    assert "# Task T1" in sent[0]
    empty = run.proj / "empty" / ".superlite"; empty.mkdir(parents=True)
    (empty / "fleet.json").write_text((run.sd / "fleet.json").read_text())
    assert fleet_io.main(["send", "W1", "T1", "--plan", str(empty)]) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err and len(err.strip().splitlines()) == 1 and err.startswith("error: --plan ")
