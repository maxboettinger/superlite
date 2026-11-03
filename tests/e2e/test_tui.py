import os
import shutil

import pytest

if not os.environ.get("SUPERLITE_E2E"):
    pytest.skip("SUPERLITE_E2E not set", allow_module_level=True)
if not shutil.which("tmux"):
    pytest.skip("tmux not on PATH", allow_module_level=True)

from tests.e2e.tui_driver import TuiSession, summary_counts  # noqa: E402

pytestmark = pytest.mark.e2e

PROMPT = (
    "Launch exactly one subagent of type general-purpose with run_in_background set to true. "
    "Its task: run the Bash command `sleep 12` six times, one call at a time, then reply \"done\". "
    "Do nothing else yourself; wait for its completion notification, then reply with the single word DONE."
)
TOOLS = ["Agent", "Bash(sleep:*)"]


def test_tui_session_start_injects_skill(tmp_path):
    with TuiSession(tmp_path, allowed_tools=TOOLS) as s:
        log = s.debug_log()
    assert "Hook SessionStart" in log
    assert "You have superlite" in log


def test_summary_timer_runs_for_a_background_agent(tmp_path):
    with TuiSession(tmp_path, allowed_tools=TOOLS) as s:
        s.send(PROMPT)
        assert s.wait_marker("SUBAGENT_STOPPED", min_seconds=75, timeout=240), s.pane()
        counts = summary_counts(s.debug_log())
    assert counts["timer_fired"] >= 1, counts
    assert counts["forking"] >= 1 or counts["notes"] >= 1, counts


def test_fork_switch_silences_summary_timer(tmp_path):
    with TuiSession(tmp_path, allowed_tools=TOOLS, env={"CLAUDE_CODE_FORK_SUBAGENT": "0"}) as s:
        s.send(PROMPT)
        assert s.wait_marker("SUBAGENT_STOPPED", min_seconds=75, timeout=240), s.pane()
        counts = summary_counts(s.debug_log())
    assert counts["timer_fired"] == 0, counts
