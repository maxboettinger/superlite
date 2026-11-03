import json

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

AGENTS = ["implementer", "implementer-haiku", "package-reviewer", "final-reviewer",
          "fixer-sonnet", "fixer-sonnet-high", "fixer-opus"]
PONG = "Reply with the single word PONG. Do not use tools."


def _env(tmp_path):
    return {"SUPERLITE_HOME": str(tmp_path / "_home")}


def _work(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    return w


def _run_marker(w):
    (w / ".superlite").mkdir()
    (w / ".superlite" / "stable.json").write_text("{}")


def _lines(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_plugin_loads_clean(tmp_path):
    s = harness.run_headless(PONG, cwd=_work(tmp_path), env=_env(tmp_path), max_turns=2)
    assert "superlite" in json.dumps(s.init["plugins"])
    assert not s.init.get("plugin_errors")
    agents = json.dumps(s.init["agents"])
    for a in AGENTS:
        assert "superlite:" + a in agents
    assert s.text.strip() == "PONG"
    assert s.cost_usd < 0.05


def test_session_start_reports_project_state(tmp_path):
    w = _work(tmp_path)
    s = harness.run_headless(PONG, cwd=w, env=_env(tmp_path), max_turns=2)
    outs = [o for o in s.hook_outputs("SessionStart") if "You have superlite" in o]
    assert len(outs) == 1
    assert "Project state: empty folder" in outs[0]
    g = tmp_path / "git"
    g.mkdir()
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=g, check=True)
    (g / "app.py").write_text("print(1)\n")
    s = harness.run_headless(PONG, cwd=g, env=_env(tmp_path), max_turns=2)
    outs = [o for o in s.hook_outputs("SessionStart") if "You have superlite" in o]
    assert len(outs) == 1
    assert "Project state: existing code" in outs[0]


def test_rewrite_test_runs_during_a_run(tmp_path):
    w = _work(tmp_path)
    _run_marker(w)
    (w / "tests").mkdir()
    (w / "tests" / "test_one.py").write_text("def test_one(): assert True\n")
    s = harness.run_headless("Use the Bash tool to run exactly: pytest -q", cwd=w, env=_env(tmp_path),
                             allowed_tools=["Bash(pytest:*)", "Bash(*sl*)"], max_turns=4)
    outs = [o for o in s.hook_outputs("PreToolUse") if "run_tests" in o]
    assert len(outs) == 1
    assert '"run_in_background":true' in outs[0].replace(" ", "")
    inc = w / ".superlite" / "incidents.jsonl"
    assert inc.exists() and "rule-rewrite" in inc.read_text()


def test_run_hooks_record_agent_metrics(tmp_path):
    w = _work(tmp_path)
    _run_marker(w)
    prompt = ("Launch exactly one general-purpose subagent with run_in_background set to true whose only "
              "task is to reply with the word PONG, wait for it, then reply DONE.")
    harness.run_headless(prompt, cwd=w, env=_env(tmp_path), allowed_tools=["Agent"], max_turns=6)
    recs = _lines(w / ".superlite" / "metrics.jsonl")
    launch = [r for r in recs if r.get("ev") == "launch"]
    stop = [r for r in recs if r.get("ev") == "stop"]
    assert len(launch) == 1 and len(stop) == 1
    assert launch[0]["agent_id"] == stop[0]["agent_id"]
    from pathlib import Path
    assert Path(stop[0]["transcript"]).exists()
