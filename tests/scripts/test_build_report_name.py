"""report.py: the build report is `<plan>.build-report.*`; a plan task's `<plan>.report.md` is never touched."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402
from test_metrics_history import setup_run  # noqa: E402
from test_routing import mech_plan  # noqa: E402


def test_stored_paths_names():
    assert report.stored_paths("docs/plans/x.md") == (Path("docs/plans/x.build-report.md"), Path("docs/plans/x.build-report.json"))
    assert report.legacy_paths("docs/plans/x.md") == (Path("docs/plans/x.report.md"), Path("docs/plans/x.report.json"))


def test_write_report_leaves_plan_task_report(tmp_path):
    p = mech_plan(tmp_path, 2)
    setup_run(tmp_path)
    keep = p.with_name("plan.report.md")
    keep.write_bytes(b"task review results\n")
    report.write_report(p, tmp_path / ".superlite")
    assert keep.read_bytes() == b"task review results\n"
    assert p.with_name("plan.build-report.md").is_file() and p.with_name("plan.build-report.json").is_file()
    assert (tmp_path / ".superlite" / "report.md").is_file()


def test_list_reads_legacy_and_new(tmp_path):
    (tmp_path / "old.report.json").write_text(json.dumps({"headline": {}}), encoding="utf-8")
    (tmp_path / "new.build-report.json").write_text(json.dumps({"headline": {}}), encoding="utf-8")
    lines = report.list_reports(tmp_path).strip().splitlines()
    assert len(lines) == 2
    assert sorted(ln.split("  ")[0] for ln in lines) == ["new", "old"]
    assert any(ln.startswith("new  ") for ln in lines) and any(ln.startswith("old  ") for ln in lines)


def test_show_reads_legacy(tmp_path):
    p = mech_plan(tmp_path, 2)
    setup_run(tmp_path)
    report.write_report(p, tmp_path / ".superlite")
    md, js = report.stored_paths(p)
    md.rename(tmp_path / "old.report.md")
    js.rename(tmp_path / "old.report.json")
    assert not report.show_report("old", tmp_path).startswith("report: no stored report")
    assert report.show_report("old", tmp_path, full=True) == (tmp_path / "old.report.md").read_text(encoding="utf-8")


def test_show_prefers_new(tmp_path):
    for n, t in (("x.report", "old\n"), ("x.build-report", "new\n")):
        (tmp_path / (n + ".md")).write_text(t, encoding="utf-8")
        (tmp_path / (n + ".json")).write_text(json.dumps({"headline": {}}), encoding="utf-8")
    assert report.show_report("x", tmp_path, full=True) == "new\n"
    assert report.show_report("x.build-report.md", tmp_path, full=True) == "new\n"
