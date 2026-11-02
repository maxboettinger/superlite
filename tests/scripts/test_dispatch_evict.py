"""dispatch: an agent evicted from the pool is removed from pool.json, so no later round offers it (issue #46).

Real sibling scripts, no fake: dispatch only reads pool.json, the plan and the ledger."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run
from test_routing import mixed
from test_spawn_free import ENV, git, write
from test_stable_split import DISPATCH
from test_wave0 import PY, plan

sys.path.insert(0, str(SCRIPTS))
import dispatch as dispatchmod  # noqa: E402
import pool as poolmod  # noqa: E402

POOL = SCRIPTS / "pool.py"
COMMIT = SCRIPTS / "commit_task.py"

WORN = [f"x{i}" for i in range(25)]  # over max_tasks 20 for both tiers: evicted
S_OLD = {"id": "s_old", "tier": "sonnet", "tasks": WORN, "files": [], "context_k": 20.0, "idle_min": 0, "busy": False}
H_OLD = {"id": "h_old", "tier": "haiku", "tasks": WORN, "files": [], "context_k": 20.0, "idle_min": 0, "busy": False}
S1 = {"id": "s1", "tier": "sonnet", "tasks": ["x0"], "files": ["src/pkg/t1.py"], "context_k": 20.0, "idle_min": 0, "busy": False}
S2 = {"id": "s2", "tier": "sonnet", "tasks": ["x0"], "files": ["src/pkg/t4.py"], "context_k": 20.0, "idle_min": 0, "busy": False}
H_OK = {"id": "h_ok", "tier": "haiku", "tasks": ["x0"], "files": [], "context_k": 20.0, "idle_min": 0, "busy": False}
S_BUSY = {"id": "s_busy", "tier": "sonnet", "tasks": WORN, "files": [], "context_k": 20.0, "idle_min": 0, "busy": True,
          "current": "T2"}  # busy is never idle: never evicted, whatever it has done
AGENTS = [S_OLD, S1, H_OLD, S2, H_OK, S_BUSY]
EVICTED = ["s_old", "h_old"]


def pool_file(tmp_path, agents):
    f = tmp_path / ".superlite" / "pool.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps({"agents": copy.deepcopy(agents)}), encoding="utf-8")
    return f


def read(f):
    return json.loads(f.read_text(encoding="utf-8"))


def go(tmp_path, p, f, *extra):
    cp = run(DISPATCH, "--plan", p, "--pool", f, "--ledger", tmp_path / "l.md", *extra, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return cp


def offered(out):
    """Every agent id on a stdout line: `agent=ID` tokens and the ids of `poll ID,ID`."""
    ids = set()
    for ln in out.splitlines():
        words = ln.split()
        ids.update(w[len("agent="):] for w in words if w.startswith("agent="))
        if "poll" in words:
            ids.update(words[words.index("poll") + 1].split(","))
    return ids


# ------------------------------------------------------------- pool.remove

def test_pool_remove_unknown_id():
    data = {"agents": [{"id": "a"}, {"id": "b"}]}
    before = copy.deepcopy(data)
    assert poolmod.remove(data, "zz") is False
    assert data == before
    empty = {}
    assert poolmod.remove(empty, "zz") is False and empty == {}  # no `agents` key invented


def test_pool_remove_known_id():
    data = {"agents": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "plan": "p.md"}
    assert poolmod.remove(data, "b") is True
    assert data == {"agents": [{"id": "a"}, {"id": "c"}], "plan": "p.md"}
    assert poolmod.remove(data, "b") is False  # gone: the second call changes nothing


def test_pool_cli_remove(tmp_path):
    f = tmp_path / ".superlite" / "pool.json"
    for aid in ("a1", "a2"):
        assert run(POOL, "add", aid, "--tier", "sonnet", "--pool", f, cwd=tmp_path).returncode == 0
    cp = run(POOL, "remove", "a1", "--pool", f, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert cp.out.strip() == "removed a1" and len(cp.out.splitlines()) == 1 and cp.err == ""
    assert [ag["id"] for ag in read(f)["agents"]] == ["a2"]
    assert not list(f.parent.glob("*.tmp"))
    kept = f.read_bytes()
    cp = run(POOL, "remove", "zz", "--pool", f, cwd=tmp_path)  # unknown: exit 2, one stderr line, file untouched
    assert cp.returncode == 2 and cp.out == "" and cp.err.strip() == "unknown agent: zz"
    assert f.read_bytes() == kept


def test_pool_save_temp_name_is_per_process(tmp_path, monkeypatch):
    """dispatch and `sl pool` may save at once: a shared `pool.json.tmp` would let one rename the other's half-written file."""
    seen = []
    real = Path.replace

    def spy(self, target):
        seen.append(self.name)
        return real(self, target)

    monkeypatch.setattr(Path, "replace", spy)
    monkeypatch.setattr(os, "getpid", lambda: 4242)
    poolmod.save(tmp_path / "pool.json", {"agents": []})
    assert seen == ["pool.json.4242.tmp"]
    assert not list(tmp_path.glob("*.tmp"))


# ------------------------------------------------------------- dispatch

