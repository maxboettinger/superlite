# tests/scripts/test_fleet_remote_collect_997.py: a stop record without a snapshot: collect retakes it in a host shell pane (#997)
import json, shutil, subprocess

import pytest
from test_fleet_remote_collect import env, host_snapshot, report, collected, frc, fs, git, NAME, REF  # noqa: F401
from test_fleet_remote_collect_953 import seed as seed_953
from test_plan_tools import SCRIPTS

PLUGIN = str(SCRIPTS.parents[2])
HEAD = "remote worker W2 left no snapshot: its stop hook took none (remote_apply snapshot failed or ran past 30 s); its tree {} stays on box; retaking it there failed: "


def host_tree(env, committed, uncommitted):
    host = env.trees / NAME
    git(env.proj, "clone", "-q", str(env.proj), str(host))
    (host / ".superlite").mkdir()
    for f, text in committed.items():
        (host / f).parent.mkdir(parents=True, exist_ok=True)
        (host / f).write_text(text)
    if committed:
        git(host, "add", "-A")
        git(host, "commit", "-q", "-m", "work")
    for f, text in uncommitted.items():
        (host / f).parent.mkdir(parents=True, exist_ok=True)
        (host / f).write_text(text)
    return host


def seed(env, host, plugin=PLUGIN):
    remote = {"label": "box", "name": NAME, "project": str(env.proj), "start": env.start, "snapshot_ref": REF, "write": True,
              "owns": ["src/*.py"], "tree": str(host), "sd": str(host / ".superlite"), "plugin": plugin}
    fs.save(env.sd, {**fs.default(), "workers": {"W2": {"state": "busy", "role": "implementer", "sent": 2000, "machine": "box", "remote": remote}}})
    d = env.sd / "remote" / "W2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "agent_id": "W2", "t": 2500}) + "\n")


class Pane:  # a fake Herdr: run_in_pane runs the command here, as the host's shell would
    def __init__(self, run=True, fail=None):
        self.run, self.fail, self.calls = run, fail, []

    def install(self, monkeypatch):
        def create_workspace(label, cwd, env_vars):
            self.calls.append(("create", label, cwd))
            if self.fail:
                raise frc.hc.HerdrError(*self.fail)
            return "w9", "w9:p1"

        def run_in_pane(pane, command):
            self.calls.append(("run", pane, command))
            if self.run:
                subprocess.run(["bash", "-c", command], capture_output=True, timeout=60)
            return ""

        def close_workspace(ws):
            self.calls.append(("close", ws))
        monkeypatch.setattr(frc.hc, "create_workspace", create_workspace)
        monkeypatch.setattr(frc.hc, "run_in_pane", run_in_pane)
        monkeypatch.setattr(frc.hc, "close_workspace", close_workspace)
        return self


def clock(monkeypatch):
    t = [100.0]
    monkeypatch.setattr(frc, "now_s", lambda: t[0])
    monkeypatch.setattr(frc, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    return t


def test_constants():
    assert frc.RETAKE_S == 120 and frc.POLL_S == 2


def test_retake_brings_committed_and_uncommitted_work_home(env, monkeypatch):
    clock(monkeypatch)
    host = host_tree(env, {"src/a.py": "two\n"}, {"src/b.py": "new\n"})
    seed(env, host)
    pane = Pane().install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    sha = git(host, "rev-parse", REF)
    assert out["status"] == "DONE"
    assert out["collected"] == {"applied": ["src/a.py", "src/b.py"], "skipped": [], "sha": sha, "retaken": True}
    assert out["concerns"] == [f"remote worker W2's stop hook took no snapshot (remote_apply snapshot failed or ran past 30 s); collect retook it on box: {sha}"]
    assert (env.proj / "src" / "a.py").read_text() == "two\n" and (env.proj / "src" / "b.py").read_text() == "new\n"
    assert collected(env) == sha and git(host, "rev-parse", sha + "^") == git(host, "rev-parse", "HEAD")
    assert [c[0] for c in pane.calls] == ["create", "run", "close"]
    assert pane.calls[0] == ("create", "sl:collect W2", str(host)) and pane.calls[2] == ("close", "w9")


def test_retake_command_runs_sl_in_the_tree(env, monkeypatch):
    clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host)
    pane = Pane().install(monkeypatch)
    frc.collect(env.sd, "W2", report())
    command = pane.calls[1][2]
    assert pane.calls[1][1] == "w9:p1" and command.startswith("sh -c ")
    assert "/skills/subagent-driven-development/scripts/sl remote_apply snapshot --ref " + REF in command
    outs = list((host / ".superlite").glob("collect-W2-*.out"))
    assert len(outs) == 1 and outs[0].read_text().splitlines()[-1] == "exit 0"
    assert not list((host / ".superlite").glob("*.tmp"))


