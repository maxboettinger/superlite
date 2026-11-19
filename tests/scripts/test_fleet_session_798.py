"""fleet spawn says when a worker lands outside the Aqua session (#798)."""
from __future__ import annotations

import json

import pytest

from test_fleet import fleet, world  # noqa: F401,E402  (world is a fixture; it puts the scripts on sys.path)

import gui_session  # noqa: E402

MAC = {"test": "xcodebuild test -scheme App -destination 'platform=macOS' {only_testing}"}
IOS = {"test": "xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 16'"}
HEAD = "launchd session Background, not Aqua: a worker spawned now cannot launch or drive a Mac app window or run a macOS xcodebuild test; "


@pytest.fixture
def session(monkeypatch):
    monkeypatch.delenv("SUPERLITE_GUI_CHECK", raising=False)

    def set_kind(k):
        monkeypatch.setattr(gui_session, "session_kind", lambda *a, **kw: k)
    return set_kind


def test_warning_for_a_macos_test_in_background(session):
    session("Background")
    w = gui_session.spawn_warning(MAC)
    assert w.startswith(HEAD)
    assert gui_session.FALLBACK in w
    assert w.endswith("; SUPERLITE_GUI_CHECK=0 skips this check")


@pytest.mark.parametrize("cfg,kind", [(MAC, "Aqua"), (MAC, None), (IOS, "Background"), (None, "Background"),
                                      ({"test": "pytest -q"}, "Background"), ("not a dict", "Background")])
def test_no_warning(session, cfg, kind):
    session(kind)
    assert gui_session.spawn_warning(cfg) is None


def test_launch_entry_for_macos_warns(session):
    session("Background")
    cfg = {"test": "pytest -q", "launch": {"macOS": {"worker": True, "data": "", "why": ""}}}
    assert gui_session.spawn_warning(cfg).startswith(HEAD)


def test_launch_entry_worker_false_is_quiet(session):
    session("Background")
    cfg = {"test": "pytest -q", "launch": {"macOS": {"worker": False, "data": "", "why": "needs a login"}}}
    assert gui_session.spawn_warning(cfg) is None


def test_env_switch_turns_it_off(session, monkeypatch):
    session("Background")
    monkeypatch.setenv("SUPERLITE_GUI_CHECK", "0")
    assert gui_session.spawn_warning(MAC) is None


def test_spawn_prints_the_warning_once(world, session, capsys):
    (world.sd / "test-cmd.json").write_text(json.dumps(MAC), encoding="utf-8")
    session("Background")
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 0
    cap = capsys.readouterr()
    assert cap.err.count("fleet: warning: " + HEAD) == 1
    assert "W1 account=" in cap.out


def test_spawn_quiet_in_aqua(world, session, capsys):
    (world.sd / "test-cmd.json").write_text(json.dumps(MAC), encoding="utf-8")
    session("Aqua")
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 0
    assert "launchd session" not in capsys.readouterr().err


def test_spawn_survives_a_failing_check(world, session, capsys, monkeypatch):
    (world.sd / "test-cmd.json").write_text(json.dumps(MAC), encoding="utf-8")

    def boom(*a, **kw):
        raise RuntimeError("launchctl broke")
    monkeypatch.setattr(gui_session, "session_kind", boom)
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 0
    assert "W1 account=" in capsys.readouterr().out
