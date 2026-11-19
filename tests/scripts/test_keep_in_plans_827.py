import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(HERE))
import report  # noqa: E402
import run_archive  # noqa: E402


def mk(tmp_path, name="fix-login", build=True, progress=True):
    sd = tmp_path / ".superlite"
    (sd / "plans").mkdir(parents=True)
    plan = sd / "plans" / f"{name}.md"
    plan.write_bytes(b"plan")
    if build:
        (sd / "plans" / f"{name}.build-report.md").write_bytes(b"rmd")
        (sd / "plans" / f"{name}.build-report.json").write_bytes(b"rjs")
    if progress:
        (sd / "progress.md").write_bytes(b"prog")
    return plan, sd


def test_outside_plan_copied_with_dated_stem(tmp_path):
    plan, sd = mk(tmp_path)
    got = run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19")
    assert got == ["docs/plans/2026-11-19-fix-login.md", "docs/plans/2026-11-19-fix-login.build-report.md",
                   "docs/plans/2026-11-19-fix-login.build-report.json", "docs/plans/2026-11-19-fix-login.progress.md"]
    assert (tmp_path / got[0]).read_bytes() == b"plan"
    assert (tmp_path / got[1]).read_bytes() == b"rmd"
    assert (tmp_path / got[2]).read_bytes() == b"rjs"
    assert (tmp_path / got[3]).read_bytes() == b"prog"


def test_plan_in_plans_folder_copies_progress_only(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "progress.md").write_bytes(b"prog")
    d = tmp_path / "docs" / "plans"
    d.mkdir(parents=True)
    plan = d / "2026-11-19-x.md"
    plan.write_bytes(b"plan")
    assert run_archive.keep_in_plans(str(plan), str(sd)) == ["docs/plans/2026-11-19-x.progress.md"]
    assert plan.read_bytes() == b"plan"
    assert not (d / "2026-11-19-x.build-report.md").exists()


def test_dated_stem_kept(tmp_path):
    plan, sd = mk(tmp_path, "2026-01-02-a", build=False, progress=False)
    assert run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19") == ["docs/plans/2026-01-02-a.md"]


def test_other_file_of_that_name_gets_suffix(tmp_path):
    plan, sd = mk(tmp_path)
    d = tmp_path / "docs" / "plans"
    d.mkdir(parents=True)
    (d / "2026-11-19-fix-login.md").write_bytes(b"other")
    got = run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19")
    assert got[0] == "docs/plans/2026-11-19-fix-login-2.md"
    assert (d / "2026-11-19-fix-login.md").read_bytes() == b"other"


def test_identical_file_reused(tmp_path):
    plan, sd = mk(tmp_path)
    d = tmp_path / "docs" / "plans"
    d.mkdir(parents=True)
    (d / "2026-11-19-fix-login.md").write_bytes(b"plan")
    (d / "2026-11-19-fix-login.progress.md").write_bytes(b"old")
    got = run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19")
    assert got[0] == "docs/plans/2026-11-19-fix-login.md"
    assert (d / "2026-11-19-fix-login.progress.md").read_bytes() == b"prog"


def test_superpowers_folder_wins(tmp_path):
    plan, sd = mk(tmp_path, build=False, progress=False)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    got = run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19")
    assert got == ["docs/superpowers/plans/2026-11-19-fix-login.md"]


def test_missing_parts_skipped(tmp_path):
    plan, sd = mk(tmp_path, build=False, progress=False)
    assert run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19") == ["docs/plans/2026-11-19-fix-login.md"]


def test_no_plan_or_foreign_run_folder(tmp_path):
    plan, sd = mk(tmp_path)
    assert run_archive.keep_in_plans("", str(sd)) == []
    assert run_archive.keep_in_plans(str(tmp_path / "nope.md"), str(sd)) == []
    other = tmp_path / "other"
    other.mkdir()
    assert run_archive.keep_in_plans(str(plan), str(other)) == []


def test_oserror_returns_written_so_far(tmp_path, monkeypatch):
    plan, sd = mk(tmp_path)
    real, calls = run_archive.shutil.copyfile, []

    def flaky(a, b):
        calls.append(b)
        if len(calls) == 3:
            raise OSError("disk")
        return real(a, b)

    monkeypatch.setattr(run_archive.shutil, "copyfile", flaky)
    got = run_archive.keep_in_plans(str(plan), str(sd), today="2026-11-19")
    assert got == ["docs/plans/2026-11-19-fix-login.md", "docs/plans/2026-11-19-fix-login.build-report.md"]


def test_report_list_uses_plans_dir(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    report.main(["--list", "--root", str(tmp_path)])
    assert os.path.join("docs", "superpowers", "plans") in capsys.readouterr().out


def test_plans_dir_creates_nothing(tmp_path):
    d = run_archive.plans_dir(tmp_path)
    assert d == tmp_path / "docs" / "plans"
    assert not (tmp_path / "docs").exists()


def test_report_list_in_empty_folder_leaves_no_plans_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report.main(["--list", "--root", str(tmp_path)])
    assert not (tmp_path / "docs").exists()


def test_module_docstring_names_plans_helpers():
    doc = run_archive.__doc__
    assert "plans_dir(" in doc and "keep_in_plans(" in doc
