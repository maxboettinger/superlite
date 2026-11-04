"""`sl experiment`: a one-shot run setting (#53) that the next big enough build claims without anyone passing flags.

The global file `$SUPERLITE_HOME/experiment.json` holds the experiment; the first `build_prime` of a plan with at least
`min_tasks` tasks claims it (runs_left - 1, under a lock) and writes the claim next to its prime. That run's prime is
full, its dispatches are one task per agent, and its history rows carry the experiment id. Explicit flags always win."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_batching import equal_plan
from test_metrics_history import HISTORY, setup_run
from test_plan_tools import SCRIPTS, run
from test_routing import DISPATCH, mech_plan, pool

EXPERIMENT = SCRIPTS / "experiment.py"
BUILD_PRIME = SCRIPTS / "build_prime.py"
FULL_ONLY = "**LOC owned:** 100"  # a task body line: in the full prime (whole plan), not in the slim one


def arm(home, min_tasks=8, runs=1, batch="1"):
    cp = run(EXPERIMENT, "set", "--id", "53-old-settings", "--prime", "full", "--batch", batch,
             "--min-tasks", min_tasks, "--runs", runs)
    assert cp.returncode == 0, cp.both
    return json.loads((home / "experiment.json").read_text(encoding="utf-8"))


def prime(d, p, *extra):
    cp = run(BUILD_PRIME, "--plan", p, "--out", d / "prime.md", *extra, cwd=d)
    assert cp.returncode == 0, cp.both
    return cp, (d / "prime.md").read_text(encoding="utf-8")


def left(home):
    return json.loads((home / "experiment.json").read_text(encoding="utf-8"))["runs_left"]


def project(tmp_path, name, n):
    d = tmp_path / name
    d.mkdir()
    return d, equal_plan(d, n)


def test_set_show_clear(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    exp = arm(home)
    assert {k: exp[k] for k in ("id", "prime", "batch", "min_tasks", "runs_left")} == \
        {"id": "53-old-settings", "prime": "full", "batch": 1, "min_tasks": 8, "runs_left": 1}
    assert json.loads(run(EXPERIMENT, "show").out)["id"] == "53-old-settings"
    assert run(EXPERIMENT, "clear").returncode == 0
    assert not (home / "experiment.json").exists()
    shown = run(EXPERIMENT, "show")
    assert shown.returncode == 0 and shown.out.strip() == ""


def test_the_first_big_enough_build_claims_it_and_gets_the_full_prime(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    d, p = project(tmp_path, "big", 8)
    _, slim = prime(d, p)
    assert FULL_ONLY not in slim  # control: no experiment, slim prime
    arm(home)
    cp, full = prime(d, p)
    assert FULL_ONLY in full and "53-old-settings" in cp.err
    claim = json.loads((d / "experiment.json").read_text(encoding="utf-8"))
    assert (claim["id"], claim["prime"], claim["batch"], claim["plan"]) == ("53-old-settings", "full", 1, str(p.resolve()))
    assert left(home) == 0


def test_a_smaller_plan_does_not_claim(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "small", 5)
    cp, text = prime(d, p)
    assert FULL_ONLY not in text and "53-old-settings" not in cp.err
    assert left(home) == 1 and not (d / "experiment.json").exists()


def test_rebuilding_the_prime_of_the_claiming_plan_keeps_its_claim(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "big", 8)
    prime(d, p)
    _, again = prime(d, p)
    assert FULL_ONLY in again and left(home) == 0


def test_once_claimed_another_plan_runs_on_the_defaults(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d1, p1 = project(tmp_path, "first", 8)
    prime(d1, p1)
    d2, p2 = project(tmp_path, "second", 9)
    _, text = prime(d2, p2)
    assert FULL_ONLY not in text and not (d2 / "experiment.json").exists()


def test_an_explicit_prime_or_the_haiku_tier_never_claims(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "big", 8)
    _, text = prime(d, p, "--prime", "slim")
    assert FULL_ONLY not in text
    cp = run(BUILD_PRIME, "--plan", p, "--tier", "haiku", "--out", d / "prime.md", cwd=d)
    assert cp.returncode == 0, cp.both
    assert left(home) == 1 and not (d / "experiment.json").exists()


def test_a_run_that_already_dispatched_does_not_claim(tmp_path, monkeypatch):
    """A mid-run prime rebuild (resume) must not switch a default run to the experiment: its pool has agents."""
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "running", 26)
    pool(d, [{"id": "a1", "tasks": ["T1"], "tier": "sonnet"}])
    cp, text = prime(d, p)
    assert FULL_ONLY not in text and "53-old-settings" not in cp.err
    assert left(home) == 1 and not (d / "experiment.json").exists()
    d2, p2 = project(tmp_path, "fresh", 8)
    pool(d2, [])  # an empty pool is a run that has not dispatched yet
    _, fresh = prime(d2, p2)
    assert FULL_ONLY in fresh and left(home) == 0


def test_the_claiming_run_keeps_its_claim_after_dispatching(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "big", 8)
    prime(d, p)
    pool(d, [{"id": "a1", "tasks": ["T1"], "tier": "sonnet"}])
    _, again = prime(d, p)
    assert FULL_ONLY in again and left(home) == 0


def test_two_builds_at_once_claim_it_only_once(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    dirs = [project(tmp_path, f"p{i}", 8) for i in range(4)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    procs = [subprocess.Popen([sys.executable, str(BUILD_PRIME), "--plan", str(p), "--out", str(d / "prime.md")], cwd=d, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for d, p in dirs]
    assert all(pr.wait(timeout=120) == 0 for pr in procs)
    assert sum((d / "experiment.json").exists() for d, _ in dirs) == 1
    assert left(home) == 0


def lines(cp):
    assert cp.returncode == 0, cp.both
    return [ln.split()[0] for ln in cp.out.splitlines() if ln.startswith("T")]


def test_the_claiming_run_dispatches_one_task_per_agent(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    d0, p0 = project(tmp_path, "control", 8)
    batched = lines(run(DISPATCH, "--plan", p0, "--pool", pool(d0, []), "--ledger", d0 / "l.md", cwd=d0))
    assert any("," in t for t in batched)  # control: the defaults batch these tasks
    arm(home)
    d, p = project(tmp_path, "big", 8)
    prime(d, p)
    solo = lines(run(DISPATCH, "--plan", p, "--pool", pool(d, []), "--ledger", d / "l.md", cwd=d))
    assert solo and not any("," in t for t in solo)


def test_a_claim_for_another_plan_leaves_dispatch_batching(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    arm(home)
    d, p = project(tmp_path, "big", 8)
    prime(d, p)
    other = d / "other.md"  # same tasks, another plan: the claim names plan.md only
    other.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    batched = lines(run(DISPATCH, "--plan", other, "--pool", pool(d, []), "--ledger", d / "l.md", cwd=d))
    assert any("," in t for t in batched)


def test_history_rows_carry_the_experiment_of_the_run(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    p = mech_plan(tmp_path, 2)
    sl = setup_run(tmp_path)
    cp = run(HISTORY, "write", "--plan", p, "--dir", sl, "--run", "r0", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    (sl / "experiment.json").write_text(json.dumps({"id": "53-old-settings", "plan": str(p.resolve()), "prime": "full", "batch": 1}),
                                        encoding="utf-8")
    cp = run(HISTORY, "write", "--plan", p, "--dir", sl, "--run", "r1", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    rows = [json.loads(x) for x in (home / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["run"]: r["experiment"] for r in rows} == {"r0": None, "r1": "53-old-settings"}
