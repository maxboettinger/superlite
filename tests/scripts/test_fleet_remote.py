# tests/scripts/test_fleet_remote.py
import json, os, subprocess, sys, threading, time
from pathlib import Path
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402
import fleet_state as fs  # noqa: E402
import herdr_client as hc  # noqa: E402

TREE = str(FIXTURES / "fleet" / "remote-tree")


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    th = tmp_path / "trees"; th.mkdir()
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("FAKE_TREE_HOME", str(th))
    monkeypatch.setenv("FAKE_TREE_LOG", str(tmp_path / "log"))
    (home / "machine.json").write_text(json.dumps({"remote_tree": [TREE]}))
    monkeypatch.chdir(proj)
    return type("E", (), {"home": home, "trees": th, "proj": proj, "sd": sd, "log": tmp_path / "log"})


def calls(e):
    return [json.loads(x) for x in e.log.read_text().splitlines()] if e.log.exists() else []


def test_tree_argv(env):
    assert fr.tree_argv() == [TREE]
    (env.home / "machine.json").write_text(json.dumps({"remote_tree": "x"}))
    assert fr.tree_argv() is None
    (env.home / "machine.json").write_text(json.dumps({"remote_tree": [1]}))
    assert fr.tree_argv() is None
    (env.home / "machine.json").write_text(json.dumps({"room": 1}))
    assert fr.tree_argv() is None
    (env.home / "machine.json").unlink()
    assert fr.tree_argv() is None


def test_target_and_check(monkeypatch):
    rows = [{"label": "box", "enabled": True}, {"label": "off", "enabled": False}]
    monkeypatch.setattr(hc, "machines", lambda: rows, raising=False)
    assert fr.target("box") == "box"
    for bad in ("off", "nope"):
        with pytest.raises(fr.RemoteError, match=f"no enabled Herdr machine {bad} "):
            fr.target(bad)
    st = {"v": "reachable"}
    monkeypatch.setattr(hc, "machine_status", lambda label, timeout_ms=10000: st["v"], raising=False)
    assert fr.check("box") == ""
    st["v"] = "unreachable: ssh: connect to host box port 22: Connection refused"
    assert fr.check("box") == st["v"]

    def boom(label, timeout_ms=10000): raise hc.HerdrError("exit", "timeout")
    monkeypatch.setattr(hc, "machine_status", boom, raising=False)
    assert fr.check("box") == "herdr machine status failed: timeout"


def test_push_read_drop(env):
    (env.proj / ".superlite" / "briefs").mkdir()
    (env.proj / ".superlite" / "briefs" / "r.md").write_text("hi")
    out = fr.push("box", str(env.proj), "proj/W3", "abc123", [".superlite/briefs/r.md"])
    assert out == str(env.trees / "proj/W3")
    c = calls(env)[0]
    assert c["argv"] == ["push", "--host", "box", "--name", "proj/W3", "--base", "abc123", "--file", ".superlite/briefs/r.md", "--timeout", "120"]
    assert Path(c["cwd"]).resolve() == env.proj.resolve()
    assert (env.trees / "proj/W3/.superlite/briefs/r.md").read_text() == "hi"
    f = env.trees / "proj/W3/x.txt"; f.write_bytes(b"0123456789abc")
    assert fr.read("box", str(f), 10) == b"abc"
    assert fr.read("box", str(f) + "z") == b""
    assert fr.drop("box", str(env.proj), "proj/W3") is True
    assert fr.drop("box", str(env.proj), "proj/W3") is False


