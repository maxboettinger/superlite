"""#986: a worker's report is filed in the run that spawned it (its record's state_dir)."""
import json, sys
from pathlib import Path

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet as fleet_mod  # noqa: E402
import fleet_io as fio  # noqa: E402


def run(tmp_path, name):
    d = tmp_path / name / ".superlite"; d.mkdir(parents=True); return d


def patch_finish(monkeypatch):
    for n in ("pane_label", "pane_title", "_tel_finish", "_ready", "_stop_worker"):
        if hasattr(fio, n):
            monkeypatch.setattr(fio, n, lambda *a, **k: None)


def test_report_dir_examples(tmp_path):
    A, B = run(tmp_path, "A"), run(tmp_path, "B")
    assert fio.report_dir(A, {"state_dir": str(B)}) == B / "fleet" / "reports"
    (B / "remote" / "W3").mkdir(parents=True)
    assert fio.report_dir(A, {"machine": "m1", "state_dir": str(B / "remote" / "W3")}) == B / "fleet" / "reports"
    assert fio.report_dir(".superlite", {"state_dir": str(tmp_path / "gone" / ".superlite")}) == Path(".superlite/fleet/reports")
    assert fio.report_dir(".superlite", {}) == Path(".superlite/fleet/reports")


def test_same_run_paths_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".superlite").mkdir()
    assert fio.report_dir(".superlite", {"state_dir": str((tmp_path / ".superlite").resolve())}) == Path(".superlite/fleet/reports")


def test_gone_run_falls_back(tmp_path, monkeypatch):
    A = run(tmp_path, "A"); patch_finish(monkeypatch)
    fio._finish(A, "W1", {"task": "T1", "state_dir": str(tmp_path / "gone" / ".superlite"), "role": "implementer"}, "Status: DONE\n", "transcript")
    assert (A / "fleet" / "reports" / "T1.json").is_file()


def test_finish_files_report_in_worker_run(tmp_path, monkeypatch, capsys):
    A, B = run(tmp_path, "A"), run(tmp_path, "B"); patch_finish(monkeypatch)
    rep = fio._finish(A, "W1", {"task": "T1", "state_dir": str(B), "role": "implementer"}, "Status: DONE\n", "transcript")
    assert (B / "fleet/reports/T1.md").is_file() and (B / "fleet/reports/T1.json").is_file()
    assert not (A / "fleet" / "reports" / "T1.json").exists() and not (A / "fleet" / "reports" / "T1.md").exists()
    assert str(B / "fleet/reports/T1.json") in capsys.readouterr().out
    assert str(rep["report"]) == str(B / "fleet/reports/T1.json")


def test_layer_report_in_worker_run(tmp_path, monkeypatch):
    A, B = run(tmp_path, "A"), run(tmp_path, "B"); patch_finish(monkeypatch)
    fio._finish_layer(A, "W2", {"task": "L1", "state_dir": str(B)}, {"status": "PASS", "exit": 0, "log": "x.log", "last": "ok"})
    assert json.loads((B / "fleet/reports/L1.json").read_text())["status"] == "PASS"


def test_collected_line_names_worker_run(tmp_path, capsys):
    A, B = run(tmp_path, "A"), run(tmp_path, "B")
    assert fio._collected(A, "W1", {"state": "ready", "last_task": "T1", "state_dir": str(B)}) is True
    assert capsys.readouterr().out.strip() == f"W1 T1 already collected: {B}/fleet/reports/T1.json"


def test_fleet_report_reads_worker_run(tmp_path, capsys):
    A, B = run(tmp_path, "A"), run(tmp_path, "B")
    (A / "fleet.json").write_text(json.dumps({"workers": {"W1": {"state": "ready", "last_task": "T1", "state_dir": str(B)}}}))
    (B / "fleet" / "reports").mkdir(parents=True); (B / "fleet/reports/T1.md").write_text("hello")
    assert fleet_mod._report(Path(A), ["W1"]) == 0
    assert capsys.readouterr().out.strip() == "hello"
    assert fleet_mod._report(Path(A), ["T1"]) == 1
    assert "error: unknown worker or report label T1" in capsys.readouterr().err
