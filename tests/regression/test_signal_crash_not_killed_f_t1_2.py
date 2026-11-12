"""F-T1-2: only SIGKILL, SIGTERM, SIGHUP and SIGINT count as an outside kill; a crash signal stays a real no-result."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load  # noqa: E402
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="signals are POSIX only")


def test_signal_name_only_outside_kills():
    assert run_tests.signal_name(-11) is None
    assert run_tests.signal_name(134) is None
    assert run_tests.signal_name(-6) is None
    assert run_tests.signal_name(-5) is None
    assert run_tests.signal_name(-9) == "SIGKILL"
    assert run_tests.signal_name(143) == "SIGTERM"
    assert run_tests.signal_name(-1) == "SIGHUP"
    assert run_tests.signal_name(130) == "SIGINT"


def test_sigsegv_run_is_filed_by_finish(tmp_path, monkeypatch):
    monkeypatch.setattr(machine_load, "snapshot_text", lambda: "machine: 1 lead of limit 6")
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": "sh -c 'kill -11 $$'"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) != 0
    log = tmp_path / run_tests.ct.DEFAULT_LOG
    incs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert incs and not any(x.get("signal") for x in incs) and incs[-1]["resolution"] == "open"
    err = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8")).get("error") or ""
    assert "killed by" not in err
