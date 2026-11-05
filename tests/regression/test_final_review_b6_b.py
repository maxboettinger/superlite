"""Final review b6: run_tests keeps task and no-result under SUPERLITE_SL; `incident hotspots` drops resolved locations."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
FAKE_SL = ROOT / "tests" / "scripts" / "fixtures" / "run_plan" / "fake_sl"

RED = "def test_x():\n    assert 1 == 2\n"
GREEN = "def test_x():\n    assert 1 == 1\n"


def rt(cwd, *args):
    env = {**os.environ, "SUPERLITE_SL": str(FAKE_SL)}
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, env=env)


def log(tmp_path):
    p = tmp_path / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def test_sl_mode_keeps_task_resolves_and_logs_no_result(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(RED, encoding="utf-8")
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 1
    red = [e for e in log(tmp_path) if e.get("kind") == "test-failure"]
    assert len(red) == 1 and red[0]["task"] == "T3"
    (tmp_path / "tests" / "test_a.py").write_text(GREEN, encoding="utf-8")
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 0
    entries = log(tmp_path)
    assert len(entries) == 2 and entries[-1]["resolution"] == "fixed"
    r = rt(tmp_path, "--fast", "tests/test_missing.py", "--task", "T3")
    assert r.returncode == 2, r.stdout + r.stderr
    stops = [e for e in log(tmp_path) if e.get("kind") == "no-result"]
    assert len(stops) == 1 and stops[0]["task"] == "T3" and stops[0]["resolution"] == "open"


def hotspots(tmp_path, *extra):
    r = subprocess.run([sys.executable, str(SCRIPTS / "incident.py"), "hotspots", "--log", str(tmp_path / "i.jsonl"), *extra],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]


def test_hotspots_drop_resolved_locations(tmp_path):
    def add(f, line, kind, res):
        cmd = [sys.executable, str(SCRIPTS / "incident.py"), "add", "--file", f, "--line", str(line), "--context", "c",
               "--kind", kind, "--resolution", res, "--log", str(tmp_path / "i.jsonl")]
        assert subprocess.run(cmd, capture_output=True, text=True, timeout=60).returncode == 0
    add("a.py", 1, "test-failure", "open")
    add("a.py", 1, "test-failure", "fixed")  # a.py:1 closed
    add("b.py", 2, "test-failure", "open")
    add("b.py", 2, "test-failure", "open")  # still open, repeated
    add("c.py", 3, "verified", "open")  # verified entries stay listed
    got = hotspots(tmp_path)
    locs = [(e["file"], e["line"]) for e in got]
    assert ("a.py", 1) not in locs
    assert locs.count(("b.py", 2)) == 1 and ("c.py", 3) in locs
