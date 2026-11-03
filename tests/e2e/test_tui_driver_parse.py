from pathlib import Path

from tests.e2e import tui_driver


def test_needs_trust_and_ready_detection():
    assert tui_driver.needs_trust("... Yes, I trust this folder ...") is True
    assert tui_driver.needs_trust("? for shortcuts") is False
    ready = 'Try "how do I log an error?"\n? for shortcuts'
    assert tui_driver.is_ready(ready) is True
    assert tui_driver.is_ready("╭────╮\n│ > │\n╰────╯") is False
    assert tui_driver.needs_trust("╭────╮\n│ > │\n╰────╯") is False
    assert tui_driver.is_ready("... Yes, I trust this folder ...") is False


def test_summary_counts_counts_each_kind():
    log = (
        "[AgentSummary] Timer fired for agent a1\n"
        "[AgentSummary] Forking for summary\n"
        "[AgentSummary] Timer fired for agent a1\n"
        "[AgentSummary] Asking for summary from 382 characters of notes\n"
        "[AgentSummary] Stopping summarization\n"
        "unrelated line\n"
    )
    assert tui_driver.summary_counts(log) == {
        "timer_fired": 2, "forking": 1, "notes": 1, "stopped": 1}
    assert tui_driver.summary_counts("") == {
        "timer_fired": 0, "forking": 0, "notes": 0, "stopped": 0}


def test_settings_json_has_marker_hooks():
    s = tui_driver.TuiSession.settings_json(Path("/tmp/m.txt"))
    stop = s["hooks"]["Stop"][0]["hooks"][0]["command"]
    sub = s["hooks"]["SubagentStop"][0]["hooks"][0]["command"]
    assert "STOPPED" in stop and "SUBAGENT_STOPPED" not in stop and ">>" in stop
    assert "SUBAGENT_STOPPED" in sub and ">>" in sub
    assert "$E2E_MARKER" in stop or "/tmp/m.txt" in stop


def test_is_ready_on_auto_mode_prompt_without_shortcuts_hint():
    pane = "Claude Code\n" + "─" * 40 + "\n❯ Try \"x\"\n" + "─" * 40 + "\n  ⏵⏵ auto mode on"
    assert tui_driver.is_ready(pane) is True
    assert tui_driver.is_ready("Claude Code v2\n  notice") is False


def test_close_kills_server_even_if_send_keys_raises(tmp_path):
    calls = []
    s = tui_driver.TuiSession(tmp_path)

    def fake(*args):
        calls.append(args)
        if args[0] == "send-keys":
            raise RuntimeError("boom")

    s._tmux = fake
    s.close()
    assert calls[-1] == ("kill-server",)


def test_socket_unique_and_debug_log_missing(tmp_path):
    a, b = tui_driver.TuiSession(tmp_path), tui_driver.TuiSession(tmp_path)
    assert a.socket != b.socket
    assert a.debug_log() == ""


def test_wait_marker_whole_line(tmp_path):
    s = tui_driver.TuiSession(tmp_path)
    s.marker_path.write_text("SUBAGENT_STOPPED\n")
    assert s.wait_marker("STOPPED", timeout=1) is False
    assert s.wait_marker("SUBAGENT_STOPPED", timeout=1) is True
