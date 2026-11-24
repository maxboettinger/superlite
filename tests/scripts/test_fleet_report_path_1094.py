"""fleet spawn refuses a brief that names the worker's own report file, which fleet wait overwrites with its reply (#1094)."""
import json

import pytest
from test_fleet import world, SCRIPTS  # noqa: F401
import fleet  # noqa: E402
import fleet_io  # noqa: E402


def _brief(world, text, name="R1.md"):
    b = world.sd / "briefs" / name; b.parent.mkdir(exist_ok=True); b.write_text(text)
    return b


@pytest.mark.parametrize("form", ["{sd}/fleet/reports/R1.md", ".superlite/fleet/reports/R1.md", "fleet/reports/R1.json",
                                  "`{sd}/fleet/reports/R1.md`", "file://{sd}/fleet/reports/R1.md"])
def test_relative_and_absolute_forms_are_refused(world, form):
    tok = form.format(sd=world.sd).strip("`").removeprefix("file://")
    b = _brief(world, f"Write your full report to {form.format(sd=world.sd)}.\n")
    rd = world.sd.resolve() / "fleet" / "reports"
    assert fleet.report_refusal(world.sd, b, "R1", world.proj) == (
        f"error: brief {b.resolve()} names {tok}: fleet wait saves the worker's reply as {rd}/R1.md and {rd}/R1.json "
        f"and would overwrite a report the worker writes there; name another file, such as {rd}/R1-full.md (#1094)")


def test_other_reports_are_not_refused(world):
    b = _brief(world, f"Read {world.sd}/fleet/reports/R2.md and fleet/reports/R10.md, write {world.sd}/fleet/reports/R1-full.md "
                      f"and {world.sd}/fleet/reports/R1.md.bak; the folder is {world.sd}/fleet/reports/.\n")
    assert fleet.report_refusal(world.sd, b, "R1", world.proj) is None


def test_batch_label_reserves_its_first_id(world):
    b = _brief(world, "Write fleet/reports/T3.md when done.\n")
    assert fleet.report_refusal(world.sd, b, "T3,T4", world.proj).endswith("(#1094)")
    assert fleet.report_refusal(world.sd, b, "T4,T3", world.proj) is None


def test_spawn_refuses_before_any_pane(world, capsys):
    fleet.main(["on"])
    b = _brief(world, f"Write your full report to {world.sd}/fleet/reports/R1.md.\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 2
    assert "(#1094)" in capsys.readouterr().err
    assert len(world.fh.calls) == n
    assert json.loads((world.sd / "fleet.json").read_text()).get("workers", {}) == {}


def test_label_flag_moves_the_reserved_name(world, monkeypatch):
    fleet.main(["on"])
    b = _brief(world, f"Write your full report to {world.sd}/fleet/reports/R1.md.\n")
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: {"id": "W1"})
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--label", "R9", "--plan", str(world.sd)]) == 0


def test_docs_name_both_fixes():
    doc = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "(#1094)" in doc and "(#1088)" in doc
    assert "(#1094)" in fleet.__doc__
