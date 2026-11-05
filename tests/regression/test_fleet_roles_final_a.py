# tests/regression/test_fleet_roles_final_a.py: final review p2 findings (fleet gate verdict, findings root, layer pane close)
import json, sys, time, types
from pathlib import Path
import pytest
SC = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SC))
from test_final_review_check import big, metrics, repo, run  # noqa: F401,E402
from test_plan_tools import SCRIPTS, make_plan  # noqa: E402
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
import herdr_client as hc  # noqa: E402
import fleet_layer as fl  # noqa: E402

def ms(): return int((time.time() + 5) * 1000)
FR = "fleet:superlite:final-reviewer"

@pytest.mark.parametrize("rec", [
    {"ev": "launch", "type": FR, "t": 0},
    {"ev": "stop", "type": FR, "last": "NEEDS_CONTEXT"},
])
def test_fleet_gate_needs_a_verdict_stop(repo, rec):
    big(repo)
    metrics(repo, {**rec, "t": ms()})
    assert json.loads(run(repo).stdout)["decision"] == "block"

def test_fleet_gate_passes_on_verdict_stop(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "type": FR, "t": ms(), "last": "Verdict: APPROVED"})
    assert run(repo).stdout == ""

def test_findings_root_is_the_git_root_with_state_dir_outside(tmp_path):
    root = (tmp_path / "repo").resolve(); (root / ".git").mkdir(parents=True)
    sd = root / "sub" / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"}])
    rp = sd / "fleet" / "reports" / "FR1.json"
    rp.write_text(json.dumps({"id": "W4", "label": "FR1", "findings": [{"file": str(root / "src" / "a.py"), "line": 1, "problem": "p", "fix": "x", "tier": 1}]}))
    lines = findings.route(sd, plan, [str(rp)], "/sl/sl")
    assert lines and lines[0].endswith("files=src/a.py task=T1")

def test_layer_closes_the_pane_when_run_in_pane_fails(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"; sd = root / ".superlite"; sd.mkdir(parents=True)
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}, "next": 5}))
    (root / "scripts").mkdir(); (root / "scripts" / "test_layers.py").write_text("#\n")
    monkeypatch.setattr(fl.fleet, "choose_account", lambda *a: ("claude3", "/u/.c3", "claude3"), raising=False)
    def open_pane(sd_, wid, cwd, env, record):
        d = json.loads((sd / "fleet.json").read_text()); d["workers"][wid] = {**record, "pane_id": "w6:p2"}
        (sd / "fleet.json").write_text(json.dumps(d)); return "w6:p2"
    monkeypatch.setattr(fl.fleet, "open_pane", open_pane, raising=False)
    closed = []
    def boom(p, c): raise hc.HerdrError("not_found", "gone")
    monkeypatch.setattr(fl, "hc", types.SimpleNamespace(run_in_pane=boom, close_pane=lambda p: closed.append(p)))
    with pytest.raises(SystemExit):
        fl.run(sd, "evals", root, env={"HOME": "/u"})
    assert closed == ["w6:p2"]
