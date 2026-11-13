"""red_gap reads a batch member's own red run; a batch implementer gets the per-task report contract (#736)."""
import json
import sys
from pathlib import Path
import pytest
from test_fleet_io import assistant, io, rec, stop_at, user, world  # noqa: F401  (world is a fixture)
import fleet_report

R1 = "tests (fast): 0 passed, 1 failed"
R2 = "tests (fast): 0 passed, 2 failed"
OWNS = ["src/a.py", "tests/test_a.py"]
GOOD = {"status": "DONE", "files": ["src/a.py"], "tests": "3 passed", "findings": [], "summary": "ok", "concerns": []}
FORMS = {
    "header": f"Red run:\n- T5: {R1}\n- T6: {R2}\n\nStatus: DONE\n",
    "indented": f"Red run:\n  T5: {R1}\n  T6: {R2}\nStatus: DONE\n",
    "lines": f"Red run T5: {R1}\nRed run T6: {R2}\nStatus: DONE\n",
    "json": "Status: DONE\n```json\n" + json.dumps({**GOOD, "red": {"T5": R1, "T6": R2}}) + "\n```\n",
}


def write(sd, report, label="T5,T6", role="implementer"):
    d = Path(sd) / "fleet" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    (d / "T5.json").write_text(json.dumps({**report, "label": label, "role": role}))


def put(sd, text):
    write(sd, fleet_report.parse(text, "T5,T6"))


def test_every_batch_form_proves_each_member(tmp_path):
    gaps = 0
    for text in FORMS.values():
        put(tmp_path, text)
        gaps += sum(io.red_gap(tmp_path, t, OWNS) is not None for t in ("T5", "T6"))
    assert gaps == 0


def test_member_none_with_test_files(tmp_path):
    write(tmp_path, {"red": "", "reds": {"T5": R1, "T6": "none - no test"}})
    assert io.red_gap(tmp_path, "T6", ["src/b.py", "tests/test_b.py"]) == "its report says `none - no test`, but it owns test files (tests/test_b.py)"
    assert io.red_gap(tmp_path, "T5", OWNS) is None


def test_missing_member_falls_back_to_red(tmp_path):
    write(tmp_path, {"red": "", "reds": {"T5": R1}})
    assert io.red_gap(tmp_path, "T6", OWNS) == "its report names no red run"
    write(tmp_path, {"red": "tests (fast): 0 passed, 3 failed", "reds": {"T5": R1}})
    assert io.red_gap(tmp_path, "T6", OWNS) is None


def test_report_without_reds(tmp_path):
    write(tmp_path, {"status": "DONE", "red": R1})
    assert io.red_gap(tmp_path, "T5", OWNS) is None and io.red_gap(tmp_path, "T6", OWNS) is None


def test_batch_contract():
    assert io.report_contract({"role": "implementer", "task": "T5,T6"}) == fleet_report.WORK_BATCH
    assert io.report_contract({"task": "T5,T6"}) == fleet_report.WORK_BATCH
    assert io.report_contract({"task": "T5"}) == fleet_report.WORK
    assert io.report_contract({"role": "fixer", "task": "T5,T6"}) == fleet_report.WORK
    assert io.report_contract({"role": "final-reviewer", "task": "T5,T6"}) == fleet_report.REVIEW


def test_ask_to_a_busy_batch_implementer_uses_the_batch_contract(world, tmp_path):
    io.send(world.sd, world.plan, "W1", ["T3", "T4"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant("Verify runs in the background."))
    stop_at(world, tr, sent + 10, last="")
    world.fh.states = [{"sl-proj-w1": "idle"}]
    io.wait(world.sd, ["W1"], 5000)
    ps = [c for c in world.fh.calls if c[0] == "prompt"]
    assert ps[-1][2] == io.ASK + " " + fleet_report.WORK_BATCH


def test_batch_line_names_the_per_task_form(world):
    msg = io.task_message(world.plan, ["T3", "T4"], "/sl/sl", "/sl")
    batch = [ln for ln in msg.splitlines() if ln.startswith("Batch:")]
    assert len(batch) == 1 and batch[0].endswith(
        " Report each task's red run on its own line, `Red run Tn: <summary line>`, and give the json block's `red` as an object keyed by task id.")