def test_push_errors(env, monkeypatch):
    with pytest.raises(fr.RemoteError, match="down unreachable: cannot reach down"):
        fr.push("down", str(env.proj), "n", None, [])
    with pytest.raises(fr.RemoteError, match="down unreachable"):
        fr.read("down", "/x")
    with pytest.raises(fr.RemoteError, match=r"box: remote_tree push: usage"):
        monkeypatch.setenv("SUPERLITE_HOME", str(env.home))
        (env.home / "machine.json").write_text(json.dumps({"remote_tree": [sys.executable, "-c", "import sys;sys.stderr.write('a\\nusage\\n');sys.exit(2)"]}))
        fr.push("box", str(env.proj), "n", None, [])
    (env.home / "machine.json").write_text("{}")
    with pytest.raises(fr.RemoteError, match="no remote_tree command in .*machine.json"):
        fr.push("box", str(env.proj), "n", None, [])
    (env.home / "machine.json").write_text(json.dumps({"remote_tree": [TREE]}))
    monkeypatch.setenv("FAKE_TREE_SLEEP", "30")
    with pytest.raises(fr.RemoteError, match="box: remote_tree push timed out after 11 s"):
        fr.push("box", str(env.proj), "n", None, [], timeout_s=1)


def test_tree_name(tmp_path):
    import hashlib

    def h(path):
        return hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:6]

    assert fr.tree_name(Path("/u/x/superlite-fleet-remote-919/.superlite"), "W3") == f"superlite-fleet-remote-919-{h('/u/x/superlite-fleet-remote-919')}/W3"
    assert fr.tree_name(Path("/u/x/my run/.superlite"), "W3") == f"my-run-{h('/u/x/my run')}/W3"
    a, b = fr.tree_name(Path("/u/a/app/.superlite"), "W1"), fr.tree_name(Path("/u/b/app/.superlite"), "W1")
    assert a != b and a.startswith("app-") and b.startswith("app-")
    assert a == fr.tree_name(Path("/u/a/app/.superlite"), "W1")


def test_plugin(env, monkeypatch):
    sl = env.proj.parent / "sl"; sl.mkdir()
    genv = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for c in (["init", "-q"], ["-c", "user.name=a", "-c", "user.email=a@b", "commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(["git", "-C", str(sl), *c], check=True, env=genv)
    sha = subprocess.run(["git", "-C", str(sl), "rev-parse", "HEAD"], capture_output=True, text=True, env=genv).stdout.strip()
    monkeypatch.delenv("GIT_DIR", raising=False)
    assert fr.plugin("box", str(sl)) == str(env.trees / "plugin" / sha[:12])
    assert calls(env)[0]["argv"][:6] == ["push", "--host", "box", "--name", "plugin/" + sha[:12], "--base"]
    assert calls(env)[0]["argv"][6] == sha


def test_mapper():
    m = fr.mapper([("/u/proj", "/h/W3"), ("/u/proj/.superlite", "/h/W3/.superlite"), ("/u/sl", "/h/plugin/abc")])
    assert m("cd /u/proj; cat /u/proj/.superlite/b.md; /u/sl/x") == "cd /h/W3; cat /h/W3/.superlite/b.md; /h/plugin/abc/x"
    assert m("/u/project") == "/u/project"
    assert m("/u/proj.bak") == "/u/proj.bak"
    assert m("see /u/proj. Then /u/sl, ok") == "see /h/W3. Then /h/plugin/abc, ok"


def line(wid, tr, t=1):
    return json.dumps({"ev": "stop", "t": t, "agent_id": wid, "transcript": tr, "last": "x"}) + "\n"


@pytest.fixture
def synced(env):
    tree = env.trees / "proj" / "W3"; (tree / ".superlite").mkdir(parents=True)
    tr = env.trees / "s.jsonl"; tr.write_text("one\n")
    (env.sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {"W3": {"remote": {"label": "box", "tree": str(tree), "sd": str(tree / ".superlite"), "name": "proj/W3", "plugin": "", "offset": 0, "tr": {}}}}}))
    env.metrics = tree / ".superlite" / "metrics.jsonl"; env.tr = tr
    return env


