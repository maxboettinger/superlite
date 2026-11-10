"""pool prune (#384): drop pool entries of agents that no longer exist and say what was removed; `pool add`
records the session that registered an in-process agent."""
import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pool  # noqa: E402


def agent(aid, **kw):
    return {"id": aid, "tier": "sonnet", "tasks": [], "files": [], "context_k": 20, "idle_min": 0, "busy": False, **kw}


def write_pool(tmp_path, agents):
    sd = tmp_path / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "pool.json").write_text(json.dumps({"plan": "p.md", "agents": agents}), encoding="utf-8")
    return sd


def ids(path):
    return [a["id"] for a in json.loads(Path(path).read_text(encoding="utf-8"))["agents"]]


def cli(tmp_path, *args, sid="new"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "CLAUDE_CODE_SESSION_ID"}
    env.update(SUPERLITE_SESSION_ID=sid, SUPERLITE_HOME=str(tmp_path / "home"))
    return subprocess.run([sys.executable, str(SCRIPTS / "pool.py"), *args, "--pool", str(tmp_path / ".superlite" / "pool.json")],
                          capture_output=True, text=True, cwd=tmp_path, env=env)


def test_in_process_agent_of_another_session_is_removed():
    data = {"agents": [agent("a1", session="old", busy=True, current="T3,T4"), agent("a2", session="new")]}
    removed, kept = pool.prune(data, {}, "new", None)
    assert removed == [("a1", "in-process agent of session old, not this session; was busy with T3,T4")]
    assert kept == []
    assert [a["id"] for a in data["agents"]] == ["a2"]


def test_idle_agent_reason_has_no_busy_part():
    data = {"agents": [agent("a1", session="old", current="T3")]}
    removed, _ = pool.prune(data, {}, "new", None)
    assert removed == [("a1", "in-process agent of session old, not this session")]


def test_agent_without_session_is_kept_with_a_hint():
    data = {"agents": [agent("a1", busy=True, current=["T5"])]}
    removed, kept = pool.prune(data, {}, "new", None)
    assert removed == []
    assert kept == [("a1", "no session recorded; sl pool remove a1 if it is gone")]
    assert [a["id"] for a in data["agents"]] == ["a1"]


def test_no_session_id_keeps_in_process_agents():
    data = {"agents": [agent("a1", session="old")]}
    removed, kept = pool.prune(data, {}, None, None)
    assert removed == []
    assert kept == [("a1", "no session id to check it against")]


def test_fleet_workers_are_checked_against_herdr():
    workers = {"W1": {"name": "sl-x-w1", "state": "busy"}, "W2": {"name": "sl-x-w2", "state": "ready"},
               "W3": {"name": "sl-x-w3", "state": "stopped"}}
    data = {"agents": [agent("W1", busy=True, current="T2"), agent("W2"), agent("W3")]}
    removed, kept = pool.prune(data, workers, "new", {"sl-x-w2", "other"})
    assert removed == [("W1", "fleet worker gone from Herdr; was busy with T2"), ("W3", "fleet worker stopped")]
    assert kept == []
    assert [a["id"] for a in data["agents"]] == ["W2"]


def test_herdr_unreachable_keeps_live_fleet_workers():
    workers = {"W1": {"name": "sl-x-w1", "state": "ready"}, "W3": {"name": "sl-x-w3", "state": "stopped"}}
    data = {"agents": [agent("W1"), agent("W3")]}
    removed, kept = pool.prune(data, workers, "new", None)
    assert removed == [("W3", "fleet worker stopped")]
    assert kept == [("W1", "Herdr unreachable")]


def test_prune_file_saves_and_prints(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("a1", session="old", busy=True, current="T3"), agent("a2", session="new")])
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    lines = pool.prune_file(str(sd / "pool.json"))
    assert lines == ["removed a1 (in-process agent of session old, not this session; was busy with T3)",
                     "pool: removed 1 of 2 agents"]
    assert ids(sd / "pool.json") == ["a2"]
    assert json.loads((sd / "pool.json").read_text(encoding="utf-8"))["plan"] == "p.md"


