"""#659: predict_live counts a run waiting at an admission command like a held full-suite lock."""
from __future__ import annotations

import json
import os
import sys

from test_plan_tools import SCRIPTS
from test_predict_live_605 import CFG, DEAD, bind, project

sys.path.insert(0, str(SCRIPTS))
import predict_live  # noqa: E402


def note(folder, data, name="test-summary-r1.lockwait"):
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data)
    (folder / name).write_text(text, encoding="utf-8")


def other(tmp_path):
    sd = tmp_path / "other" / ".superlite"
    sd.mkdir(parents=True)
    bind("s1", sd, os.getpid())
    return sd


def test_contention_counts_admission_wait(tmp_path):
    root = project(tmp_path)
    note(other(tmp_path), {"admission": "gate", "pid": os.getpid(), "since": 1.0})
    assert predict_live.admission_waiting(root) is True
    c = predict_live.contention(root, CFG)
    assert c["full_lock"] is True
    assert c["full_factor"] == 1.5


def test_dead_pid_does_not_count(tmp_path):
    root = project(tmp_path)
    note(other(tmp_path), {"admission": "gate", "pid": DEAD, "since": 1.0})
    assert predict_live.admission_waiting(root) is False


def test_own_note_does_not_count(tmp_path):
    root = project(tmp_path)
    bind("s1", root / ".superlite", os.getpid())
    note(root / ".superlite", {"admission": "gate", "pid": os.getpid(), "since": 1.0})
    assert predict_live.admission_waiting(root) is False


def test_lock_note_is_not_an_admission_wait(tmp_path):
    root = project(tmp_path)
    note(other(tmp_path), {"lock": "x", "pid": os.getpid(), "since": 1.0})
    assert predict_live.admission_waiting(root) is False


def test_broken_note_is_skipped(tmp_path):
    root = project(tmp_path)
    sd = other(tmp_path)
    note(sd, "{not json", "test-summary-a.lockwait")
    note(sd, {"admission": "gate", "pid": os.getpid()}, "test-summary-b.lockwait")
    assert predict_live.admission_waiting(root) is True
