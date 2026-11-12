"""herdr_client helpers a fleet restore needs: session id, all agents, pane existence (#577)."""
from __future__ import annotations

import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import herdr_client as hc  # noqa: E402


def fake(monkeypatch, result=None, raises=None):
    seen = []

    def call(args, *a, **k):
        seen.append(list(args))
        if raises:
            raise hc.HerdrError(*raises)
        return result

    monkeypatch.setattr(hc, "call", call)
    return seen


def test_session_of_shapes():
    assert hc.session_of({"agent_session": {"kind": "id", "value": "84f86f13-02e3"}}) == "84f86f13-02e3"
    assert hc.session_of({"name": "x"}) is None
    assert hc.session_of({"agent_session": {"value": ""}}) is None


def test_agent_session_reads_agent_get(monkeypatch):
    seen = fake(monkeypatch, {"agent": {"agent_session": {"value": "abc"}}})
    assert hc.agent_session("sl-a-w1") == "abc"
    assert seen == [["agent", "get", "sl-a-w1"]]
    fake(monkeypatch, {"agent": {}})
    assert hc.agent_session("sl-a-w1") is None


def test_all_agents_keeps_unnamed(monkeypatch):
    rows = [{"pane_id": "w5:p9"}, {"name": "sl-a-w1", "pane_id": "w6:p1"}, "junk"]
    seen = fake(monkeypatch, {"agents": rows})
    assert hc.all_agents() == rows[:2]
    assert seen == [["agent", "list"]]


def test_pane_exists_false_on_not_found(monkeypatch):
    seen = fake(monkeypatch, raises=("pane_not_found", "no pane"))
    assert hc.pane_exists("w6:p1") is False
    assert seen == [["pane", "get", "w6:p1"]]
    fake(monkeypatch, {"pane": {}})
    assert hc.pane_exists("w6:p1") is True


@pytest.mark.parametrize("code", ["missing", "timeout"])
def test_pane_exists_reraises_missing_and_timeout(monkeypatch, code):
    fake(monkeypatch, raises=(code, "x"))
    with pytest.raises(hc.HerdrError):
        hc.pane_exists("w6:p1")
