"""history.run_rows: every row of a run carries the run config id the run ran under (#682)."""
from __future__ import annotations

import json
import sys

from test_metrics_history import setup_run
from test_plan_tools import SCRIPTS
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import history  # noqa: E402


def test_rows_carry_the_run_config_id(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = mech_plan(tmp_path, 2)
    sl = setup_run(tmp_path)
    (sl / "run-config.json").write_text(json.dumps({"id": "lean-1a2b3c4d"}), encoding="utf-8")
    rows = history.run_rows(p, sl)
    assert rows and all(r["run_config"] == "lean-1a2b3c4d" for r in rows)


def test_rows_without_a_run_config_file_have_none(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = mech_plan(tmp_path, 2)
    sl = setup_run(tmp_path)
    rows = history.run_rows(p, sl)
    assert rows and all(r["run_config"] is None for r in rows)


def test_run_config_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = mech_plan(tmp_path, 2)
    sl = setup_run(tmp_path)
    (sl / "run-config.json").write_text("{", encoding="utf-8")
    rows = history.run_rows(p, sl)
    assert rows and all(r["run_config"] is None for r in rows)
