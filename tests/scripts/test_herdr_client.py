import json, os, sys
from pathlib import Path
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import herdr_client as hc  # noqa: E402
FAKE = FIXTURES / "fleet" / "herdr"

@pytest.fixture
def fake(tmp_path, monkeypatch):
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("SUPERLITE_HERDR_BIN", str(FAKE)); monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.delenv("FAKE_HERDR_REPLY", raising=False)
    def calls():
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return calls

def test_create_workspace_flags_and_ids(fake, monkeypatch):
    ws, pane = hc.create_workspace("sl:x", "/proj", {"CLAUDE_CONFIG_DIR": "/u/.c1", "SUPERLITE_FLEET_WORKER": "W1"})
    assert (ws, pane) == ("w6", "w6:p1")
    argv = fake()[0]
    assert argv[:5] == ["workspace", "create", "--label", "sl:x", "--cwd"] and argv.count("--env") == 2 and "--no-focus" in argv
    assert "CLAUDE_CONFIG_DIR=/u/.c1" in argv

def test_env_vars_become_repeated_env_flags(fake):
    hc.create_workspace("l", "/p", {"A": "1", "B": "2", "C": ""})
    argv = fake()[0]
    assert argv.count("--env") == 2 and "A=1" in argv and "B=2" in argv and "--no-focus" in argv

def test_split_pane_returns_new_id(fake):
    assert hc.split_pane("w6:p1", "right", "/proj", {}) == "w6:p2"
    assert fake()[0][:4] == ["pane", "split", "w6:p1", "--direction"]

def test_start_agent_ok_and_not_ready(fake, monkeypatch):
    assert hc.start_agent("sl-proj-w1", "w6:p1", ["--agent", "superlite:implementer"]) == "idle"
    argv = fake()[0]; assert "--" in argv and argv[argv.index("--") + 1:] == ["--agent", "superlite:implementer"]
    monkeypatch.setenv("FAKE_HERDR_REPLY", json.dumps({"error": {"code": "agent_not_ready", "message": "blocked during startup"}}))
    with pytest.raises(hc.HerdrError) as e: hc.start_agent("sl-proj-w1", "w6:p1", [])
    assert e.value.code == "agent_not_ready"

def test_prompt_passes_each_until_flag(fake):
    assert hc.prompt("W1", "hi there", ["done", "blocked"], 1000) == "done"
    argv = fake()[0]
    assert argv[:4] == ["agent", "prompt", "W1", "hi there"] and argv.count("--until") == 2 and argv[-2:] == ["--timeout", "1000"]

def test_error_payload_raises_with_code(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_REPLY", json.dumps({"error": {"code": "agent_prompt_stalled", "message": "no activity"}}))
    with pytest.raises(hc.HerdrError) as e: hc.prompt("W1", "x", ["done"], 10)
    assert (e.value.code, e.value.message) == ("agent_prompt_stalled", "no activity")

def test_nonzero_exit_raises_with_stderr(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_REPLY", "EXIT 7 boom")
    with pytest.raises(hc.HerdrError) as e: hc.call(["agent", "list"])
    assert e.value.code == "exit" and "boom" in e.value.message

def test_nonzero_exit_with_json_error_keeps_code(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_REPLY", 'EXIT 3 {"error":{"code":"agent_not_ready","message":"trust"}}')
    with pytest.raises(hc.HerdrError) as e: hc.call(["agent", "list"])
    assert e.value.code == "agent_not_ready" and e.value.message == "trust"

def test_agent_states_maps_name_to_status_and_skips_unnamed_agents(fake):
    assert hc.agent_states() == {"sl-proj-w1": "done", "sl-proj-w2": "working"} and hc.agent_state("sl-proj-w2") == "idle"

def test_read_text_returns_plain_stdout(fake):
    assert "Yes, I trust this folder" in hc.read_screen("W1")
    assert fake()[0][:3] == ["agent", "read", "W1"]

def test_send_keys_wait_close(fake):
    hc.send_keys("W1", ["Down", "Enter"]); assert hc.wait_state("W1", ["idle"], 500) == "idle"
    hc.close_pane("w6:p2"); hc.close_workspace("w6")
    assert [c[:2] for c in fake()] == [["agent", "send-keys"], ["agent", "wait"], ["pane", "close"], ["workspace", "close"]]

def test_missing_binary_is_herdr_error(monkeypatch):
    monkeypatch.setenv("SUPERLITE_HERDR_BIN", "/nonexistent/herdr")
    with pytest.raises(hc.HerdrError) as e: hc.call(["agent", "list"])
    assert e.value.code == "missing"

def test_exit_agent_sends_exit_without_wait(fake):
    hc.exit_agent("W1")
    argv = fake()[0]
    assert argv == ["agent", "prompt", "W1", "/exit", "--timeout", "5000"]

def test_string_error_is_herdr_error(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_REPLY", json.dumps({"error": "boom"}))
    with pytest.raises(hc.HerdrError) as e:
        hc.call(["agent", "list"])
    assert e.value.code == "error" and e.value.message == "boom"

def test_list_payload_is_parse_error(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_REPLY", "[1, 2]")
    with pytest.raises(hc.HerdrError) as e:
        hc.call(["agent", "list"])
    assert e.value.code == "parse"


@pytest.mark.parametrize("call", [
    lambda: hc.create_workspace("l", "/tmp", {}),
    lambda: hc.start_agent("a", "p1", ["x"]),
    lambda: hc.agent_states(),
])
def test_success_reply_without_result_shape_is_parse_error(fake, monkeypatch, call):
    monkeypatch.setenv("FAKE_HERDR_REPLY", '{"result":{}}')
    with pytest.raises(hc.HerdrError) as e:
        call()
    assert e.value.code == "parse"

@pytest.mark.parametrize("name", ["W1", "1w", ".claude-account1", "a" * 33])
def test_start_agent_surfaces_invalid_agent_name_of_herdr_0_9_5(fake, name):
    with pytest.raises(hc.HerdrError) as e: hc.start_agent(name, "w6:p1", [])
    assert e.value.code == "invalid_agent_name"
