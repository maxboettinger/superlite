"""run_tests --fast says when the test command takes no paths and runs whole (#708)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402
from _fixtures import DISK_FREE  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)
NOTE = "--fast paths not passed, .superlite/test-cmd.json has no {files}"
LINE = f"run_tests: {NOTE}; the whole command runs: bash all.sh"


def run(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(DISK_FREE, SUPERLITE_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def project(tmp_path, cfg):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    (tmp_path / "all.sh").write_text('echo "3 passed"\n', encoding="utf-8")
    (tmp_path / "run.sh").write_text('echo "$# passed"\n', encoding="utf-8")
    (tmp_path / "a.sh").write_text("exit 0\n", encoding="utf-8")
    return tmp_path


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_fast_paths_dropped_line(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh"})
    cp = run(tmp_path, "--fast", "a.sh")
    assert cp.returncode == 0, cp.both
    assert cp.stderr.count(LINE) == 1, cp.stderr
    data = summary(tmp_path)
    assert data["mode"] == "fast"
    assert data["passed"] == 3
    assert data["paths_dropped"] == NOTE
    assert run_tests.summary_line(data) == f"tests (whole command, {NOTE}): 3 passed, 0 failed"


def test_files_template_no_line(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh", "test_file": "bash run.sh {files}"})
    cp = run(tmp_path, "--fast", "a.sh")
    assert cp.returncode == 0, cp.both
    assert "--fast paths not passed" not in cp.stderr
    data = summary(tmp_path)
    assert data["passed"] == 1
    assert "paths_dropped" not in data
    assert run_tests.summary_line(data) == "tests (fast): 1 passed, 0 failed"


def test_full_run_no_line(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh", "lock": False})
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert "--fast paths not passed" not in cp.stderr
    assert "paths_dropped" not in summary(tmp_path)


def test_dropped_note_swift_names_only_testing():
    spec = {"language": "swift", "origin": "~/.config/superlite/test-cmd.json"}
    assert run_tests.dropped_note(spec) == "--fast paths not passed, ~/.config/superlite/test-cmd.json has no {only_testing}"


def test_plain_fast_head_unchanged():
    assert run_tests.summary_line({"passed": 3, "failed": 1, "skipped": 0, "mode": "fast"}) == "tests (fast): 3 passed, 1 failed"


def test_docs_language_names_the_line():
    text = (ROOT / "docs" / "language.md").read_text(encoding="utf-8")
    assert "ignores the `--fast` paths" in text
    assert f"`{LINE}`" in text
    assert "holds {file}; the placeholder for --fast paths is {files}" in text
