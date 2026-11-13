"""Experiment end to end (#682): online arms to report, and offline replay rows to report; no live agent."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "bench"))
import batch_cost  # noqa: E402
import experiment  # noqa: E402
import mechanical_ab  # noqa: E402

SRC = REPO.joinpath("tests", "bench", "fixtures", "replay")


def make_home(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    (home / "run-configs.json").write_text(json.dumps(
        {"configs": {"cheap": {"lead": {"model": "haiku"}}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    return home


def cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "experiment.py"), *args], capture_output=True, text=True,
                          env=dict(os.environ))


def test_online_arms_to_report(tmp_path, monkeypatch):
    make_home(tmp_path, monkeypatch)
    root = tmp_path / "root"
    (root / ".superlite").mkdir(parents=True)
    exp = experiment.set_arms(root, "e1", ["default", "cheap"], batches=4, seed=3)
    for i in range(1, 5):
        batch = f"B{i}"
        got = experiment.assign(root, batch)
        assert got is not None and got["experiment"] == "e1"
        row = batch_cost.record(root, {"id": batch, "run_config": exp["configs"][got["arm"]]}, "shipped")
        assert row is not None and row["arm"] == got["arm"] and row["experiment"] == "e1"
    out = cli("report", "e1", "--root", str(root))
    assert out.returncode == 0, out.stderr
    assert "default" in out.stdout and "cheap" in out.stdout
    assert "not enough data" in out.stdout
    out = cli("report", "e1", "--root", str(root), "--min", "2")
    assert out.returncode == 0, out.stderr
    assert "verdict:" in out.stdout
    assert "default: 2 batches" in out.stdout and "cheap: 2 batches" in out.stdout
    assert "excluded" not in out.stdout


def test_replay_rows_to_report(tmp_path, monkeypatch):
    make_home(tmp_path, monkeypatch)
    FIX = tmp_path.joinpath("fx")
    FIX.mkdir()
    for name in ("fake_agent.py", "fake_judge.py"):
        shutil.copy(SRC / name, FIX / name)
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "m.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "tests" / "test_m.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom m import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n",
        encoding="utf-8")
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
        subprocess.run(["git", *cmd], cwd=repo, check=True, capture_output=True)
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "test_hidden.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom m import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{
        "id": "c1", "repo": str(repo), "base": "HEAD", "title": "add is wrong", "body": "add subtracts",
        "test_cmd": f'"{sys.executable}" -m pytest -q tests/test_m.py',
        "hidden_test": {"path": "tests/test_hidden.py", "source": "hidden/test_hidden.py"}}]), encoding="utf-8")
    out = tmp_path / "out"
    rc = mechanical_ab.replay_main([
        str(cases), "--arms", "default,cheap", "--n", "3", "--experiment", "r1", "--out", str(out),
        "--agent-cmd", f'"{sys.executable}" "{FIX / "fake_agent.py"}" --fix-arms cheap --cost 0.01 --arm {{arm}}'])
    assert rc == 0
    root = tmp_path / "root"
    (root / ".superlite").mkdir(parents=True)
    res = cli("report", "r1", "--rows", str(out / "replay.jsonl"), "--root", str(root))
    assert res.returncode == 0, res.stderr
    assert "default: 3 batches" in res.stdout and "cheap: 3 batches" in res.stdout
    assert "verdict:" in res.stdout
