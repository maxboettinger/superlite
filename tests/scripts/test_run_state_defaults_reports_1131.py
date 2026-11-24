"""#1131: the reporting tools' state defaults go through state.default_dir()/default_root(), never a bare cwd `.superlite`."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from test_session_state import SCRIPTS, state  # noqa: F401
from test_state_plugin_folder_1116 import plug  # noqa: F401

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import history  # noqa: E402
import incident  # noqa: E402
import metrics  # noqa: E402
import next_tasks  # noqa: E402
import report  # noqa: E402
import run_archive  # noqa: E402


def clean(tmp):
    assert not any((tmp / "plugin" / "skills").rglob(".superlite"))


@pytest.fixture
def pj(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    return tmp, proj


def test_next_tasks_default_plan_from_plugin(pj):
    tmp, proj = pj
    assert next_tasks.default_plan() == str(proj / ".superlite" / "plan.md")
    clean(tmp)


def test_next_tasks_default_plan_outside_plugin(tmp_path, monkeypatch):
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "a1")
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    (tmp_path / "w").mkdir()
    monkeypatch.chdir(tmp_path / "w")
    monkeypatch.setenv("PWD", str(tmp_path / "w"))
    assert next_tasks.default_plan() == str(Path(".superlite") / "plan.md")


def test_history_write_from_plugin_lands_in_project(pj, monkeypatch):
    tmp, proj = pj
    seen = []
    monkeypatch.setattr(history, "run_rows", lambda plan, sl_dir=None, run_id=None: seen.append(Path(sl_dir)) or [])
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp / "home"))
    assert history.main(["write", "--plan", "p.md"]) == 0
    assert seen == [proj / ".superlite"]
    clean(tmp)


def test_report_dir_default_from_plugin(pj, capsys):
    tmp, proj = pj
    assert report.main(["--plan", "p.md"]) == 2
    assert str(proj / ".superlite") in capsys.readouterr().err
    clean(tmp)


def test_report_list_root_default_from_plugin(pj, monkeypatch, tmp_path):
    tmp, proj = pj
    seen = []
    monkeypatch.setattr(run_archive, "archive_dir", lambda sd: seen.append(Path(sd)) or tmp / "none")
    monkeypatch.setattr(report, "list_reports", lambda plans, archive: "")
    assert report.main(["--list"]) == 0
    assert seen == [proj / ".superlite"]
    clean(tmp)


def test_metrics_dir_default_from_plugin(pj, capsys):
    tmp, proj = pj
    (proj / ".superlite").mkdir()
    (proj / ".superlite" / "metrics.jsonl").write_text("")
    metrics.main([])
    assert "no metrics.jsonl" not in capsys.readouterr().err
    clean(tmp)


def test_finish_summary_lint_log_default(tmp_path, monkeypatch):
    sd = tmp_path / "s" / ".superlite"
    sd.mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(sd))
    ledger = sd / "progress.md"
    ledger.write_text("")
    seen = []
    monkeypatch.setattr(finish, "unblocked_report", lambda led, lint, *a, **k: seen.append(Path(lint)) or "")
    finish.summary(str(ledger), str(sd / "incidents.jsonl"), plan="")
    assert seen == [sd / "lint-log.jsonl"]


def test_incident_has_no_cwd_default():
    assert not hasattr(incident, "DEFAULT_LOG")
