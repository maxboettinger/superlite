# tests/scripts/test_lead_needs_decision_906.py
import json, sys
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402
import fleet_report  # noqa: E402
import metrics  # noqa: E402

JSON_TEXT = "Asked main.\n\nStatus: NEEDS_DECISION\n\n```json\n" + json.dumps({"status": "NEEDS_DECISION", "files": [], "tests": "", "red": "none - no test", "findings": [], "summary": "asks"}) + "\n```\n"
LEAD_LINE = "`Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|NEEDS_DECISION|BLOCKED>`"


def test_parse_json_needs_decision():
    r = fleet_report.parse(JSON_TEXT)
    assert r["status"] == "NEEDS_DECISION" and r["valid"] is True


def test_parse_text_needs_decision():
    assert fleet_report.parse("Wrote .superlite/question.json.\n\nStatus: NEEDS_DECISION")["status"] == "NEEDS_DECISION"


def test_metrics_status_of_needs_decision():
    assert metrics.status_of("x\nStatus: NEEDS_DECISION") == "NEEDS_DECISION"
    assert metrics.status_of("Status: NEEDS_CONTEXT") == "NEEDS_CONTEXT"


def test_lead_brief_line_lists_needs_decision(tmp_path):
    b = tmp_path / "lead.md"; b.write_text("do the plan\n")
    assert LEAD_LINE in fleet_report.brief_message("lead", str(b))


def test_implementer_line_unchanged(tmp_path):
    b = tmp_path / "w.md"; b.write_text("x\n")
    assert "`Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>`" in fleet_report.brief_message("implementer", str(b))


def test_planning_lead_keeps_planned(tmp_path):
    b = tmp_path / "lead.md"; b.write_text("plan it\nEnd: Status: DONE planned: x\n")
    assert fleet_report.PLANNED in fleet_report.brief_message("lead", str(b))


def test_report_contract_lead(tmp_path):
    assert fleet_io.report_contract({"role": "lead", "lead_sd": str(tmp_path)}) == fleet_report.LEAD_WORK


def _world(tmp_path, monkeypatch, with_q):
    sd = tmp_path / "proj" / ".superlite"; (sd / "fleet").mkdir(parents=True)
    lsd = tmp_path / "lead" / ".superlite"; lsd.mkdir(parents=True)
    if with_q: (lsd / "question.json").write_text("{}")
    w = {"name": "sl-proj-w4", "pane_id": "w6:p4", "account": "claude1", "agent": "superlite:lead", "tier": "sonnet", "state": "busy", "task": "lead-b", "started": 1000, "role": "lead", "lead_sd": str(lsd)}
    (sd / "fleet.json").write_text(json.dumps({"on": True, "label": "sl:x", "workspace_id": "w6", "root_pane": "w6:p1", "accounts": ["claude1"], "next": 5, "workers": {"W4": w}}))
    monkeypatch.setattr(fleet_io, "pane_label", lambda *a, **k: None)
    monkeypatch.setattr(fleet_io, "_release", lambda *a, **k: None)
    monkeypatch.setattr(fleet_io, "_tel_finish", lambda *a, **k: None)
    return sd, lsd, w


def test_wait_line_names_question(tmp_path, monkeypatch, capsys):
    sd, lsd, w = _world(tmp_path, monkeypatch, True)
    res = fleet_io._finish(sd, "W4", w, JSON_TEXT, "transcript")
    q = f"{lsd.resolve()}/question.json"
    assert capsys.readouterr().out.rstrip("\n").endswith(f" question={q}")
    assert res["question"] == q and fleet_io.wave_failure(res) is True


def test_wait_line_without_question_file(tmp_path, monkeypatch, capsys):
    sd, lsd, w = _world(tmp_path, monkeypatch, False)
    res = fleet_io._finish(sd, "W4", w, JSON_TEXT, "transcript")
    assert " question=" not in capsys.readouterr().out and "question" not in res
