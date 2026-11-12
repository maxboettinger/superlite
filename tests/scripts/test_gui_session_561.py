"""gui_session: macOS xcodebuild test needs the desktop session (#561)."""
from __future__ import annotations

import os
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import gui_session  # noqa: E402

TMD = (
    "Testing failed:\n\tFailed to establish communication with the test runner. (Underlying Error: The connection to "
    "service named com.apple.testmanagerd.control was invalidated: failed at lookup with error 3 - No such process.)\n"
    "\tTest session results, code coverage, and logs:\n\t\t/tmp/x.xcresult\n\n** TEST FAILED **\n"
)


def fake(tmp_path, body, name="launchctl"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


def on_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")


@pytest.mark.parametrize("cmd,want", [
    ("xcodebuild test -scheme App -destination 'platform=macOS'", True),
    ("xcodebuild -scheme App test", True),
    ("cd app && /usr/bin/xcodebuild test-without-building -xctestrun a.xctestrun", True),
    ("xcodebuild test -scheme A -destination 'platform=macOS,variant=Mac Catalyst'", True),
    ("xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 16'", False),
    ("xcodebuild build -scheme App", False),
    ("swift test", False),
    ("maxapp remote 'xcodebuild test -scheme App'", False),
    ("xcodebuild test -scheme 'A && B'", True),
    ("xcodebuild test -scheme 'A", False),
    ("env FOO=1 xcodebuild test -scheme A", True),
    ("FOO=1 xcrun xcodebuild test -scheme A", True),
    ("xcodebuild test -scheme A -destination 'id=ABC'", False),
])
def test_needs_gui(cmd, want):
    assert gui_session.needs_gui(cmd) is want


def test_quoted_operator_not_split():
    assert gui_session.needs_gui("xcodebuild test -scheme 'A && B'") is True


def test_unbalanced_quote_false():
    assert gui_session.needs_gui("xcodebuild test -scheme 'A") is False


def test_env_prefix():
    assert gui_session.needs_gui("env FOO=1 xcodebuild test -scheme A") is True


def test_destination_id_not_checked():
    assert gui_session.needs_gui("xcodebuild test -scheme A -destination 'id=ABC'") is False


def test_session_kind(tmp_path):
    assert gui_session.session_kind(str(fake(tmp_path, "echo Background"))) == "Background"
    assert gui_session.session_kind(str(fake(tmp_path, "echo Aqua"))) == "Aqua"
    assert gui_session.session_kind(str(tmp_path / "missing")) is None
    assert gui_session.session_kind(str(fake(tmp_path, "exit 1"))) is None
    assert gui_session.session_kind(str(fake(tmp_path, "true"))) is None


def test_timeout_none(tmp_path, monkeypatch):
    monkeypatch.setattr(gui_session, "TIMEOUT", 0.5)
    assert gui_session.session_kind(str(fake(tmp_path, "sleep 10"))) is None


def test_preflight(tmp_path, monkeypatch):
    fake(tmp_path, "echo Background")
    on_path(monkeypatch, tmp_path)
    monkeypatch.delenv("SUPERLITE_GUI_CHECK", raising=False)
    msg = gui_session.preflight(["xcodebuild test -scheme App"])
    assert msg.startswith("ENV-ERROR: no macOS GUI session (launchctl managername: Background, not Aqua): ")
    assert gui_session.preflight(["swift test"]) is None
    monkeypatch.setenv("SUPERLITE_GUI_CHECK", "0")
    assert gui_session.preflight(["xcodebuild test -scheme App"]) is None
    monkeypatch.delenv("SUPERLITE_GUI_CHECK")
    fake(tmp_path, "echo Aqua")
    assert gui_session.preflight(["xcodebuild test -scheme App"]) is None


def test_preflight_skips_launchctl_without_gui_command(tmp_path, monkeypatch):
    fake(tmp_path, f"touch {tmp_path}/called; echo Background")
    on_path(monkeypatch, tmp_path)
    assert gui_session.preflight(["swift test"]) is None
    assert not (tmp_path / "called").exists()


def test_runner_unreachable():
    assert gui_session.runner_unreachable(TMD) is True
    assert gui_session.runner_unreachable(TMD + "Executed 3 tests, with 1 failure (0 unexpected) in 0.2 (0.3) seconds\n") is False
    assert gui_session.runner_unreachable("** TEST FAILED **\n") is False
    assert gui_session.runner_unreachable(TMD + "Test Case '-[A b]' passed (0.1 seconds).\n") is False


def test_swift_testing_counts_as_executed():
    assert gui_session.runner_unreachable(TMD + "✔ Test foo() passed after 0.001 seconds.\n") is False


def test_unreachable_reason():
    assert gui_session.unreachable_reason("Background").startswith(
        "ENV-ERROR: xcodebuild could not reach its test runner (testmanagerd) and ran no test: "
        "an environment fault, not a test failure; session: Background; ")
    assert "session: unknown" in gui_session.unreachable_reason(None)


def test_texts_capped(tmp_path, monkeypatch):
    fake(tmp_path, "echo Background")
    on_path(monkeypatch, tmp_path)
    monkeypatch.delenv("SUPERLITE_GUI_CHECK", raising=False)
    for text in (gui_session.preflight(["xcodebuild test"]), gui_session.unreachable_reason("Background"),
                 gui_session.unreachable_reason(None)):
        assert text.startswith("ENV-ERROR: ")
        assert len(text) <= 400
        assert "swift test" in text and "iOS Simulator" in text
