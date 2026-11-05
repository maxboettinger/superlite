import json, sys
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_state as fs  # noqa: E402

def sd(tmp_path):
    d = tmp_path / ".superlite"; d.mkdir(); return d

def test_load_missing_file_returns_default(tmp_path):
    assert fs.load(sd(tmp_path)) == {"on": False, "workers": {}, "next": 1, "accounts": [], "workspace_id": None, "root_pane": None, "label": ""}
    assert fs.is_on(tmp_path / ".superlite") is False

def test_set_on_then_is_on_and_ids(tmp_path):
    d = sd(tmp_path); fs.set_on(d, "sl:x", ["claude1"])
    assert fs.is_on(d) is True and fs.load(d)["accounts"] == ["claude1"]
    assert fs.next_id(d) == "W1" and fs.next_id(d) == "W2" and fs.load(d)["next"] == 3

def test_worker_lifecycle(tmp_path):
    d = sd(tmp_path); fs.set_on(d, "sl:x", ["claude1"])
    w = fs.add_worker(d, "W1", "w6:p1", "claude1", "superlite:implementer", "sonnet")
    assert w["state"] == "starting" and w["pane_id"] == "w6:p1"
    assert fs.set_state(d, "W1", "busy", "T3")["task"] == "T3"
    assert list(fs.workers(d, "busy")) == ["W1"] and fs.workers(d, "ready") == {}
    fs.set_workspace(d, "w6", "w6:p1"); assert fs.load(d)["workspace_id"] == "w6"

def test_save_is_atomic_and_rereadable(tmp_path):
    d = sd(tmp_path); data = fs.load(d); data["on"] = True; fs.save(d, data)
    assert json.loads(fs.path(d).read_text())["on"] is True and not list(d.glob("*.tmp"))
    assert fs.load(d) == data

def test_set_state_unknown_worker_raises_keyerror(tmp_path):
    import pytest
    d = sd(tmp_path); fs.set_on(d, "sl:x", [])
    with pytest.raises(KeyError): fs.set_state(d, "W9", "busy")

def test_set_off_removes_file_and_is_on_false(tmp_path):
    d = sd(tmp_path); fs.set_on(d, "sl:x", []); fs.set_off(d)
    assert not fs.path(d).exists() and fs.is_on(d) is False

def test_next_id_parallel_is_unique(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    d = sd(tmp_path)
    with ThreadPoolExecutor(8) as ex:
        ids = list(ex.map(lambda _: fs.next_id(d), range(8)))
    assert sorted(ids) == sorted("W%d" % i for i in range(1, 9)) and not list(d.glob("*.tmp"))

def test_set_off_under_concurrent_writer(tmp_path):
    import threading, time
    d = sd(tmp_path); fs.set_on(d, "sl:x", ["claude1"])
    held = threading.Event()
    def writer():
        with fs.locked(d):
            held.set(); data = fs.load(d); time.sleep(0.3); data["on"] = True; fs.save(d, data)
    t = threading.Thread(target=writer); t.start(); held.wait()
    fs.set_off(d); t.join()
    assert not fs.path(d).exists()
