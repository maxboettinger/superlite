"""layer_store: shared green-hash store, run lock, changed-file diff."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "layer_store.py"


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def ls():
    """The layer_store module under test, loaded from its file."""
    spec = importlib.util.spec_from_file_location("layer_store", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["layer_store"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def s(tmp_path):
    return tmp_path / "store" / "test-layers.json"


def test_store_path_shared_by_worktree(ls, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", str(wt))
    expected = main.resolve() / ".git" / "superlite" / "test-layers.json"
    from_main, from_wt = ls.store_path(main), ls.store_path(wt)
    assert from_main == expected
    assert from_wt == expected
    assert from_main.is_absolute() and from_wt.is_absolute()


def test_store_path_outside_git(ls, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert ls.store_path(plain) == plain / ".superlite" / "test-layers.json"


def test_record_then_green(ls, s):
    ls.record_green(s, "unit", "h1", {"a.py": "1"})
    assert ls.is_green(s, "unit", "h1") is True
    assert ls.is_green(s, "unit", "h2") is False
    assert ls.is_green(s, "tui", "h1") is False


def test_green_list_capped(ls, s):
    for i in range(205):
        ls.record_green(s, "unit", f"h{i}", {})
    assert not any(ls.is_green(s, "unit", f"h{i}") for i in range(5))
    assert ls.is_green(s, "unit", "h5")
    assert ls.is_green(s, "unit", "h204")
    assert len(json.loads(s.read_text())["layers"]["unit"]["green"]) == 200


def test_record_is_idempotent(ls, s):
    ls.record_green(s, "unit", "h1", {"a.py": "1"})
    ls.record_green(s, "unit", "h1", {"a.py": "1"})
    assert json.loads(s.read_text())["layers"]["unit"]["green"].count("h1") == 1


def test_changed_files(ls, s):
    ls.record_green(s, "unit", "h1", {"a.py": "1", "b.py": "2", "d.py": "5"})
    assert ls.changed_files(s, "unit", {"a.py": "1", "b.py": "3", "c.py": "4"}) == ["b.py", "c.py", "d.py"]
    assert ls.changed_files(s, "tui", {"x": "1"}) == ["x"]
    assert ls.has_manifest(s, "unit") is True
    assert ls.has_manifest(s, "tui") is False


def test_running_live_pid(ls, s):
    ls.start_run(s, "unit", "h1", os.getpid())
    assert ls.running(s, "unit", "h1") is True
    assert ls.running(s, "unit", "h2") is False
    ls.end_run(s, "unit")
    assert ls.running(s, "unit", "h1") is False


def test_running_dead_pid(ls, s):
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    ls.start_run(s, "unit", "h1", child.pid)
    assert ls.running(s, "unit", "h1") is False


def test_corrupt_store(ls, s):
    s.parent.mkdir(parents=True)
    s.write_text("not json")
    assert ls.is_green(s, "unit", "h1") is False
    ls.record_green(s, "unit", "h1", {"a.py": "1"})
    data = json.loads(s.read_text())
    assert data["version"] == 1
    assert ls.is_green(s, "unit", "h1") is True


def test_no_temp_files_left(ls, s):
    ls.record_green(s, "unit", "h1", {"a.py": "1"})
    ls.start_run(s, "unit", "h1", os.getpid())
    assert sorted(p.name for p in s.parent.iterdir()) == ["running.json", "test-layers.json", "test-layers.lock"]


def test_running_huge_pid_does_not_raise(ls, s):
    ls.start_run(s, "unit", "d", 2 ** 70)
    assert ls.running(s, "unit", "d") is False
    assert ls.pid_alive(2 ** 70) is False


def test_running_permission_error_counts_alive(ls, s, monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX os.kill semantics")
    ls.start_run(s, "unit", "h1", 999999)

    def deny(pid, sig):
        raise PermissionError

    monkeypatch.setattr(ls.os, "kill", deny)
    assert ls.running(s, "unit", "h1") is True


WRITER = """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("layer_store", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
store, layer = Path(sys.argv[2]), sys.argv[3]
for i in range(40):
    m.record_green(store, layer, layer + str(i), {})
    m.start_run(store, layer, "d", i + 1)
"""


def test_concurrent_writers_keep_every_entry(ls, s):
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SCRIPT), str(s), layer]) for layer in ("a", "b", "c")]
    assert [p.wait() for p in procs] == [0, 0, 0]
    for layer in ("a", "b", "c"):
        assert ls.is_green(s, layer, layer + "39")
        assert ls.is_green(s, layer, layer + "0")
        assert layer in json.loads((s.parent / "running.json").read_text())
