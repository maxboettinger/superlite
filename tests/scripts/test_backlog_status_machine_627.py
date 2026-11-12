# tests/scripts/test_backlog_status_machine_627.py
import argparse
import os
import sys
from collections import namedtuple
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_state  # noqa: E402

GB = 1024 ** 3
Usage = namedtuple("Usage", "total used free")


def _fake_slot(tmp_path, body):
    d = tmp_path / "bin"
    d.mkdir()
    if body is not None:
        f = d / "maxapp-slot"
        f.write_text("#!/bin/sh\n" + body + "\n")
        f.chmod(0o755)
    return d


def _setup(monkeypatch, tmp_path, body):
    d = _fake_slot(tmp_path, body)
    monkeypatch.setenv("PATH", str(d))
    monkeypatch.setattr(backlog.shutil, "disk_usage", lambda p: Usage(0, 0, int(123.4 * GB)))


def test_machine_line_with_slots(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "echo 1 2")
    assert backlog.machine_line(tmp_path) == "machine: 123.4 GB free disk; build slots 1/2 busy (maxapp-slot)"


def test_machine_line_without_slots(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, None)
    assert backlog.machine_line(tmp_path) == "machine: 123.4 GB free disk"


def test_machine_line_bad_slot_output(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "echo x")
    assert backlog.machine_line(tmp_path) == "machine: 123.4 GB free disk"
    (tmp_path / "bin" / "maxapp-slot").write_text("#!/bin/sh\nexit 2\n")
    assert backlog.machine_line(tmp_path) == "machine: 123.4 GB free disk"


def _status(monkeypatch, tmp_path, capsys, states):
    _setup(monkeypatch, tmp_path, "echo 0 3")
    monkeypatch.setattr(backlog, "_root", lambda: tmp_path)
    monkeypatch.setattr(backlog, "refresh_open", lambda r: {})
    monkeypatch.setattr(backlog_state, "load", lambda p: {"batches": [{"id": f"B{i}", "state": s} for i, s in enumerate(states)]})
    monkeypatch.setattr(backlog_state, "status_lines", lambda d, all_=False: ["B0 row"])
    assert backlog.cmd_status(argparse.Namespace(all=False)) == 0
    return capsys.readouterr().out.splitlines()


def test_status_machine_line_with_running_batch(monkeypatch, tmp_path, capsys):
    lines = _status(monkeypatch, tmp_path, capsys, ["running"])
    assert [x for x in lines if x.startswith("machine: ")] == [lines[-1]]
    assert not any(x.startswith("next:") for x in lines)


def test_no_machine_line_without_open_batch(monkeypatch, tmp_path, capsys):
    lines = _status(monkeypatch, tmp_path, capsys, [])
    assert not any(x.startswith("machine: ") for x in lines)
    assert lines[-1].startswith("next:")


def test_no_machine_line_when_every_batch_shipped(monkeypatch, tmp_path, capsys):
    lines = _status(monkeypatch, tmp_path, capsys, ["shipped"])
    assert not any(x.startswith("machine: ") for x in lines)
    assert lines[-1].startswith("next:")


def test_machine_line_before_next_line(monkeypatch, tmp_path, capsys):
    lines = _status(monkeypatch, tmp_path, capsys, ["planned", "parked"])
    m = [i for i, x in enumerate(lines) if x.startswith("machine: ")]
    n = [i for i, x in enumerate(lines) if x.startswith("next:")]
    assert len(m) == 1 and all(m[0] < j for j in n)
