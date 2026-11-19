# tests/scripts/test_fleet_not_run_807.py: a report naming checks it did not run shows on the wait line (#807)
import json
import pytest
from test_fleet_io import world, io  # noqa: F401
import fleet_report


def recs(world):
    return json.loads((world.sd / "fleet.json").read_text())["workers"]


def set_role(world, wid, role):
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text())
    d["workers"][wid]["role"] = role
    p.write_text(json.dumps(d))


def finish(world, wid, label, text):
    w = recs(world)[wid]
    w["task"] = label
    return io._finish(world.sd, wid, w, text, "transcript")


@pytest.mark.parametrize("text,want", [
    ("Not run: iOS simulator check - no simulator\nStatus: DONE", ["iOS simulator check - no simulator"]),
    ("- **Not run:** Mac launch - app did not build\nStatus: DONE", ["Mac launch - app did not build"]),
    ("Not run:\n- simulator check\n- Mac launch\nStatus: DONE", ["simulator check", "Mac launch"]),
    ("not run: `sl run_tests --full` - out of scope\r\nStatus: DONE", ["sl run_tests --full - out of scope"]),
    ("Not run: none.\nStatus: DONE", []),
    ("```\nNot run: inside a fence\n```\nStatus: DONE", []),
    ("The test did not run before the fix.\nStatus: DONE", []),
    (None, []),
])
def test_not_run_lines(text, want):
    assert fleet_report.not_run(text) == want


def test_done_with_unrun_check_becomes_done_with_concerns(world, capsys):
    set_role(world, "W1", "package-reviewer")
    r = finish(world, "W1", "rev-T3", "Reviewed T3.\nNot run: iOS simulator check - no simulator booted\nStatus: DONE")
    out = capsys.readouterr().out
    assert r["status"] == "DONE_WITH_CONCERNS" and "W1 rev-T3 DONE_WITH_CONCERNS findings=0 not_run=1 " in out
    rep = json.loads((world.sd / "fleet" / "reports" / "rev-T3.json").read_text())
    assert rep["status"] == "DONE_WITH_CONCERNS" and rep["status_reported"] == "DONE"
    assert rep["not_run"] == ["iOS simulator check - no simulator booted"]
    assert not io.wave_failure(r)


def test_approved_with_unrun_check_is_partial(world, capsys):
    set_role(world, "W1", "final-reviewer")
    r = finish(world, "W1", "FR1", "Not run: packet section 4 - file missing\nVerdict: APPROVED")
    assert r["status"] == "APPROVED" and r.get("partial") is True
    assert " findings=0 not_run=1 partial " in capsys.readouterr().out
    assert io.wave_failure(r)


def test_other_statuses_keep_their_word(world, capsys):
    set_role(world, "W1", "package-reviewer")
    r = finish(world, "W1", "rev-T4", "Not run: Mac launch - no GUI session\nStatus: BLOCKED")
    assert r["status"] == "BLOCKED" and "W1 rev-T4 BLOCKED findings=0 not_run=1 " in capsys.readouterr().out
    assert "status_reported" not in json.loads((world.sd / "fleet" / "reports" / "rev-T4.json").read_text())


@pytest.mark.parametrize("role", ["research", "writer"])
def test_research_and_writer_ignore_not_run_lines(world, capsys, role):
    set_role(world, "W1", role)
    r = finish(world, "W1", "R1", "Not run: nothing I could run here - read only\nStatus: DONE")
    assert r["status"] == "DONE" and "not_run" not in capsys.readouterr().out


def test_report_without_not_run_lines_is_unchanged(world, capsys):
    r = finish(world, "W1", "T3", "Status: DONE")
    out = capsys.readouterr().out
    assert r["status"] == "DONE" and " not_run=" not in out and "W1 T3 DONE findings=0 " in out
    rep = json.loads((world.sd / "fleet" / "reports" / "T3.json").read_text())
    assert "not_run" not in rep and "status_reported" not in rep


def test_package_reviewer_texts_carry_the_rule(world):
    set_role(world, "W1", "package-reviewer")
    assert io.report_contract(recs(world)["W1"]) == fleet_report.WORK + " " + fleet_report.NOT_RUN
    assert io.report_contract(recs(world)["W2"]) == fleet_report.WORK
    assert fleet_report.brief_message("package-reviewer", "/r/b.md") == f"Read /r/b.md and do what it says. {fleet_report.WORK} {fleet_report.NOT_RUN}"
    assert fleet_report.brief_message("fixer", "/r/b.md") == f"Read /r/b.md and do what it says. {fleet_report.WORK}"
    assert "`Not run: <check> - <why>`" in fleet_report.NOT_RUN and fleet_report.NOT_RUN.endswith("never DONE.")