def mirrored(e):
    p = e.sd / "remote" / "W3" / "metrics.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def test_sync_basic_and_other_worker(synced):
    e = synced
    e.metrics.write_text(line("W3", str(e.tr)) + line("W4", str(e.tr)))
    assert fr.sync(e.sd, "W3") == 1
    got = mirrored(e)
    assert [g["agent_id"] for g in got] == ["W3"]
    assert got[0]["transcript"] == str(e.sd / "remote" / "W3" / "s.jsonl")
    assert (e.sd / "remote" / "W3" / "s.jsonl").read_text() == "one\n"
    assert fr.sync(e.sd, "W3") == 0


def test_sync_other_worker(synced):
    e = synced
    e.metrics.write_text(line("W4", str(e.tr)) + line("W44", str(e.tr)))
    assert fr.sync(e.sd, "W3") == 0
    assert mirrored(e) == []
    assert not (e.sd / "remote" / "W3" / "s.jsonl").exists()


def test_sync_partial_line(synced):
    e = synced
    full = line("W3", str(e.tr))
    e.metrics.write_text(full[:-1])
    assert fr.sync(e.sd, "W3") == 0 and mirrored(e) == []
    e.metrics.write_text(full)
    assert fr.sync(e.sd, "W3") == 1 and len(mirrored(e)) == 1


def test_sync_transcript_by_offset(synced):
    e = synced
    e.metrics.write_text(line("W3", str(e.tr)))
    fr.sync(e.sd, "W3")
    e.tr.write_text("one\ntwo\n")
    e.metrics.write_text(line("W3", str(e.tr)) + line("W3", str(e.tr), 2) + line("W3", str(e.tr), 3))
    assert fr.sync(e.sd, "W3") == 2
    assert (e.sd / "remote" / "W3" / "s.jsonl").read_text() == "one\ntwo\n"
    assert json.loads((e.sd / "fleet.json").read_text())["workers"]["W3"]["remote"]["tr"] == {str(e.tr): 8}


def test_sync_down(synced):
    e = synced
    e.metrics.write_text(line("W3", str(e.tr)))
    rec = json.loads((e.sd / "fleet.json").read_text())
    rec["workers"]["W3"]["remote"]["label"] = "down"
    (e.sd / "fleet.json").write_text(json.dumps(rec))
    assert fr.sync(e.sd, "W3") == -1
    assert json.loads((e.sd / "fleet.json").read_text())["workers"]["W3"]["remote"]["offset"] == 0


def test_sync_reads_outside_the_lock(synced, monkeypatch):
    e = synced
    e.metrics.write_text(line("W3", str(e.tr)))
    monkeypatch.setenv("FAKE_TREE_SLEEP", "1.5")
    t = threading.Thread(target=fr.sync, args=(e.sd, "W3"))
    t.start()
    for _ in range(100):
        if calls(e):
            break
        time.sleep(0.02)
    t0 = time.monotonic()
    with fs.locked(e.sd):
        waited = time.monotonic() - t0
    t.join()
    assert waited < 0.75
    assert len(mirrored(e)) == 1


def test_sync_concurrent_appends_once(synced, monkeypatch):
    e = synced
    e.metrics.write_text(line("W3", str(e.tr)))
    monkeypatch.setenv("FAKE_TREE_SLEEP", "0.3")
    res = []
    ts = [threading.Thread(target=lambda: res.append(fr.sync(e.sd, "W3"))) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(res) == [0, 1]
    assert len(mirrored(e)) == 1
    assert (e.sd / "remote" / "W3" / "s.jsonl").read_text() == "one\n"
    assert json.loads((e.sd / "fleet.json").read_text())["workers"]["W3"]["remote"]["tr"] == {str(e.tr): 4}


@pytest.mark.parametrize("exc", [subprocess.TimeoutExpired("git", 30), FileNotFoundError("git")])
def test_plugin_git_failure_is_remote_error(env, monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(fr.subprocess, "run", boom)
    with pytest.raises(fr.RemoteError, match="git rev-parse"):
        fr.plugin("box", str(env.proj))
