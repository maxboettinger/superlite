# tests/scripts/test_exit_agent_930.py: a lean agent (--disable-slash-commands) gets no /exit and no wait; slash=True keeps both (#930)
import json, sys
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
    return lambda: [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def test_exit_lean_sends_nothing(fake):
    assert hc.exit_agent("sl-x-w1") is None
    assert fake() == []


def test_exit_lean_explicit_sends_nothing(fake):
    hc.exit_agent("sl-x-w1", slash=False)
    assert fake() == []


def test_exit_lean_ignores_a_failing_herdr(fake, monkeypatch):
    monkeypatch.setenv("FAKE_HERDR_FAIL", "agent prompt")
    hc.exit_agent("sl-x-w1")
    assert fake() == []


def test_exit_slash_keeps_exit_and_wait(fake):
    hc.exit_agent("sl-x-w1", slash=True)
    assert [c[:4] for c in fake()] == [["agent", "prompt", "sl-x-w1", "/exit"], ["agent", "wait", "sl-x-w1", "--until"]]
