# tests/scripts/test_fleet_remote_fetch.py
import json, os, subprocess, sys
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402

TREE = str(FIXTURES / "fleet" / "remote-tree")
REF = "refs/superlite/remote/p-1a2b3c/W2/stop"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True, text=True, env=env, check=True).stdout.strip()


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    th = tmp_path / "trees"; th.mkdir()
    proj = tmp_path / "proj"; proj.mkdir()
    git(proj, "init", "-q")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("FAKE_TREE_HOME", str(th))
    monkeypatch.setenv("FAKE_TREE_LOG", str(tmp_path / "log"))
    (home / "machine.json").write_text(json.dumps({"remote_tree": [TREE]}))
    return type("E", (), {"trees": th, "proj": proj, "log": tmp_path / "log"})


def test_fetch_brings_objects(env):
    host = env.trees / "p-1a2b3c" / "W2"; host.mkdir(parents=True)
    git(host, "init", "-q")
    (host / "a.txt").write_text("hi")
    git(host, "add", "a.txt"); git(host, "commit", "-q", "-m", "x")
    sha = git(host, "rev-parse", "HEAD")
    git(host, "update-ref", REF, sha)
    assert fr.fetch("box", str(env.proj), "p-1a2b3c/W2", REF) == sha
    assert git(env.proj, "rev-parse", "refs/maxapp/box/p-1a2b3c/W2/superlite/remote/p-1a2b3c/W2/stop") == sha
    assert git(env.proj, "show", f"{sha}:a.txt") == "hi"
    argv = json.loads(env.log.read_text().splitlines()[0])
    assert argv["argv"] == ["fetch", "--host", "box", "--name", "p-1a2b3c/W2", "--ref", REF, "--timeout", "120"]
    assert argv["cwd"] == str(env.proj.resolve()) or argv["cwd"] == str(env.proj)


def test_fetch_errors(env):
    with pytest.raises(fr.RemoteError, match="down unreachable: "):
        fr.fetch("down", str(env.proj), "p/W1", REF)
    host = env.trees / "p" / "W1"; host.mkdir(parents=True)
    git(host, "init", "-q")
    with pytest.raises(fr.RemoteError, match="box: remote_tree fetch: no such ref"):
        fr.fetch("box", str(env.proj), "p/W1", REF)


def test_remote_home():
    assert fr.remote_home("/home/u/.maxapp/trees/superlite/p-1a2b3c/W2") == "/home/u"
    with pytest.raises(fr.RemoteError, match="cannot tell the home folder from tree path /x/y"):
        fr.remote_home("/x/y")
