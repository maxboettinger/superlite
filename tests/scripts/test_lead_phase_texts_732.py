# tests/scripts/test_lead_phase_texts_732.py
"""Texts to a lead name its phase's statuses; the READY resend sends the lead's own brief (#732)."""
import json
import os
import sys

import pytest

from test_fleet_io import io, world  # noqa: F401
from test_fleet_io_b87 import lead, script
from test_fleet_restore_577 import fr, w, worker  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import backlog_run as br  # noqa: E402
import fleet_report  # noqa: E402

pytestmark = pytest.mark.skipif(os.environ.get("SUPERLITE_REAL") == "1", reason="scripted herdr replies")
PLAN_BRIEF = "# Lead brief: B1 (x)\n" + bb.PLAN_END + "\n"
BUILD_BRIEF = "# Lead brief: B1 (x)\nEnd: Status: DONE once merge printed shipped; otherwise Status: BLOCKED with the reason.\n"


def as_lead(world, last, name="lead.md", text=PLAN_BRIEF, record=True):
    """W1 is a lead whose briefs/lead.md is a planning brief; NAME holds TEXT; RECORD stores NAME as the record's brief."""
    lsd = lead(world, last)
    (lsd / "briefs" / "lead.md").write_text(PLAN_BRIEF, encoding="utf-8")
    p = (lsd / "briefs" / name).resolve()
    p.write_text(text, encoding="utf-8")
    if record:
        fj = json.loads((world.sd / "fleet.json").read_text())
        fj["workers"]["W1"]["brief"] = str(p)
        (world.sd / "fleet.json").write_text(json.dumps(fj))
    return p


def rec(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def test_report_contract_by_role(tmp_path):
    plan = tmp_path / "lead.md"
    plan.write_text(PLAN_BRIEF, encoding="utf-8")
    assert io.report_contract({"role": "layer"}) == ""
    assert io.report_contract({"role": "final-reviewer", "brief": str(plan)}) == fleet_report.REVIEW
    assert io.report_contract({}) == fleet_report.WORK
    for role in ("implementer", "research", "fixer"):
        assert io.report_contract({"role": role, "brief": str(plan)}) == fleet_report.WORK


def test_lead_brief_and_contract_follow_the_phase(tmp_path):
    briefs = tmp_path / ".superlite" / "briefs"
    briefs.mkdir(parents=True)
    plan, build = briefs / "lead.md", briefs / "lead-build.md"
    plan.write_text(PLAN_BRIEF, encoding="utf-8")
    build.write_text(BUILD_BRIEF, encoding="utf-8")
    lsd = str(tmp_path / ".superlite")
    assert io.lead_brief({"role": "lead", "lead_sd": lsd, "brief": str(build)}) == build
    assert io.report_contract({"role": "lead", "lead_sd": lsd, "brief": str(build)}) == fleet_report.WORK
    assert io.report_contract({"role": "lead", "lead_sd": lsd, "brief": str(plan)}) == fleet_report.PLANNED
    assert io.lead_brief({"role": "lead", "lead_sd": lsd}) == plan
    assert io.lead_brief({"role": "lead", "lead_sd": lsd, "brief": str(briefs / "gone.md")}) == plan
    assert io.report_contract({"role": "lead", "lead_sd": lsd}) == fleet_report.PLANNED
    assert io.lead_brief({"role": "lead"}) is None
    assert io.lead_brief({"role": "lead", "lead_sd": "", "brief": str(tmp_path / "gone.md")}) is None
    assert io.report_contract({"role": "lead"}) == fleet_report.WORK


def test_send_text_to_planning_lead_names_done_planned(world):
    as_lead(world, "Status: DONE")
    records = script(world, "ok")
    text = br.PLAN_FIX.format(plan="docs/plans/p.md", errs="lint failed")
    io.send_text(world.sd, "W1", text)
    assert records == [text + "\n\n" + fleet_report.PLANNED]


def test_send_text_to_build_lead_keeps_work(world):
    as_lead(world, "Status: DONE", "lead-build.md", BUILD_BRIEF)
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records == ["go on\n\n" + fleet_report.WORK]


def test_ready_resend_sends_the_build_brief(world, capsys):
    p = as_lead(world, "READY", "lead-build.md", BUILD_BRIEF)
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records == [f"Read {p} and do what it says. {fleet_report.WORK}"]
    assert "W1 brief resent (its last stop said only READY)" in capsys.readouterr().out
    assert rec(world)["brief"] == str(p) and rec(world)["state"] == "busy"


def test_ready_resend_to_planning_lead_names_done_planned(world):
    p = as_lead(world, "READY")
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records == [f"Read {p} and do what it says. {fleet_report.PLANNED}"]


def test_ready_resend_without_a_recorded_brief_uses_lead_md(world):
    p = as_lead(world, "READY", record=False)
    records = script(world, "ok")
    io.send_text(world.sd, "W1", "go on")
    assert records == [f"Read {p} and do what it says. {fleet_report.PLANNED}"]


@pytest.mark.parametrize("name,text,want", [("lead.md", PLAN_BRIEF, "PLANNED"), ("lead-build.md", BUILD_BRIEF, "WORK")])
def test_restore_continue_names_the_lead_phase_contract(w, name, text, want):
    lsd = w.sd.parent / "wt" / ".superlite"
    (lsd / "briefs").mkdir(parents=True)
    (lsd / "briefs" / "lead.md").write_text(PLAN_BRIEF, encoding="utf-8")
    p = lsd / "briefs" / name
    p.write_text(text, encoding="utf-8")
    w.save({"W1": worker(name="sl-a-lead", role="lead", agent="lead", lead_sd=str(lsd), session="ls1", pane_id="w6:p1", brief=str(p))})
    lines, blocked = w.run()
    assert not blocked and any(x.startswith("W1 restored") and x.endswith("busy, continued") for x in lines)
    prompt = next(c for c in w.fake.calls if c[0] == "prompt" and c[1] == "sl-a-lead")[2]
    assert prompt.startswith(fr.LEAD_CONTINUE) and prompt.endswith(fr.LEAD_TAIL + "\n\n" + getattr(fleet_report, want))
    assert w.data()["workers"]["W1"]["brief"] == str(p)
