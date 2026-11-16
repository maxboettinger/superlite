"""#933 T5: `dispatch`, `agent_stop` and `review` lines from capture-agent-launch and capture-agent-stop."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import telemetry  # noqa: E402
import telemetry_agents  # noqa: E402

LAUNCH = ROOT / "hooks" / "capture-agent-launch"
STOP = ROOT / "hooks" / "capture-agent-stop"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
SESSION_ENV = ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "stable.json").write_text('{"run_id": "20261116T130500Z-a1b2c3"}')
    return tmp_path


def run(hook, proj, payload):
    env = {k: v for k, v in os.environ.items() if k not in SESSION_ENV}
    env["CLAUDE_PROJECT_DIR"] = str(proj)
    return subprocess.run([BASH, str(hook)], input=json.dumps(payload), capture_output=True, text=True, env=env, cwd=proj)


def launch(desc="T3 parser", model="claude-sonnet-5-5", agent_id="a1", typ="superlite:implementer"):
    return {"tool_name": "Agent", "session_id": "s1",
            "tool_input": {"subagent_type": typ, "description": desc, "prompt": "secret prompt"},
            "tool_response": {"status": "async_launched", "agentId": agent_id, "description": desc,
                              "resolvedModel": model}}


def entry(ts, mid, text=None, tools=0, usage=None):
    content = [{"type": "tool_use", "id": f"{mid}-{i}", "name": "Read", "input": {}} for i in range(tools)]
    if text is not None:
        content.append({"type": "text", "text": text})
    return {"type": "assistant", "timestamp": ts, "isSidechain": True,
            "message": {"id": mid, "model": "claude-sonnet-5-5", "content": content, "usage": usage or {}}}


def transcript(tmp_path, last="Status: DONE", name="t.jsonl"):
    rows = [
        {"type": "user", "timestamp": "2026-11-16T12:00:00.000Z", "message": {"content": "private task text"}},
        entry("2026-11-16T12:00:10.000Z", "m1", tools=2,
              usage={"input_tokens": 60, "output_tokens": 10, "cache_read_input_tokens": 20, "cache_creation_input_tokens": 4}),
        entry("2026-11-16T12:00:30.000Z", "m2", text=last, tools=1,
              usage={"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50,
                     "cache_creation": {"ephemeral_5m_input_tokens": 6, "ephemeral_1h_input_tokens": 4}}),
    ]
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def stop_payload(tr, typ="superlite:implementer", agent_id="a1"):
    return {"hook_event_name": "SubagentStop", "agent_id": agent_id, "agent_type": typ, "session_id": "s1",
            "agent_transcript_path": str(tr), "last_assistant_message": "x"}


def events(kind):
    return [e for e in telemetry.read_events() if e["kind"] == kind]


def test_kind_dispatch_agent_launch(proj):
    r = run(LAUNCH, proj, launch())
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (e,) = events("dispatch")
    assert telemetry.validate(e) == []
    assert (e["task"], e["role"], e["agent_type"], e["model"]) == ("T3", "implementer", "superlite:implementer", "claude-sonnet-5-5")
    assert e["run"] == "20261116T130500Z-a1b2c3" and e["session"] == "s1"
    assert "parser" not in json.dumps(e) and "secret" not in json.dumps(e)
    assert (proj / ".superlite" / "metrics.jsonl").exists()


def test_kind_dispatch_agent_launch_no_task_id(proj):
    run(LAUNCH, proj, launch(desc="Review the thing"))
    (e,) = events("dispatch")
    assert e["task"] is None and telemetry.validate(e) == []


def test_kind_agent_stop_subagent(proj, tmp_path):
    tr = transcript(tmp_path)
    run(LAUNCH, proj, launch())
    r = run(STOP, proj, stop_payload(tr))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (e,) = events("agent_stop")
    assert telemetry.validate(e) == []
    assert e["role"] == "implementer" and e["model"] == "claude-sonnet-5-5" and e["status"] == "DONE"
    assert e["tokens"] == {"in": 160, "out": 30, "cache_read": 70, "cache_write": 14}
    assert e["tool_calls"] == 3 and e["duration_s"] == 30.0 and e["cost_usd"] > 0
    assert e["task"] == "T3" and e["session"] == "s1"
    assert "private task" not in json.dumps(e)
    assert events("review") == []


def test_agent_stop_function(tmp_path):
    tr = transcript(tmp_path)
    d = telemetry_agents.agent_stop(tr, "superlite:implementer")
    assert d["role"] == "implementer" and d["status"] == "DONE" and d["tool_calls"] == 3
    assert d["tokens"]["in"] == 160 and d["task"] is None
    assert telemetry_agents.agent_stop(tmp_path / "none.jsonl", "superlite:implementer") is None


def test_kind_review_final_reviewer(proj, tmp_path):
    last = "Verdict: CHANGES_REQUESTED\n- a.py:3 - bad - fix it - tier 1\n- b.py:9 - worse - fix it - tier 1\n"
    tr = transcript(tmp_path, last=last)
    run(STOP, proj, stop_payload(tr, "superlite:final-reviewer"))
    (e,) = events("review")
    assert telemetry.validate(e) == []
    assert (e["review_kind"], e["verdict"], e["findings"], e["round"]) == ("final", "CHANGES_REQUESTED", 2, 1)
    assert "bad" not in json.dumps(e)
    run(STOP, proj, stop_payload(tr, "superlite:final-reviewer"))
    assert [x["round"] for x in events("review")] == [1, 2]
    assert len(events("agent_stop")) == 2


def test_kind_review_package_reviewer(proj, tmp_path):
    tr = transcript(tmp_path, last="Verdict: APPROVED\n")
    run(STOP, proj, stop_payload(tr, "superlite:package-reviewer"))
    (e,) = events("review")
    assert (e["review_kind"], e["verdict"], e["findings"], e["round"]) == ("package", "APPROVED", 0, 1)


def test_agent_stop_missing_transcript(proj, tmp_path):
    r = run(STOP, proj, stop_payload(tmp_path / "gone.jsonl"))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert events("agent_stop") == []
    rows = [json.loads(x) for x in (proj / ".superlite" / "metrics.jsonl").read_text().splitlines()]
    assert [x["ev"] for x in rows] == ["stop"]


def test_agent_hooks_outside_run_silent(tmp_path):
    (tmp_path / ".git").mkdir()
    tr = transcript(tmp_path)
    for hook, payload in ((LAUNCH, launch()), (STOP, stop_payload(tr))):
        r = run(hook, tmp_path, payload)
        assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert telemetry.read_events() == []
