"""Offline replay runner (#682): fake agent and judge commands, a tiny repo built in tmp, no live agent."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))
import mechanical_ab as ab  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "replay"
PY = sys.executable


def sh(*parts) -> str:
    return " ".join(f'"{p}"' for p in parts)


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "run-configs.json").write_text(json.dumps(
        {"configs": {"cheap": {"lead": {"model": "haiku", "effort": "low"}}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
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
    case = {"id": "c1", "repo": str(repo), "base": "HEAD", "title": "add is wrong", "body": "add subtracts",
            "test_cmd": f"{PY} -m pytest -q tests/test_m.py",
            "hidden_test": {"path": "tests/test_hidden.py", "source": "hidden/test_hidden.py"}}
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([case]), encoding="utf-8")
    return tmp_path, cases


def run(env, *extra, agent="--fix-arms cheap --cost 0.01", n="3"):
    tmp, cases = env
    out = tmp / "out"
    argv = [str(cases), "--arms", "default,cheap", "--n", n, "--out", str(out), "--experiment", "exp1",
            "--agent-cmd", f"{sh(PY, FIX / 'fake_agent.py')} {agent} --arm {{arm}}", *extra]
    rc = ab.replay_main(argv)
    rows = []
    if (out / "replay.jsonl").exists():
        rows = [json.loads(x) for x in (out / "replay.jsonl").read_text(encoding="utf-8").splitlines()]
    return rc, rows


def test_replay_order_rounds():
    order = ab.replay_order(["c1", "c2"], ["A", "B"], 3, 7)
    assert len(order) == 12
    for k in (1, 2, 3):
        for c in ("c1", "c2"):
            assert sorted(a for cc, a, kk in order if cc == c and kk == k) == ["A", "B"]
    assert [kk for _, _, kk in order] == sorted(kk for _, _, kk in order)
    assert order == ab.replay_order(["c1", "c2"], ["A", "B"], 3, 7)


def test_n_below_3_refuses(env, capsys):
    tmp, cases = env
    assert ab.replay_main([str(cases), "--arms", "default,cheap", "--n", "2"]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_replay_fake_agent_rows(env):
    rc, rows = run(env)
    assert rc == 0 and len(rows) == 6
    for r in rows:
        assert r["row"] == "replay" and r["experiment"] == "exp1" and r["arms"] == ["default", "cheap"]
        assert r["config"].startswith(r["arm"] + "-")
        assert r["lead"]["cost_usd"] == 0.01
        if r["arm"] == "cheap":
            assert r["end"] == "passed" and r["quality"] == 100.0
        else:
            assert r["end"] == "failed" and r["quality"] == 0.0


def test_judge_diff_survives_agent_commit(env):
    dlog = env[0] / "diff.log"
    rc, rows = run(env, "--judge-cmd", f"{sh(PY, FIX / 'fake_judge.py')} --diff-file {{diff_file}} --diff-log {sh(dlog)}",
                   agent="--fix-arms cheap --commit")
    assert rc == 0
    flags = [int(x) for x in dlog.read_text(encoding="utf-8").split()]
    assert flags and all(flags)


def test_judge_only_on_passing(env):
    log = env[0] / "judge.log"
    rc, rows = run(env, "--judge-cmd", f"{sh(PY, FIX / 'fake_judge.py')} --score 8 --log {sh(log)}")
    assert rc == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3
    for r in rows:
        if r["arm"] == "cheap":
            assert r["judge"] == 8 and r["quality"] == 80.0


def test_dry_run_lists_runs(env, capsys):
    rc, rows = run(env, "--dry-run")
    assert rc == 0 and rows == []
    out = capsys.readouterr().out
    assert len(json.loads(out)) == 6
    assert not (env[0] / "out").exists()


def test_cost_cap_skips(env):
    count = env[0] / "count.log"
    rc, rows = run(env, "--cost-cap", "2.5", agent=f"--fix-arms cheap --cost 1.0 --count-log {sh(count)}")
    assert rc == 0 and len(rows) == 6
    assert [r["end"] for r in rows].count("skipped") == 3
    assert len(count.read_text(encoding="utf-8").splitlines()) == 3
    assert all(r["end"] != "skipped" for r in rows[:3])


def test_timeout_kills_by_pid(env):
    t0 = time.time()
    rc, rows = run(env, "--timeout", "1", agent="--sleep 30")
    assert rows and time.time() - t0 < 25  # a missed kill would wait 30 s per run
    assert all(r["end"] == "timeout" for r in rows)


def test_hidden_test_not_visible_to_agent(env):
    listing = env[0] / "listing.txt"
    rc, rows = run(env, agent=f"--fix-arms cheap --list-to {sh(listing)}", n="3")
    assert rc == 0
    text = listing.read_text(encoding="utf-8")
    assert "test_m.py" in text and "test_hidden" not in text


def test_case_missing_keys_refuses(env, capsys):
    tmp, cases = env
    bad = tmp / "bad.json"
    bad.write_text(json.dumps([{"id": "c1"}]), encoding="utf-8")
    assert ab.replay_main([str(bad), "--arms", "default,cheap", "--n", "3"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error:") and "Traceback" not in err