def test_prune_file_reads_worker_names_from_fleet_json(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("W1"), agent("W2"), agent("a3")])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {
        "W1": {"name": "sl-a-w1", "state": "ready"}, "W2": {"name": "sl-a-w2", "state": "busy", "task": "T2"}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    monkeypatch.setattr(pool, "herdr_names", lambda: {"sl-a-w2"})
    lines = pool.prune_file(str(sd / "pool.json"))
    assert lines == ["removed W1 (fleet worker gone from Herdr)",
                     "kept a3 (no session recorded; sl pool remove a3 if it is gone)",
                     "pool: removed 1 of 3 agents"]
    assert ids(sd / "pool.json") == ["W2", "a3"]


def test_prune_file_asks_herdr_only_for_live_fleet_workers(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("a2", session="new")])
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    calls = []
    monkeypatch.setattr(pool, "herdr_names", lambda: calls.append(1) or set())
    before = (sd / "pool.json").read_text(encoding="utf-8")
    assert pool.prune_file(str(sd / "pool.json")) == ["pool: nothing to prune (1 agent)"]
    assert (sd / "pool.json").read_text(encoding="utf-8") == before
    assert calls == []


def test_prune_file_without_a_pool(tmp_path):
    sd = tmp_path / ".superlite"
    assert pool.prune_file(str(sd / "pool.json")) == [f"pool: no pool.json in {sd}"]
    assert not (sd / "pool.json").exists()


def test_cli_add_records_the_session_and_prune_follows_it(tmp_path):
    r = cli(tmp_path, "add", "a9", "--tier", "sonnet", "--current", "T1")
    assert r.returncode == 0, r.stderr
    saved = json.loads((tmp_path / ".superlite" / "pool.json").read_text(encoding="utf-8"))
    assert saved["agents"][0]["session"] == "new"
    r = cli(tmp_path, "prune")
    assert (r.returncode, r.stdout.splitlines()) == (0, ["pool: nothing to prune (1 agent)"]), r.stderr
    r = cli(tmp_path, "prune", sid="later")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["removed a9 (in-process agent of session new, not this session; was busy with T1)",
                                     "pool: removed 1 of 1 agent"]
    assert ids(tmp_path / ".superlite" / "pool.json") == []


def test_worker_without_state_is_checked_against_herdr(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("W1")])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {"W1": {"name": "sl-a-w1"}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    monkeypatch.setattr(pool, "herdr_names", lambda: {"sl-a-w1"})
    assert pool.prune_file(str(sd / "pool.json")) == ["pool: nothing to prune (1 agent)"]


def test_prune_file_rereads_fleet_json_under_the_lock(tmp_path, monkeypatch):
    import fleet_state
    sd = write_pool(tmp_path, [agent("W1")])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {"W1": {"name": "sl-a-w1", "state": "ready"}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    monkeypatch.setattr(pool, "herdr_names", lambda: {"sl-a-w1"})
    held, loads = [], []
    real_locked, real_load = fleet_state.locked, fleet_state.load

    @contextlib.contextmanager
    def locked(d):
        with real_locked(d):
            held.append(True)
            try:
                yield
            finally:
                held.clear()

    def load(d):
        loads.append(bool(held))
        return real_load(d)
    monkeypatch.setattr(fleet_state, "locked", locked)
    monkeypatch.setattr(fleet_state, "load", load)
    pool.prune_file(str(sd / "pool.json"))
    assert loads[-1] is True


def test_prune_file_leaves_the_pool_of_another_live_session(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("a1", session="old")])
    home = tmp_path / "home"
    (sd / "session").write_text("other\n", encoding="utf-8")
    (home / "sessions").mkdir(parents=True)
    (home / "sessions" / "other").write_text(f"{sd}\n", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    lines = pool.prune_file(str(sd / "pool.json"))
    assert lines == [f"pool: not pruned: {sd} belongs to session other; take the run over first: sl orchestrator takeover --plan {sd}"]
    assert ids(sd / "pool.json") == ["a1"]


def test_prune_file_survives_non_dict_fleet_worker_records(tmp_path, monkeypatch):
    sd = write_pool(tmp_path, [agent("W1")])
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {"W1": 5}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "new")
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    lines = pool.prune_file(str(sd / "pool.json"))
    assert lines[-1].startswith("pool:")
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": [1]}), encoding="utf-8")
    assert pool.prune_file(str(sd / "pool.json"))[-1].startswith("pool:")
