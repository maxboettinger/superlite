# tests/scripts/test_fleet_waits_909.py: fleet status names the test or build command a busy worker waits on (#909)
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_waits as fw  # noqa: E402
import herdr_client as hc  # noqa: E402

PROCS = [(100, 1, 600, "-zsh"), (150, 100, 590, "claude --model sonnet"), (200, 150, 500, "/bin/zsh -c sl run_tests --full"),
         (201, 200, 490, "python3 /x/run_tests.py --full"), (202, 201, 480, "python3 -m pytest tests -q"), (300, 1, 50, "-zsh")]


@pytest.mark.parametrize("args,want", [
    ("/usr/bin/python3 /x/scripts/run_tests.py --full --task T3", "run_tests --full --task T3"),
    ("bash /x/scripts/sl run_tests --fast a.py", "run_tests --fast a.py"),
    ("python3 -m pytest tests -q", "pytest tests -q"),
    ("/x/usr/bin/xcodebuild test -scheme App", "xcodebuild test -scheme App"),
    ("maxapp test", "maxapp test"),
    ("npm run test", "npm run test"),
    ("/bin/zsh -c sl run_tests --full", None),
    ("git status", None),
    ("claude --model sonnet", None),
])
def test_label_examples(args, want):
    assert fw.label(args) == want


def test_label_cut_at_40():
    out = fw.label("/usr/bin/xcodebuild test -scheme App -destination platform=iOS_Simulator,name=iPhone_15_Pro_Max -derivedDataPath .build")
    assert len(out) <= 40 and out.startswith("xcodebuild test")


@pytest.mark.parametrize("text,want", [("41:07", 2467), ("02:03:04", 7384), ("1-02:03:04", 93784), ("abc", None)])
def test_etime_examples(text, want):
    assert fw.etime_s(text) == want


def test_waits_on_example():
    assert fw.waits_on({"W1": 100, "W2": 300}, PROCS) == {"W1": ("run_tests --full", 490)}


def test_suffixes_reads_shell_pid_and_ps(monkeypatch):
    calls = []

    def call(args, *a, **k):
        calls.append(args)
        return {"process_info": {"shell_pid": 100, "x": 1}}
    monkeypatch.setattr(hc, "call", call)
    monkeypatch.setattr(fw, "_ps", lambda: PROCS)
    got = fw.suffixes(None, {"W1": {"state": "busy", "pane_id": "p1"}, "W2": {"state": "ready", "pane_id": "p2"}})
    assert got == {"W1": " waits on run_tests --full 8 min"}
    assert calls == [["pane", "process-info", "--pane", "p1"]]
    monkeypatch.setattr(fw, "_ps", lambda: [(100, 1, 600, "-zsh"), (200, 100, 30, "maxapp test")])
    assert fw.suffixes(None, {"W1": {"state": "busy", "pane_id": "p1"}}) == {"W1": " waits on maxapp test 30 s"}


def test_suffixes_skips_remote_and_idle(monkeypatch):
    def call(*a, **k):
        raise AssertionError("herdr called")
    monkeypatch.setattr(hc, "call", call)
    monkeypatch.setattr(fw, "_ps", lambda: PROCS)
    assert fw.suffixes(None, {"W1": {"state": "busy", "pane_id": "p1", "machine": "m"}, "W2": {"state": "ready", "pane_id": "p2"}}) == {}


def test_suffixes_error_is_empty(monkeypatch):
    def call(*a, **k):
        raise hc.HerdrError("timeout", "x")
    monkeypatch.setattr(hc, "call", call)
    monkeypatch.setattr(fw, "_ps", lambda: PROCS)
    assert fw.suffixes(None, {"W1": {"state": "busy", "pane_id": "p1"}}) == {}
