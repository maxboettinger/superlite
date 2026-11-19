# tests/scripts/test_fleet_remote_collect_984.py: collect can sync first and its recoverable concerns name `sl fleet collect Wn` (#984)
from test_fleet_remote_collect import env, host_snapshot, report, collected, frc, NAME, REF  # noqa: F401
from test_fleet_remote_collect_953 import seed, append_stop, clock, syncing, HOST_TREE


def test_sync_first_reads_late_record(env, monkeypatch):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    readings = iter([100.0, 100.0 + frc.WAIT_S + 1])
    calls = []

    def sync(sd, wid):
        calls.append(wid)
        if len(calls) == 1:
            append_stop(env, t=2600, snapshot=sha)
        return 0
    monkeypatch.setattr(frc.fr, "sync", sync)
    monkeypatch.setattr(frc, "now_s", lambda: next(readings, 1000.0))
    monkeypatch.setattr(frc, "sleep", lambda s: None)
    seed(env, 2000, [])
    out = frc.collect(env.sd, "W2", report(), sync=True)
    assert out["status"] == "DONE" and out["collected"]["sha"] == sha
    assert calls == ["W2"] and collected(env) == sha


def test_sync_false_stays_blocked_in_same_setup(env, monkeypatch):
    sha = host_snapshot(env, {"src/a.py": "two\n"})
    readings = iter([100.0, 100.0 + frc.WAIT_S + 1])
    calls = []

    def sync(sd, wid):
        calls.append(wid)
        if len(calls) == 1:
            append_stop(env, t=2600, snapshot=sha)
        return 0
    monkeypatch.setattr(frc.fr, "sync", sync)
    monkeypatch.setattr(frc, "now_s", lambda: next(readings, 1000.0))
    monkeypatch.setattr(frc, "sleep", lambda s: None)
    seed(env, 2000, [])
    out = frc.collect(env.sd, "W2", report())
    assert out["status"] == "BLOCKED" and "no stop record of its task" in out["concerns"][0]
    assert calls == [] and collected(env) is None


def test_no_record_concern_names_fleet_collect(env, monkeypatch):
    clock(monkeypatch)
    seed(env, 2000, [{"t": 1000, "snapshot": "a" * 40}])
    syncing(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [f"remote worker W2 left no snapshot: no stop record of its task reached this machine within 45 s; its tree {HOST_TREE} stays on box (snapshot ref {REF}); sl fleet collect W2 brings it home once its stop record lands"]


def test_fetch_and_conflict_concerns_name_fleet_collect(env, monkeypatch):
    clock(monkeypatch)
    seed(env, 2000, [{"t": 2500, "snapshot": "b" * 40}])

    def down(*a, **k):
        raise frc.fr.RemoteError("down")
    monkeypatch.setattr(frc.fr, "fetch", down)
    assert frc.collect(env.sd, "W2", report())["concerns"] == ["cannot fetch W2's work: down; sl fleet collect W2 retries"]
    monkeypatch.setattr(frc.fr, "fetch", lambda *a, **k: "b" * 40)
    monkeypatch.setattr(frc.remote_apply, "apply", lambda *a, **k: {"conflicts": ["a.py"], "applied": [], "skipped": []})
    kept = f"refs/maxapp/box/{NAME}/superlite/remote/p-1a2b3c/W2/stop"
    assert frc.collect(env.sd, "W2", report())["concerns"] == [f"remote changes conflict with local edits: a.py (kept at {kept}); sl fleet collect W2 retries once those local edits are resolved"]


def test_hook_took_none_unchanged(env, monkeypatch):
    clock(monkeypatch)
    seed(env, 2000, [{"t": 2500}])
    syncing(monkeypatch)
    out = frc.collect(env.sd, "W2", report())
    assert out["concerns"] == [f"remote worker W2 left no snapshot: its stop hook took none (remote_apply snapshot failed or ran past 30 s); its tree {HOST_TREE} stays on box"]
