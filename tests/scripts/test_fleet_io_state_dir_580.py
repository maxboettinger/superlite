# tests/scripts/test_fleet_io_state_dir_580.py: a worker's stop records live in its state_dir (#580)
import json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402


def stop(wid, t):
    return {"ev": "stop", "agent_id": wid, "t": t}


def put(d, workers, **top):
    d.mkdir(parents=True, exist_ok=True)
    (d / "fleet.json").write_text(json.dumps({"on": True, "workers": workers, **top}), encoding="utf-8")


def test_latest_stop_reads_the_worker_state_dir(tmp_path):
    w, s = tmp_path / "W", tmp_path / "S"
    put(w, {"W1": {"state_dir": str(s)}})
    s.mkdir()
    (s / "metrics.jsonl").write_text(json.dumps(stop("W1", 7)) + "\n", encoding="utf-8")
    assert io.latest_stop(w, "W1", 0)["t"] == 7
    assert io.latest_stop(w, "W1", 0, stops=[])["t"] == 7  # a pre-read list of W is ignored


def test_latest_stop_same_folder_unchanged(tmp_path):
    w = tmp_path / "W"
    put(w, {"W1": {}})
    (w / "metrics.jsonl").write_text(json.dumps(stop("W1", 3)) + "\n", encoding="utf-8")
    assert io.latest_stop(w, "W1", 0)["t"] == 3
    assert io.latest_stop(w, "W1", 4) is None


def test_stopped_follows_moved_to(tmp_path, monkeypatch):
    s, w = tmp_path / "S", tmp_path / "W"
    s.mkdir()
    (s / "fleet.json").write_text(json.dumps({"on": False, "moved_to": str(w)}), encoding="utf-8")
    put(w, {"W1": {"sent": 5, "task": "T1", "pane_id": "p"}})
    seen = []
    monkeypatch.setattr(io, "pane_label", lambda sd, wid, text, timeout_ms=None: seen.append(sd) or True)
    assert io.stopped(s, "W1", 10) is True
    assert [str(x) for x in seen] == [str(w)]
