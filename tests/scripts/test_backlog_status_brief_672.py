"""#672: status names a low disk and the simulators a shipped batch still owes; the lead brief names simulators.txt."""
import argparse
import sys
from collections import namedtuple
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_brief as bb  # noqa: E402
import backlog_run  # noqa: E402
import backlog_state  # noqa: E402
import trees  # noqa: E402

GB = 1024 ** 3
Usage = namedtuple("Usage", "total used free")
U1 = "4F1A2B3C-0000-4000-8000-00000000000A"
U2 = "5B2C3D4E-0000-4000-8000-00000000000B"


def _levels(monkeypatch, free_gb, floor="20", warn="50"):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", floor)
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", warn)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(backlog.shutil, "disk_usage", lambda p: Usage(0, 0, int(free_gb * GB)))
    if not hasattr(trees, "disk_levels"):
        def fake_levels():
            import os
            return float(os.environ["SUPERLITE_DISK_FLOOR_GB"]), float(os.environ["SUPERLITE_DISK_WARN_GB"])
        monkeypatch.setattr(trees, "disk_levels", fake_levels, raising=False)
    if not hasattr(backlog_run, "simulators_owed_line"):
        def fake_line(bid, owed):
            return f"{bid} simulators owed: " + ", ".join(f"{o['sim']} ({o['why']})" for o in owed) + \
                "; delete each with xcrun simctl delete <udid>, then sl backlog status"
        monkeypatch.setattr(backlog_run, "simulators_owed_line", fake_line, raising=False)


def test_machine_line_below_warn(monkeypatch, tmp_path):
    _levels(monkeypatch, 41.2)
    assert backlog.machine_line(tmp_path) == "machine: 41.2 GB free disk, below the 50 GB warn level"


def test_machine_line_below_floor(monkeypatch, tmp_path):
    _levels(monkeypatch, 12.0)
    assert backlog.machine_line(tmp_path) == \
        "machine: 12.0 GB free disk, below the 20 GB floor (sl backlog start starts no lead)"


def test_machine_line_levels_off(monkeypatch, tmp_path):
    _levels(monkeypatch, 12.0, floor="0", warn="0")
    assert backlog.machine_line(tmp_path) == "machine: 12.0 GB free disk"


def _status(monkeypatch, tmp_path, capsys, batches):
    monkeypatch.setattr(backlog, "_root", lambda: tmp_path)
    monkeypatch.setattr(backlog, "refresh_open", lambda r: {})
    backlog_state.update(backlog_state.path(tmp_path), lambda d: d["batches"].extend(batches))
    assert backlog.cmd_status(argparse.Namespace(all=False)) == 0
    return capsys.readouterr().out.splitlines()


def _shipped(bid, owed=None):
    b = {"id": bid, "state": "shipped", "issues": [1], "topic": "t", "files": []}
    if owed is not None:
        b["simulators_owed"] = owed
    return b


def test_status_low_disk_without_open_batch(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 41.2)
    lines = _status(monkeypatch, tmp_path, capsys, [_shipped("B1")])
    assert lines[-1] == "next: sl backlog plan"
    assert lines[-2] == "machine: 41.2 GB free disk, below the 50 GB warn level"


def test_status_no_machine_line_with_enough_disk(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)
    lines = _status(monkeypatch, tmp_path, capsys, [_shipped("B1")])
    assert not any(x.startswith("machine: ") for x in lines)


def _owed(*sims):
    return [{"sim": s, "why": "delete failed"} for s in sims]


def test_status_owed_line_and_reread(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)
    calls = []
    monkeypatch.setattr(trees, "present_simulators", lambda s: calls.append(list(s)) or [U2], raising=False)
    lines = _status(monkeypatch, tmp_path, capsys, [_shipped("B7", _owed(U1, U2))])
    assert calls == [[U1, U2]]
    owed = [x for x in lines if "simulators owed" in x]
    assert len(owed) == 1 and owed[0].startswith(f"B7 simulators owed: {U2} (") and U1 not in owed[0]
    assert lines.index(owed[0]) < lines.index("next: sl backlog plan")
    kept = backlog_state.load(backlog_state.path(tmp_path))["batches"][0]
    assert kept["simulators_owed"] == _owed(U2)[0:1]


def test_status_owed_emptied_drops_key(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)
    monkeypatch.setattr(trees, "present_simulators", lambda s: [], raising=False)
    lines = _status(monkeypatch, tmp_path, capsys, [_shipped("B7", _owed(U1))])
    assert not any("simulators owed" in x for x in lines)
    assert "simulators_owed" not in backlog_state.load(backlog_state.path(tmp_path))["batches"][0]


def test_status_owed_kept_when_list_fails(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)
    monkeypatch.setattr(trees, "present_simulators", lambda s: None, raising=False)
    lines = _status(monkeypatch, tmp_path, capsys, [_shipped("B7", _owed(U1, U2))])
    owed = [x for x in lines if "simulators owed" in x]
    assert len(owed) == 1 and U1 in owed[0] and U2 in owed[0]
    assert len(backlog_state.load(backlog_state.path(tmp_path))["batches"][0]["simulators_owed"]) == 2


def test_status_owed_all_present_does_not_write(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)
    monkeypatch.setattr(trees, "present_simulators", lambda s: [U1, U2], raising=False)
    monkeypatch.setattr(backlog, "_root", lambda: tmp_path)
    monkeypatch.setattr(backlog, "refresh_open", lambda r: {})
    backlog_state.update(backlog_state.path(tmp_path), lambda d: d["batches"].append(_shipped("B7", _owed(U1, U2))))
    calls = []
    monkeypatch.setattr(backlog_state, "update", lambda *a, **k: calls.append(a))
    assert backlog.cmd_status(argparse.Namespace(all=False)) == 0
    assert "simulators owed" in capsys.readouterr().out
    assert calls == []


def test_status_no_simctl_call_without_owed(monkeypatch, tmp_path, capsys):
    _levels(monkeypatch, 90.0)

    def boom(s):
        raise AssertionError("simctl called")
    monkeypatch.setattr(trees, "present_simulators", boom, raising=False)
    _status(monkeypatch, tmp_path, capsys, [_shipped("B1")])


def test_brief_names_simulators_file():
    b = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}
    ctx = {"sl": "/x/sl", "backlog_md": "/x/backlog.md", "repo": "o/r", "worktree": "/w/b1",
           "approved": {"by": "AskUserQuestion", "time": "t"}}
    t = bb.lead_brief(b, ctx)
    assert "/w/b1/.superlite/simulators.txt" in t
    assert "copy this sentence into every worker brief" in t.split("\nSimulators:")[1].split("\n")[0]
    t2 = bb.lead_brief(b, {k: v for k, v in ctx.items() if k != "worktree"})
    assert ".superlite/simulators.txt of your worktree" in t2
