"""#548: a signal-killed run is a killed run, not a no-result bug; a --fast path valid from the root stays valid from a package dir."""
from __future__ import annotations

import json
import os
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import machine_load  # noqa: E402
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="signals are POSIX only")


@pytest.fixture(autouse=True)
def _fake_machine(monkeypatch):
    monkeypatch.setattr(machine_load, "snapshot_text", lambda: "machine: 1 lead of limit 6")
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)


def project(tmp_path, command):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "bash", "test": command}), encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def incidents(tmp_path):
    log = tmp_path / run_tests.ct.DEFAULT_LOG
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def test_signal_name():
    assert run_tests.signal_name(-9) == "SIGKILL"
    assert run_tests.signal_name(143) == "SIGTERM"
    assert run_tests.signal_name(137) == "SIGKILL"
    assert run_tests.signal_name(1) is None
    assert run_tests.signal_name(0) is None
    assert run_tests.signal_name(2) is None


def test_sigkill_command_is_killed_not_failure(tmp_path, monkeypatch):
    project(tmp_path, "sh -c 'kill -9 $$'")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) == 2
    err = summary(tmp_path)["error"]
    assert err.startswith("test run killed by SIGKILL (exit") and "its test processes were killed" in err
    assert "machine: 1 lead of limit 6" in err
    inc = incidents(tmp_path)
    assert inc and inc[-1]["signal"] == "SIGKILL" and inc[-1]["kind"] == "no-result"


def test_sigkill_pytest_is_killed_not_failure(tmp_path, monkeypatch):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_k.py").write_text("import os, signal\n\ndef test_k():\n    os.kill(os.getpid(), signal.SIGKILL)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) == 2
    err = summary(tmp_path)["error"]
    assert err.startswith("test run killed by SIGKILL (exit") and "its test processes were killed" in err
    assert incidents(tmp_path)[-1]["signal"] == "SIGKILL"


def test_exit_143_without_result_is_sigterm(tmp_path, monkeypatch):
    project(tmp_path, "sh -c 'exit 143'")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) == 2
    assert summary(tmp_path)["error"].startswith("test run killed by SIGTERM (exit 143)")


def test_exit_143_with_counts_is_a_result(tmp_path, monkeypatch):
    project(tmp_path, "echo '1 passed in 0.1s'; exit 143")
    monkeypatch.chdir(tmp_path)
    run_tests.main(["--full"])
    data = summary(tmp_path)
    assert "killed by" not in (data.get("error") or "")
    assert not any(i.get("signal") for i in incidents(tmp_path))


def test_snapshot_failure_never_stops_a_run(tmp_path, monkeypatch):
    def boom():
        raise RuntimeError("ps gone")
    monkeypatch.setattr(machine_load, "snapshot_text", boom)
    project(tmp_path, "sh -c 'exit 143'")
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--full"]) == 2
    assert summary(tmp_path)["error"].startswith("test run killed by SIGTERM")


def node_project(tmp_path):
    root = tmp_path
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps(
        {"language": "node", "test": "echo '1 passed'", "test_file": "echo '1 passed' {files}"}), encoding="utf-8")
    (root / "pkg" / "a" / "test").mkdir(parents=True)
    (root / "pkg" / "a" / "test" / "x.test.ts").write_text("", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "pkg" / "a" / "node_modules").mkdir()


def test_root_relative_path_from_package_dir(tmp_path, monkeypatch, capsys):
    node_project(tmp_path)
    monkeypatch.chdir(tmp_path / "pkg" / "a")
    run_tests.main(["--fast", "pkg/a/test/x.test.ts"])
    err = capsys.readouterr().err
    assert "run_tests: --fast pkg/a/test/x.test.ts read from the root" in err
    assert "test path not found" not in err


def test_cwd_relative_path_still_rewritten(tmp_path, monkeypatch, capsys):
    node_project(tmp_path)
    monkeypatch.chdir(tmp_path / "pkg" / "a")
    run_tests.main(["--fast", "test/x.test.ts"])
    err = capsys.readouterr().err
    assert "read from the root" not in err and "test path not found" not in err


def test_missing_node_path_is_usage_error(tmp_path, monkeypatch, capsys):
    node_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert run_tests.main(["--fast", "pkg/missing/x.test.ts"]) == 2
    assert "test path not found" in capsys.readouterr().err


def test_go_pattern_not_checked(tmp_path):
    assert run_tests.missing_fast_paths(["./pkg/..."], python=False) == []
    assert run_tests.missing_fast_paths(["./pkg/..."], python=True) == []
    assert run_tests.missing_fast_paths(["pkg/x_test.go"], python=False) == []
    assert run_tests.missing_line(["./pkg/..."], tmp_path, tmp_path, python=False) is None
