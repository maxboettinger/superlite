# tests/scripts/test_fleet_placement.py
import json, socket, sys
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_placement as fp  # noqa: E402
import fleet_state as fs  # noqa: E402
import herdr_client as hc  # noqa: E402

ROOM = str(FIXTURES / "fleet" / "room")
READY = {"machines": [{"name": "host1", "state": "ready", "room": 12}, {"name": "box", "state": "ready", "room": 12},
                      {"name": "far", "state": "unreachable", "room": 0}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("FAKE_ROOM_LOG", str(tmp_path / "log"))
    monkeypatch.setenv("FAKE_ROOM_JSON", json.dumps(READY))
    monkeypatch.delenv("FAKE_ROOM_EXIT", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "host1.local")
    monkeypatch.setattr(hc, "machines", lambda: [{"label": "box", "enabled": True}])
    (home / "machine.json").write_text(json.dumps({"remote_room": [ROOM], "remote_tree": ["x"]}))
    return type("E", (), {"home": home, "proj": proj, "sd": sd, "log": tmp_path / "log"})


def runs(e):
    return len(e.log.read_text().splitlines()) if e.log.exists() else 0


def workers(e, *machines):
    d = fs.default()
    for i, m in enumerate(machines):
        w = {"state": "busy"}
        if m:
            w["machine"] = m
        d["workers"][f"w{i}"] = w
    fs.save(e.sd, d)


def test_room_maps_local(env):
    assert fp.room(env.sd, now=100.0) == {"local": {"state": "ready", "room": 12}, "box": {"state": "ready", "room": 12},
                                          "far": {"state": "unreachable", "room": 0}}


def test_cache_ttl(env):
    fp.room(env.sd, now=100.0)
    fp.room(env.sd, now=130.0)
    assert runs(env) == 1
    assert (env.sd / "room.json").exists()
    fp.room(env.sd, now=161.0)
    assert runs(env) == 2


@pytest.mark.parametrize("how", ["nokey", "exit", "json"])
def test_room_failure_means_local(env, monkeypatch, how):
    if how == "nokey":
        (env.home / "machine.json").write_text("{}")
    elif how == "exit":
        monkeypatch.setenv("FAKE_ROOM_EXIT", "1")
    else:
        monkeypatch.setenv("FAKE_ROOM_JSON", "not json")
    assert fp.room(env.sd, now=1.0) == {"local": {"state": "unknown", "room": None}}
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_room_timeout_means_local(env, monkeypatch):
    import subprocess
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("x", 20)
    monkeypatch.setattr(subprocess, "run", boom)
    assert fp.room(env.sd, now=1.0) == {"local": {"state": "unknown", "room": None}}


def test_enabled_and_mode(env):
    assert fp.enabled(env.sd) is True
    fp.set_mode(env.sd, "local")
    assert fp.enabled(env.sd) is False
    fp.set_mode(env.sd, "spread")
    assert fp.enabled(env.sd) is True
    with pytest.raises(ValueError):
        fp.set_mode(env.sd, "x")
    (env.home / "machine.json").write_text(json.dumps({"remote_room": [ROOM]}))
    assert fp.enabled(env.sd) is False


def test_tie_goes_local(env):
    workers(env, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_busier_local_goes_remote(env):
    workers(env, None, None, None)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) == "box"


def test_remote_workers_count(env):
    workers(env, None, None, None, "box", "box")
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


@pytest.mark.parametrize("marker", ["a.xcodeproj", "a.xcworkspace", "Package.swift"])
def test_xcode_project_local(env, marker):
    workers(env, None, None, None)
    (env.proj / marker).mkdir()
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_swift_language_local(env):
    workers(env, None, None, None)
    (env.sd / "test-cmd.json").write_text(json.dumps({"language": "swift"}))
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


@pytest.mark.parametrize("role", ["checker", "writer", "lead"])
def test_local_roles(env, role):
    workers(env, None, None, None)
    assert fp.choose(env.sd, role, env.proj, now=1.0) is None


def test_disabled_local(env):
    workers(env, None, None, None)
    fp.set_mode(env.sd, "local")
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_not_saved_machine(env, monkeypatch):
    workers(env, None, None, None)
    monkeypatch.setattr(hc, "machines", lambda: [{"label": "box", "enabled": False}])
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_skip_expires(env):
    workers(env, None, None, None)
    fp.skip(env.sd, "box", "unreachable", now=1000.0)
    assert fp.choose(env.sd, "implementer", env.proj, now=1100.0) is None
    assert fp.choose(env.sd, "implementer", env.proj, now=1000.0 + 601) == "box"


def _margin_room(monkeypatch, box_room):
    rows = [{"name": "host1", "state": "ready", "room": 12}, {"name": "box", "state": "ready", "room": box_room}]
    monkeypatch.setenv("FAKE_ROOM_JSON", json.dumps({"machines": rows}))


def _set_margin(e, value):
    (e.home / "machine.json").write_text(json.dumps({"remote_room": [ROOM], "remote_tree": ["x"], "remote_margin": value}))


def test_margin_zero_prefers_roomier_box(env, monkeypatch):
    _margin_room(monkeypatch, 13)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None  # default margin 2: 11 < 12
    (env.sd / "room.json").unlink()
    _set_margin(env, 0)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) == "box"


@pytest.mark.parametrize("bad", ["0", 1.5, True, None, [0]])
def test_margin_non_int_means_two(env, monkeypatch, bad):
    _margin_room(monkeypatch, 13)
    _set_margin(env, bad)
    assert fp.choose(env.sd, "implementer", env.proj, now=1.0) is None


def test_docstring_names_margin_key():
    assert "remote_margin" in fp.__doc__


def test_skip_threads_keep_both_entries(env, monkeypatch):
    import threading, time
    real = fp._skips

    def slow(sd):
        d = real(sd)
        time.sleep(0.2)  # widen the read-modify-write window
        return d
    monkeypatch.setattr(fp, "_skips", slow)
    ts = [threading.Thread(target=fp.skip, args=(env.sd, label, "x", 10.0, 1000.0)) for label in ("a", "b")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert set(json.loads((env.sd / "room-skip.json").read_text())) == {"a", "b"}


def test_cache_files_replaced_never_half_written(env):
    fp.skip(env.sd, "a", "x", now=1000.0)
    with open(env.sd / "room-skip.json") as old:  # a reader holding the file during the next write
        fp.skip(env.sd, "b", "x", now=1000.0)
        assert set(json.loads(old.read())) == {"a"}  # the old content whole, not a truncated one
    assert set(json.loads((env.sd / "room-skip.json").read_text())) == {"a", "b"}
    fp.room(env.sd, now=1000.0)
    assert sorted(p.name for p in env.sd.iterdir() if p.name.startswith("room")) == ["room-skip.json", "room-skip.json.lock", "room.json"]
