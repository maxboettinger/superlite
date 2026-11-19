# tests/scripts/test_fleet_remote_collect_953.py: collect waits for the task turn's own stop record, syncing the mirror (#953)
import json
from test_fleet_remote_collect import env, host_snapshot, report, collected, frc, fs, NAME, REF  # noqa: F401

HOST_TREE = "/rh/.maxapp/trees/proj/p-1a2b3c/W2"


def seed(env, sent, stops):
    remote = {"label": "box", "name": NAME, "project": str(env.proj), "start": env.start, "snapshot_ref": REF, "write": True,
              "owns": ["src/*.py"], "tree": HOST_TREE, "sd": HOST_TREE + "/.superlite"}
    fs.save(env.sd, {**fs.default(), "workers": {"W2": {"state": "busy", "role": "implementer", "sent": sent, "machine": "box", "remote": remote}}})
    d = env.sd / "remote" / "W2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "metrics.jsonl").write_text("".join(json.dumps({"ev": "stop", "agent_id": "W2", **s}) + "\n" for s in stops))


def append_stop(env, **s):
    with open(env.sd / "remote" / "W2" / "metrics.jsonl", "a") as fh:
        fh.write(json.dumps({"ev": "stop", "agent_id": "W2", **s}) + "\n")


def clock(monkeypatch):
    t = [100.0]
    monkeypatch.setattr(frc, "now_s", lambda: t[0])
    monkeypatch.setattr(frc, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    return t


def syncing(monkeypatch, on_call=None):
    calls = []

    def sync(sd, wid):
        calls.append(wid)
        if on_call:
            on_call(len(calls))
        return 0
    monkeypatch.setattr(frc.fr, "sync", sync)
    return calls


def test_constants():
    assert frc.WAIT_S == 45 and frc.POLL_S == 2


def test_ready_snapshot_before_sent_is_not_the_task(env, monkeypatch):
    clock(monkeypatch)
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    seed(env, 2000, [{"t": 1000, "snapshot": "a" * 40}])
    calls = syncing(monkeypatch, lambda n: append_stop(env, t=2500, snapshot=sha) if n == 1 else None)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "DONE" and out["collected"]["sha"] == sha
    assert (env.proj / "src" / "a.py").read_text() == "two\n"
    assert calls == ["W2"] and collected(env) == sha


def test_late_stop_record_is_waited_for(env, monkeypatch):
    t = clock(monkeypatch)
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    seed(env, 2000, [])
    calls = syncing(monkeypatch, lambda n: append_stop(env, t=2600, snapshot=sha) if n == 3 else None)
    out = frc.collect(env.sd, "W2", report())
    assert out["collected"]["applied"] == ["src/a.py"] and len(calls) == 3
    assert t[0] - 100 == 4


def test_no_stop_record_within_wait_blocked(env, monkeypatch):
    t = clock(monkeypatch)
    seed(env, 2000, [{"t": 1000, "snapshot": "a" * 40}])
    calls = syncing(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"] == [f"remote worker W2 left no snapshot: no stop record of its task reached this machine within 45 s; its tree {HOST_TREE} stays on box (snapshot ref {REF})"]
    assert 45 <= t[0] - 100 <= 47 and len(calls) >= 20
    assert collected(env) is None


def test_stop_record_without_snapshot_blocked_at_once(env, monkeypatch):
    t = clock(monkeypatch)
    seed(env, 2000, [{"t": 2500}])
    calls = syncing(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED"
    assert out["concerns"] == [f"remote worker W2 left no snapshot: its stop hook took none (remote_apply snapshot failed or ran past 30 s); its tree {HOST_TREE} stays on box"]
    assert calls == [] and t[0] == 100


def test_sync_error_counts_as_nothing_new(env, monkeypatch):
    clock(monkeypatch)
    seed(env, 2000, [])

    def boom(sd, wid):
        raise frc.fr.RemoteError("box unreachable")
    monkeypatch.setattr(frc.fr, "sync", boom)
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED" and "no stop record of its task" in out["concerns"][0]
