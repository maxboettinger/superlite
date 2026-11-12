"""`sl status` waiting line (#655): one line per waiting full run, read from the `.lockwait` notes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import status  # noqa: E402

LOCK = {"lock": "/h/locks/full-suite-python.lock", "holder": {"pid": 77, "root": "/r"}, "pid": 4242,
        "since": 1000.0, "place": 2, "queued": 3}


def note(sd, name, data):
    (sd / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def test_lock_note_line(tmp_path):
    note(tmp_path, "test-summary.lockwait", LOCK)
    assert status.waiting_lines(tmp_path, now=1720.0, alive=lambda p: True) == [
        "full run waiting: 12 min for the python full-suite lock, queue place 2 of 3 (held by pid 77 in /r)"]


def test_admission_note_line(tmp_path):
    note(tmp_path, "test-summary-r1.lockwait", {"admission": "gate", "pid": 4242, "since": 1000.0})
    assert status.waiting_lines(tmp_path, now=1190.0, alive=lambda p: True) == [
        "full run waiting: 3 min for the admission command gate"]


def test_dead_pid_skipped(tmp_path):
    note(tmp_path, "test-summary.lockwait", LOCK)
    note(tmp_path, "test-summary-r1.lockwait", {"admission": "gate", "pid": 4242, "since": 1000.0})
    assert status.waiting_lines(tmp_path, now=1720.0, alive=lambda p: False) == []


def test_note_without_place_or_holder(tmp_path):
    note(tmp_path, "test-summary.lockwait",
         {"lock": "/h/locks/full-suite-xcode.lock", "holder": {}, "pid": 1, "since": 0.0})
    assert status.waiting_lines(tmp_path, now=60.0, alive=lambda p: True) == [
        "full run waiting: 1 min for the xcode full-suite lock"]


def test_unreadable_note_skipped(tmp_path):
    note(tmp_path, "test-summary.lockwait", "{")
    assert status.waiting_lines(tmp_path, now=60.0, alive=lambda p: True) == []


def test_note_without_pid_skipped(tmp_path):
    note(tmp_path, "test-summary.lockwait", {"lock": "/x/full-suite-python.lock", "holder": {"pid": 2}})
    assert status.waiting_lines(tmp_path, now=60.0, alive=lambda p: True) == []


def test_overview_adds_line(tmp_path, monkeypatch):
    note(tmp_path, "test-summary.lockwait", {**LOCK, "pid": __import__("os").getpid(), "since": 0.0})
    lines = status.overview(tmp_path, None)
    i = next(n for n, ln in enumerate(lines) if ln.startswith("last test run:"))
    assert lines[i + 1].startswith("full run waiting: ")


def test_nonpositive_pid_not_alive():
    assert status.pid_alive(-1) is False and status.pid_alive(0) is False
