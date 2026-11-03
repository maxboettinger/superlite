import json
import os
from pathlib import Path

import pytest

from tests.e2e import harness
from tests.e2e.harness import HarnessError, parse_stream, scrubbed_env

FIXTURE = Path(__file__).parent / "fixtures" / "headless-pong.jsonl"
RESULT = '{"type":"result","subtype":"success","result":"ok","total_cost_usd":0}'


def test_parse_skips_malformed_lines():
    s = parse_stream(['not json', '{"type":"system","subtype":"init","plugins":["superlite"]}', RESULT])
    assert s.skipped == 1
    assert s.init["plugins"] == ["superlite"]
    assert s.text == "ok"


def test_parse_without_result_raises():
    with pytest.raises(HarnessError) as e:
        parse_stream(['{"type":"system","subtype":"init"}'], stderr="boom line")
    assert "boom line" in str(e.value)


def test_hook_outputs_filters_by_event():
    lines = [
        '{"type":"system","subtype":"hook_response","hook_event":"SessionStart","output":"a"}',
        '{"type":"system","subtype":"hook_response","hook_event":"Stop","output":"b"}',
        RESULT,
    ]
    s = parse_stream(lines)
    assert s.hook_outputs("SessionStart") == ["a"]
    assert len(s.hooks) == 2


def test_scrubbed_env_drops_session_vars(monkeypatch):
    names = ["CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
             "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_ENTRYPOINT",
             "CLAUDE_CODE_PLUGIN_DIRS", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "CLAUDE_ENV_FILE"]
    for n in names:
        monkeypatch.setenv(n, "x")
    monkeypatch.setenv("PATH", os.environ["PATH"])
    env = scrubbed_env({"X": "1"})
    assert all(n not in env for n in names)
    assert env["PATH"] and env["X"] == "1"


def test_fixture_pong_parses():
    s = parse_stream(FIXTURE.read_text().splitlines())
    assert "superlite" in json.dumps(s.init["plugins"])
    assert s.text == "PONG"
    outs = s.hook_outputs("SessionStart")
    assert len(outs) == 1 and "You have superlite" in outs[0]


@pytest.mark.e2e
def test_never_runs_without_env():
    # skipped by conftest unless SUPERLITE_E2E is set; passes when it runs under the flag
    assert os.environ.get("SUPERLITE_E2E")


def test_run_headless_argv_and_isolation(monkeypatch, tmp_path):
    seen = {}

    class P:
        stdout = RESULT
        stderr = ""

    def fake(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return P()

    monkeypatch.setattr(harness.subprocess, "run", fake)
    harness.run_headless("hi", cwd=tmp_path, allowed_tools=["Bash(pytest:*)", "Agent"], settings={"a": 1})
    cmd = seen["cmd"]
    i = cmd.index("--setting-sources")
    assert cmd[i + 1] == ""
    assert cmd[cmd.index("--plugin-dir") + 1] == str(harness.REPO_ROOT)
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert int(cmd[cmd.index("--max-turns") + 1]) <= 8
    assert cmd[-3:] == ["--allowedTools", "Bash(pytest:*)", "Agent"]
    assert cmd.index("--allowedTools") > cmd.index("-p") + 1
    assert seen["kw"]["stdin"] is harness.subprocess.DEVNULL
