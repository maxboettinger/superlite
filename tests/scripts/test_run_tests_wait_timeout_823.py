"""run_tests --wait without --timeout waits as long as the run is predicted to need, and says why it stopped (#823)."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import predict_live  # noqa: E402
import run_tests  # noqa: E402


def test_call_cap_values():
    assert run_tests.call_cap({}) == 540.0
    assert run_tests.call_cap({"BASH_MAX_TIMEOUT_MS": "1800000"}) == 1740.0
    assert run_tests.call_cap({"BASH_MAX_TIMEOUT_MS": "90000"}) == 45.0
    for bad in ("abc", "0", "-5"):
        assert run_tests.call_cap({"BASH_MAX_TIMEOUT_MS": bad}) == 540.0


def test_wait_seconds_examples():
    ws = run_tests.wait_seconds
    assert ws(None, 1000.0, 540.0) == (540.0, False)
    assert ws({"started": 1000.0, "predicted": 578.0, "limit": 3600.0}, 1000.0, 1740.0) == (638.0, False)
    assert ws({"started": 1000.0, "predicted": 578.0, "limit": 3600.0}, 1000.0, 540.0) == (540.0, True)
    assert ws({"started": 1000.0, "predicted": None, "limit": 3600.0}, 1100.0, 7200.0) == (3560.0, False)
    assert ws({"started": 1000.0, "predicted": 60.0, "limit": 3600.0}, 1000.0, 1740.0) == (540.0, False)
    assert ws({"started": 1000.0, "predicted": None, "limit": 0}, 1000.0, 1740.0) == (1740.0, False)
    assert ws({"started": 1000.0, "predicted": 578.0, "limit": 3600.0}, 1000.0, 45.0) == (45.0, True)


def project(tmp_path, run_min):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": "pytest", "run_min": run_min}), encoding="utf-8")
    return tmp_path


def test_predicted_length_from_run_min(tmp_path):
    root = project(tmp_path, {"fast": 1, "full": 4})
    assert run_tests.predicted_length(root, "full") == (240.0, "run_min in test-cmd.json")
    assert run_tests.predicted_length(root, "fast")[0] == 60.0


def test_predicted_length_none_on_error(tmp_path, monkeypatch):
    def boom(root, cfg):
        raise RuntimeError("x")

    monkeypatch.setattr(predict_live, "project_tests", boom)
    assert run_tests.predicted_length(tmp_path, "full") == (None, None)


def test_predicted_length_none_without_data(tmp_path):
    assert run_tests.predicted_length(tmp_path, "full") == (None, None)


def test_write_and_read_run_meta(tmp_path):
    mine = tmp_path / "s.json"
    root = project(tmp_path, {"fast": 1, "full": 4})
    run_tests.write_run_meta(mine, 1234.5, "full", 3600.0, root)
    meta = run_tests.run_meta(mine)
    assert meta["started"] == 1234.5 and meta["mode"] == "full" and meta["limit"] == 3600.0
    assert meta["predicted"] == 240.0 and meta["predicted_from"] == "run_min in test-cmd.json"
    assert run_tests.run_meta(tmp_path / "none.json") is None
    mine.with_suffix(".meta").write_text("not json", encoding="utf-8")
    assert run_tests.run_meta(mine) is None


def test_background_writes_meta(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    s = tmp_path / "s.json"
    r = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--fast", "test_ok.py", "--background", "--summary", str(s)],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    printed = next(ln for ln in r.stdout.splitlines() if ln.startswith("summary: "))[len("summary: "):]
    meta = json.loads(Path(printed).with_suffix(".meta").read_text(encoding="utf-8"))
    assert meta["mode"] == "fast" and meta["limit"] == 3600 and isinstance(meta["started"], float)
    run_tests_wait = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--wait", printed, "--timeout", "60"],
                                    cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert run_tests_wait.returncode == 0


def write_meta(path, **kw):
    path.with_suffix(".meta").write_text(json.dumps(kw), encoding="utf-8")


def wait(tmp_path, monkeypatch, capsys, *args):
    monkeypatch.chdir(tmp_path)
    rc = run_tests.main(["--wait", str(tmp_path / "s.json"), *args])
    return rc, capsys.readouterr().err


def test_timeout_line_names_prediction_and_cap(tmp_path, monkeypatch, capsys):
    write_meta(tmp_path / "s.json", started=time.time() - 100, predicted=578, limit=3600)
    monkeypatch.setattr(run_tests, "call_cap", lambda env=None: 0.6)
    rc, err = wait(tmp_path, monkeypatch, capsys)
    assert rc == 2
    line = next(ln for ln in err.splitlines() if ln.startswith("tests: no result yet"))
    assert re.match(r"^tests: no result yet after 0\.6 s \(about 4\d\d s left of a predicted 578 s run; "
                    r"one call waits at most 0\.6 s; BASH_MAX_TIMEOUT_MS raises it\); run again: ", line), line


def test_timeout_line_past_prediction(tmp_path, monkeypatch, capsys):
    write_meta(tmp_path / "s.json", started=time.time() - 700, predicted=578, limit=3600)
    rc, err = wait(tmp_path, monkeypatch, capsys, "--timeout", "0.5")
    line = next(ln for ln in err.splitlines() if ln.startswith("tests: no result yet"))
    assert rc == 2 and re.search(r"\(\d+ s past its predicted 578 s\)", line) and "one call waits" not in line


def test_timeout_line_unchanged_without_meta(tmp_path, monkeypatch, capsys):
    rc, err = wait(tmp_path, monkeypatch, capsys, "--timeout", "0.5")
    line = next(ln for ln in err.splitlines() if ln.startswith("tests: no result yet"))
    assert line == f"tests: no result yet after 0.5 s; run again: {run_tests.wait_line(tmp_path / 's.json')[len('wait: '):]}"
