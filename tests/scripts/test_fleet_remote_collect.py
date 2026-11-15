# tests/scripts/test_fleet_remote_collect.py
import json, os, subprocess, sys
import pytest
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote_collect as frc  # noqa: E402
import fleet_state as fs  # noqa: E402

TREE = str(FIXTURES / "fleet" / "remote-tree")
NAME = "p-1a2b3c/W2"
REF = "refs/superlite/remote/p-1a2b3c/W2/stop"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True, text=True, env=env, check=True).stdout.strip()


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    th = tmp_path / "trees"; th.mkdir()
    proj = tmp_path / "proj"; (proj / "src").mkdir(parents=True)
    git(proj, "init", "-q")
    (proj / "src" / "a.py").write_text("one\n")
    (proj / "docs").mkdir(); (proj / "docs" / "n.md").write_text("n\n")
    git(proj, "add", "-A"); git(proj, "commit", "-q", "-m", "base")
    start = git(proj, "rev-parse", "HEAD")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("FAKE_TREE_HOME", str(th))
    (home / "machine.json").write_text(json.dumps({"remote_tree": [TREE]}))
    sd = proj / ".superlite"; sd.mkdir()
    return type("E", (), {"trees": th, "proj": proj, "sd": sd, "start": start})


def worker(env, write=True, owns=("src/*.py",), snap="UNSET", machine="box"):
    remote = {"label": "box", "name": NAME, "project": str(env.proj), "start": env.start, "snapshot_ref": REF, "write": write, "owns": list(owns) if owns is not None else None}
    rec = {"state": "idle", "role": "implementer"}
    if machine:
        rec.update(machine=machine, remote=remote)
    fs.save(env.sd, {**fs.default(), "workers": {"W2": rec}})
    if snap != "UNSET":
        d = env.sd / "remote" / "W2"; d.mkdir(parents=True, exist_ok=True)
        lines = [{"ev": "stop", "agent_id": "W2"}] if snap is None else [{"ev": "stop", "agent_id": "W2", "snapshot": "old"}, {"ev": "stop", "agent_id": "W2", "snapshot": snap}]
        (d / "metrics.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))


def host_snapshot(env, files):
    host = env.trees / "p-1a2b3c" / "W2"
    git(env.proj, "clone", "-q", str(env.proj), str(host))
    for f, text in files.items():
        (host / f).parent.mkdir(parents=True, exist_ok=True)
        (host / f).write_text(text)
    git(host, "add", "-A"); git(host, "commit", "-q", "-m", "snap")
    sha = git(host, "rev-parse", "HEAD")
    git(host, "update-ref", REF, sha)
    return sha


def report():
    return {"status": "DONE", "files": ["src/a.py"], "concerns": []}


def collected(env):
    return fs.load(env.sd)["workers"]["W2"]["remote"].get("collected")


def test_collect_applies(env):
    sha = host_snapshot(env, {"src/a.py": "two\n", "docs/n.md": "changed\n"})
    worker(env, snap=sha)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "DONE"
    assert out["collected"] == {"applied": ["src/a.py"], "skipped": ["docs/n.md"], "sha": sha}
    assert out["concerns"] == ["remote changes outside the task not applied: docs/n.md"]
    assert (env.proj / "src" / "a.py").read_text() == "two\n"
    assert (env.proj / "docs" / "n.md").read_text() == "n\n"
    assert collected(env) == sha


def test_collect_twice_applies_once(env):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    worker(env, snap=sha)
    frc.collect(env.sd, "W2", report())
    (env.proj / "src" / "a.py").write_text("local later\n")
    r = report()
    assert frc.collect(env.sd, "W2", r) == report()
    assert (env.proj / "src" / "a.py").read_text() == "local later\n"


def test_collect_conflict_blocked(env):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    worker(env, snap=sha)
    (env.proj / "src" / "a.py").write_text("local\n")
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"] == [f"remote changes conflict with local edits: src/a.py (kept at refs/maxapp/box/{NAME}/superlite/remote/p-1a2b3c/W2/stop)"]
    assert (env.proj / "src" / "a.py").read_text() == "local\n"
    assert collected(env) is None


def test_collect_read_only_untouched(env):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    worker(env, write=False, snap=sha)
    assert frc.collect(env.sd, "W2", report()) == report()
    worker(env, snap=sha, machine=None)
    assert frc.collect(env.sd, "W2", report()) == report()
    assert (env.proj / "src" / "a.py").read_text() == "one\n"


def test_collect_no_snapshot(env):
    worker(env, snap=None)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED" and out["concerns"] == ["remote worker W2 left no snapshot"]
    worker(env)  # no mirrored record at all
    assert frc.collect(env.sd, "W2", report())["concerns"] == ["remote worker W2 left no snapshot"]


def test_collect_fetch_error(env):
    worker(env, snap="deadbeef")  # no host tree: fetch fails
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"][0].startswith("cannot fetch W2's work: box: remote_tree fetch:")
    assert collected(env) is None


def test_collect_regression_prefix_nested(env):
    sha = host_snapshot(env, {"src/a.py": "two\n", "tests/regression/a/b.py": "x\n"})
    worker(env, snap=sha)
    out = frc.collect(env.sd, "W2", report())
    assert out["collected"]["applied"] == ["src/a.py", "tests/regression/a/b.py"]
    assert (env.proj / "tests" / "regression" / "a" / "b.py").read_text() == "x\n"


def test_collect_apply_oserror_blocked(env, monkeypatch):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    worker(env, snap=sha)

    def boom(*a, **k):
        raise IsADirectoryError("src/a.py")
    monkeypatch.setattr(frc.remote_apply, "apply", boom)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"][0].startswith("cannot apply W2's work:")
    assert collected(env) is None


def test_collect_sha_mismatch_blocked(env):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    snap = "f" * 40
    worker(env, snap=snap)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"] == [f"fetched {sha} but the stop record names {snap}"]
    assert (env.proj / "src" / "a.py").read_text() == "one\n"
    assert collected(env) is None
