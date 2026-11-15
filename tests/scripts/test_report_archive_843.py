"""report.py lists and shows the runs archived in the main checkout (#843)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from test_plan_tools import SCRIPTS, run
from test_report import REPORT, fixture, go

sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402

RID, OLD = "20261114-235958-B7", "20261101-120000"


def _arch(tmp_path):
    p = fixture(tmp_path)
    go(tmp_path, p)
    md, js = report.stored_paths(p)
    arch = tmp_path / "arch"
    (arch / RID).mkdir(parents=True)
    shutil.copy(md, arch / RID / "build-report.md")
    shutil.copy(js, arch / RID / "build-report.json")
    (arch / RID / "run.json").write_text(json.dumps({"plan": "/x/p.md", "batch": "B7"}), encoding="utf-8")
    (arch / OLD).mkdir()
    (arch / OLD / "progress.md").write_text("x", encoding="utf-8")
    (arch / OLD / "a.txt").write_text("x", encoding="utf-8")
    plans = tmp_path / "plans"
    plans.mkdir()
    return plans, arch


def test_list_appends_archived_runs(tmp_path):
    plans, arch = _arch(tmp_path)
    lines = report.list_reports(plans, arch).splitlines()
    assert lines[0] == f"no stored reports in {plans}"
    assert lines[1] == f"archived runs in {arch}:"
    assert lines[2].startswith(f"  {RID}  p  B7  time ") and "  cost " in lines[2]
    assert lines[3] == f"  {OLD}  -  -  no build report"
    assert len(lines) == 4


def test_list_without_archive_unchanged(tmp_path):
    plans, arch = _arch(tmp_path)
    want = f"no stored reports in {plans}\n"
    assert report.list_reports(plans) == want
    assert report.list_reports(plans, tmp_path / "none") == want
    empty = tmp_path / "empty"
    empty.mkdir()
    assert report.list_reports(plans, empty) == want


def test_show_by_run_id(tmp_path):
    plans, arch = _arch(tmp_path)
    s = report.show_report(RID, plans, archive=arch)
    assert s.startswith("build report (projected -> actual)")
    assert (arch / RID / "build-report.md").as_posix() in s
    assert report.show_report(RID, plans, full=True, archive=arch) == (arch / RID / "build-report.md").read_text(encoding="utf-8")


def test_show_by_plan_stem_falls_back_to_archive(tmp_path):
    plans, arch = _arch(tmp_path)
    assert RID in report.show_report("p", plans, archive=arch)


def test_show_run_without_report(tmp_path):
    plans, arch = _arch(tmp_path)
    assert report.show_report(OLD, plans, archive=arch) == (
        f"report: archived run {OLD} has no build report; files in {arch / OLD}: a.txt, progress.md\n")


def test_show_unknown_unchanged(tmp_path):
    plans, arch = _arch(tmp_path)
    want = f"report: no stored report for nope in {plans}\n"
    assert report.show_report("nope", plans, archive=arch) == want
    assert report.show_report("nope", plans) == want


def test_cli_root_picks_archive(tmp_path):
    main = tmp_path / "main"
    r = main / ".superlite" / "runs" / RID
    r.mkdir(parents=True)
    (r / "run.json").write_text("{}", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", str(main)], check=True, env=env)
    out = run(REPORT, "--list", "--root", main, "--plans", tmp_path / "plans", cwd=tmp_path).out
    assert RID in out
