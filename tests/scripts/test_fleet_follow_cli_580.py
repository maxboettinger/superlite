# tests/scripts/test_fleet_follow_cli_580.py: fleet commands and state.bind move the session's fleet into their folder (#580)
import json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_state as fs  # noqa: E402
import state  # noqa: E402


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for v in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(fleet, "agent_gone", lambda *a, **k: False)


def run(tmp_path, name):
    d = tmp_path / name / ".superlite"; d.mkdir(parents=True); return d


def session_fleet_in(S, sid="s1", workers=None):
    fs.save(S, {**fs.default(), "on": True, "owner_session": sid,
                "workers": workers if workers is not None else {"W1": {"name": "sl-a", "state": "busy", "task": "R1", "account": "x", "pane_id": "p"}}})
    fs.remember(S, sid)


def test_status_after_lint_bind_shows_busy_workers(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    state.bind(S); session_fleet_in(S)
    state.bind(W)
    capsys.readouterr()
    assert fleet.main(["status", "--plan", str(W)]) == 0
    out = capsys.readouterr().out
    assert "fleet: off" not in out and any(l.startswith("W1 busy") for l in out.splitlines())


def test_wait_delegation_follows_first(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    session_fleet_in(S)
    seen = []
    import fleet_io
    monkeypatch.setattr(fleet_io, "main", lambda argv: seen.append(fs.is_on(W)) or 0)
    assert fleet.main(["wait", "--plan", str(W)]) == 0
    assert seen == [True]
    assert f"fleet: this session's fleet moved from {S.resolve()} to {W.resolve()} (1 workers)" in capsys.readouterr().err


def test_fleet_on_elsewhere_follows_then_turns_on(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    session_fleet_in(S)
    assert fleet.main(["on", "--plan", str(W)]) == 0
    assert "W1" in fs.load(W)["workers"] and fs.is_on(W)


def test_status_names_moved_stub(tmp_path, capsys):
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    fs.save(S, {**fs.default(), "moved_to": str(W)})
    assert fleet.main(["status", "--plan", str(S)]) == 0
    assert f"fleet: off (moved to {W})" in capsys.readouterr().out


def test_spawn_blocked_names_moved_to(tmp_path, capsys):
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    fs.save(S, {**fs.default(), "moved_to": str(W)})
    assert fleet.main(["spawn", "--plan", str(S)]) == 3
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED:") and out.strip().endswith(f"; this fleet moved to {W}: pass --plan {W}")


def test_name_does_not_follow(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    session_fleet_in(S)
    assert fleet.main(["name", "--plan", str(W)]) == 0
    assert fs.is_on(S) and not fs.is_on(W)


def test_bind_without_fleet_prints_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, W = run(tmp_path, "S"), run(tmp_path, "W")
    state.bind(S); state.bind(W)
    assert capsys.readouterr().err == ""