def test_retake_failure_blocked(env, monkeypatch):
    clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host, plugin=str(env.trees / "no-plugin"))
    pane = Pane().install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED" and len(out["concerns"]) == 1
    c = out["concerns"][0]
    assert c.startswith(HEAD.format(host)) and c.endswith("; sl fleet collect W2 retries") and "no-plugin" in c
    assert collected(env) is None and (env.proj / "src" / "a.py").read_text() == "one\n"
    assert pane.calls[-1] == ("close", "w9")


def test_retake_without_result_blocked_after_bound(env, monkeypatch):
    t = clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host)
    pane = Pane(run=False).install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [HEAD.format(host) + "no result within 120 s; sl fleet collect W2 retries"]
    assert t[0] == 100 + frc.RETAKE_S and pane.calls[-1] == ("close", "w9")


def test_retake_read_error_blocked(env, monkeypatch):
    t = clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host)
    pane = Pane(run=False).install(monkeypatch)

    def down(label, path, offset=0, timeout_s=30):
        raise frc.fr.RemoteError("box unreachable: cannot reach box")
    monkeypatch.setattr(frc.fr, "read", down)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [HEAD.format(host) + "box unreachable: cannot reach box; sl fleet collect W2 retries"]
    assert t[0] == 100 and pane.calls[-1] == ("close", "w9")


def test_retake_herdr_error_blocked(env, monkeypatch):
    clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host)
    pane = Pane(fail=("unreachable", "no route to box")).install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [HEAD.format(host) + "herdr unreachable: no route to box; sl fleet collect W2 retries"]
    assert [c[0] for c in pane.calls] == ["create"]


def test_no_retake_without_plugin(env, monkeypatch):
    clock(monkeypatch)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host, plugin=None)
    pane = Pane().install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [HEAD.format(host) + "its record names no host tree or plugin tree; sl fleet collect W2 retries"]
    assert pane.calls == []


def test_hook_snapshot_is_not_retaken(env, monkeypatch):
    clock(monkeypatch)
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    seed_953(env, 2000, [{"t": 2500, "snapshot": sha}])
    pane = Pane().install(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["collected"] == {"applied": ["src/a.py"], "skipped": [], "sha": sha} and out["concerns"] == [] and pane.calls == []


def test_recollect_retakes_again(env, monkeypatch):
    clock(monkeypatch)
    monkeypatch.setattr(frc.fr, "sync", lambda sd, wid: 0)
    host = host_tree(env, {}, {"src/a.py": "two\n"})
    seed(env, host)
    Pane(run=False).install(monkeypatch)
    assert frc.collect(env.sd, "W2", report())["status"] == "BLOCKED"
    Pane().install(monkeypatch)
    out = frc.collect(env.sd, "W2", report(), sync=True)
    assert out["status"] == "DONE" and out["collected"]["retaken"] is True and collected(env) == out["collected"]["sha"]


@pytest.mark.skipif(shutil.which("dash") is None, reason="needs a POSIX sh other than bash")
def test_retake_command_under_dash_with_spaced_paths(env, tmp_path, monkeypatch):
    clock(monkeypatch)
    sha = "0123456789abcdef0123456789abcdef01234567"
    tree = tmp_path / "host tree"
    (tree / ".superlite").mkdir(parents=True)
    sl = tmp_path / "plug in" / "skills" / "subagent-driven-development" / "scripts" / "sl"
    sl.parent.mkdir(parents=True)
    sl.write_text(f'#!/bin/bash\necho "cwd=$PWD args=$*" >&2\necho {sha}\n')
    ref = "refs/superlite/remote/p-1a2b3c/W2/stop"
    remote = {"label": "box", "snapshot_ref": ref, "tree": str(tree), "sd": str(tree / ".superlite"), "plugin": str(tmp_path / "plug in")}
    monkeypatch.setattr(frc.hc, "create_workspace", lambda label, cwd, env_vars: ("w9", "w9:p1"))
    monkeypatch.setattr(frc.hc, "close_workspace", lambda ws: None)
    monkeypatch.setattr(frc.hc, "run_in_pane", lambda pane, command: subprocess.run(["dash", "-c", command], capture_output=True, timeout=60).stdout.decode())
    assert frc._retake(remote, "W2") == (sha, "")
    outs = list((tree / ".superlite").glob("collect-W2-*.out"))
    assert len(outs) == 1 and outs[0].read_text().splitlines()[-1] == "exit 0"
    assert not list((tree / ".superlite").glob("*.tmp"))
    text = outs[0].read_text()
    assert f"cwd={tree.resolve()}" in text or f"cwd={tree}" in text
    assert f"args=remote_apply snapshot --ref {ref}" in text
