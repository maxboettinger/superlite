"""run_tests --wait ends with a summary line, takes a last look at the deadline, and a leftover child cannot hold a run (#382)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402


def rt(cwd, *args, timeout=120):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def last_line(text):
    return [ln for ln in text.splitlines() if ln.strip()][-1]


def test_summary_line_examples():
    assert run_tests.summary_line({"passed": 5022, "failed": 0, "skipped": 0, "mode": "full"}) == "tests (full): 5022 passed, 0 failed"
    assert run_tests.summary_line({"passed": 3, "failed": 1, "skipped": 2, "mode": "fast"}) == "tests (fast): 3 passed, 1 failed, 2 skipped"
    assert (run_tests.summary_line({"passed": 0, "failed": 1, "skipped": 0, "mode": "full", "error": "run_tests crashed: X"})
            == "tests (full): 0 passed, 1 failed; error: run_tests crashed: X")
    assert run_tests.summary_line({"passed": 1, "failed": 0, "skipped": 0}) == "tests: 1 passed, 0 failed"


def test_wait_prints_the_line_last(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"passed": 5022, "failed": 0, "skipped": 0, "mode": "full"}), encoding="utf-8")
    r = rt(tmp_path, "--wait", str(p), "--timeout", "5")
    assert r.returncode == 0
    assert json.loads(r.stdout)["passed"] == 5022
    assert last_line(r.stderr) == "tests (full): 5022 passed, 0 failed"
    p.write_text(json.dumps({"passed": 1, "failed": 2, "skipped": 0, "mode": "fast"}), encoding="utf-8")
    r = rt(tmp_path, "--wait", str(p), "--timeout", "5")
    assert r.returncode == 1
    assert last_line(r.stderr) == "tests (fast): 1 passed, 2 failed"


def test_wait_last_look_at_the_deadline(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    monkeypatch.chdir(tmp_path)

    def late(mine):
        p.write_text(json.dumps({"passed": 1, "failed": 0, "skipped": 0, "mode": "fast"}), encoding="utf-8")
        return None

    monkeypatch.setattr(run_tests, "pid_gone", late)
    assert run_tests.main(["--wait", str(p), "--timeout", "0"]) == 0


def test_timeout_names_the_rerun(tmp_path):
    p = tmp_path / "s.json"
    p.with_suffix(".pid").write_text(str(os.getpid()), encoding="utf-8")
    r = rt(tmp_path, "--wait", str(p), "--timeout", "0.5")
    assert r.returncode == 2
    assert f"run_tests: timed out waiting for {p}; log {p.with_suffix('.log')}" in r.stderr
    line = last_line(r.stderr)
    assert line.startswith(f"tests: no result yet after 0.5 s (pid {os.getpid()} still running); run again: ")
    assert line.endswith(f" run_tests --wait {p}")
    p.with_suffix(".pid").unlink()
    r = rt(tmp_path, "--wait", str(p), "--timeout", "0.5")
    assert r.returncode == 2
    line = last_line(r.stderr)
    assert line.startswith("tests: no result yet after 0.5 s; run again: ") and "(pid" not in line


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell")
def test_leftover_child_does_not_hold_the_run(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "other", "test": "sh -c '(sleep 20 &) ; echo 1 passed'"}), encoding="utf-8")
    t0 = time.monotonic()
    r = rt(tmp_path, "--full")
    assert r.returncode == 0, r.stderr
    assert time.monotonic() - t0 < 10
    assert json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))["passed"] == 1


def test_run_captured_returns_code_and_output():
    r = run_tests.run_captured([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"])
    assert (r.returncode, r.stdout, r.stderr) == (3, "out\n", "err\n")


def test_default_wait_is_540():
    assert run_tests.DEFAULT_WAIT == 540.0