def test_drop_evicted_keeps_an_agent_busy_since_the_plan(tmp_path):
    """The pool is read fresh at drop time: an agent a `pool busy` call took meanwhile is not removed."""
    f = pool_file(tmp_path, [S_OLD, S1, dict(H_OLD, busy=True, current="T9"), dict(H_OK, current="T8")])
    dispatchmod.drop_evicted(f, {"s_old": "20 tasks done", "h_old": "20 tasks done", "h_ok": "x", "zz": "unknown"})
    assert [ag["id"] for ag in read(f)["agents"]] == ["s1", "h_old", "h_ok"]  # only the idle, evicted one went


def test_drop_evicted_without_a_pool_file_is_a_noop(tmp_path):
    f = tmp_path / ".superlite" / "pool.json"
    dispatchmod.drop_evicted(f, {"a1": "x"})
    assert not f.exists()

def test_evicted_not_on_any_line(tmp_path):
    """Mixed tiers (sonnet T1/T4, haiku lane T3): across agent=, poll and lane lines no evicted id appears."""
    p = mixed(tmp_path)
    for extra in ((), ("--batch", "1")):
        f = pool_file(tmp_path, AGENTS)
        cp = go(tmp_path, p, f, *extra)
        ids = offered(cp.out)
        assert not ids & set(EVICTED), cp.both
        assert "h_ok" in ids and ids & {"s1", "s2"}, cp.both  # the eligible agents are still offered
        assert "evict=s_old 20 tasks done" in cp.err and "evict=h_old 20 tasks done" in cp.err, cp.both
        assert "evict=s_busy" not in cp.err and "s_busy" not in ids


def test_evicted_removed_from_pool_file(tmp_path):
    p = mixed(tmp_path)
    f = pool_file(tmp_path, AGENTS)
    go(tmp_path, p, f)
    after = read(f)["agents"]
    assert [ag["id"] for ag in after] == ["s1", "s2", "h_ok", "s_busy"]
    assert after == [S1, S2, H_OK, S_BUSY]  # the rest is untouched, the busy agent included
    assert not list(f.parent.glob("*.tmp"))


def test_second_run_does_not_reevict(tmp_path):
    p = mixed(tmp_path)
    f = pool_file(tmp_path, AGENTS)
    first = go(tmp_path, p, f)
    assert "evict=s_old" in first.err
    kept = f.read_bytes()
    second = go(tmp_path, p, f)
    assert "evict=" not in second.err, second.both
    assert second.out == first.out and f.read_bytes() == kept  # same lines, pool file not rewritten


def test_nothing_evicted_leaves_pool_file_alone(tmp_path):
    p = mixed(tmp_path)
    f = pool_file(tmp_path, [S1, S2, H_OK])
    before = f.read_bytes()
    cp = go(tmp_path, p, f)
    assert "evict=" not in cp.err and f.read_bytes() == before


def test_evicted_in_an_earlier_round_is_not_offered_later(tmp_path):
    """The real leak: round 1 evicts a1 (T1's 60k does not fit), round 2 (only small T2 ready) would fit it again."""
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    p.write_text(p.read_text(encoding="utf-8").replace("### T1 slug · Complexity 3 · Est. context 30k",
                                                      "### T1 slug · Complexity 3 · Est. context 60k")
                 .replace("### T2 feed · Complexity 3 · Est. context 30k", "### T2 feed · Complexity 3 · Est. context 6k"),
                 encoding="utf-8")
    a1 = {"id": "a1", "tier": "sonnet", "tasks": [], "files": [], "context_k": 50.0, "idle_min": 0, "busy": False}
    f = pool_file(tmp_path, [a1])
    one = go(tmp_path, p, f)
    assert "evict=a1 context over 80k" in one.err and "a1" not in offered(one.out), one.both
    led = tmp_path / "l.md"
    led.write_text("- commit T1 abcdef1234 slug\n", encoding="utf-8")
    two = go(tmp_path, p, f)
    assert "a1" not in offered(two.out) and two.out.startswith("T2 fresh"), two.both


def test_commit_task_dispatch_never_offers_evicted(tmp_path):
    """`commit_task T1 --dispatch`: the same round-1 eviction, then the post-commit dispatch round, same assertion."""
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    text = (p.read_text(encoding="utf-8").replace("### T1 slug · Complexity 3 · Est. context 30k",
                                                  "### T1 slug · Complexity 3 · Est. context 60k")
            .replace("### T2 feed · Complexity 3 · Est. context 30k", "### T2 feed · Complexity 3 · Est. context 6k"))
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo, "plan.md", text)
    write(repo, "README.md", "base\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    a1 = {"id": "a1", "tier": "sonnet", "tasks": [], "files": [], "context_k": 50.0, "idle_min": 0, "busy": False}
    f = pool_file(repo, [a1])
    one = go(repo, repo / "plan.md", f)  # round 1: a1 cannot take the 60k T1
    assert "evict=a1" in one.err
    write(repo, "src/pkg/slug.py", "def slugify(text):\n    return text\n")
    cp = subprocess.run([sys.executable, str(COMMIT), "T1", "--plan", "plan.md", "--dispatch"], capture_output=True,
                        text=True, cwd=repo, env=ENV, encoding="utf-8")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    after_next = cp.stdout.split("next:", 1)[1]
    assert after_next.strip().startswith("T2"), cp.stdout
    assert "a1" not in offered(after_next), cp.stdout
    assert [ag["id"] for ag in read(f)["agents"]] == []
