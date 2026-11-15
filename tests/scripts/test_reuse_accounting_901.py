"""Worker reuse counts the predictor prefix once, shows its numbers in the evict line, keeps the default estimate (#901)."""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
from test_fleet import world  # noqa: E402,F401  (fixture)

LIM = {"max_context_k": 80, "max_tasks": 20, "max_idle_min": 50}
AG = {"context_k": 75, "baseline_k": 30, "tasks": ["T1"], "idle_min": 0}


def test_reuse_counts_the_prefix_once():
    assert assign.eligibility(AG, 38, LIM, 0.0, 0.0) == "context over 80k"
    assert assign.eligibility(AG, 38, LIM, 0.0, 18.0) is None


def test_reuse_prefix_never_goes_negative():
    ag = {**AG, "context_k": 70}  # added 40k; the next task counts 0, not -8
    assert assign.eligibility(ag, 10, LIM, 0.0, 18.0) is None
    assert assign.eligibility({**ag, "context_k": 111}, 10, LIM, 0.0, 18.0) == "context over 80k"  # 81 + 0


def test_context_note_with_and_without_baseline():
    assert assign.context_note({"context_k": 96, "baseline_k": 55}, 38, 7, 18) == "held 96k, at READY 55k, next 20k"
    assert assign.context_note({"context_k": 96}, 38, 7, 18) == "held 96k, at READY unknown (prime 7k used), next 20k"


PLAN = """# Plan
**Goal:** x.
**Tech stack:** Python 3.12; pytest

Global constraints: none

```mermaid
%% taskgraph
flowchart LR
  T1
```

### T1 one · Complexity 3{est}
**Owns:** src/pkg/t1.py
**Est. time:** 2 min
**Produces:** pkg.t1.f() -> None

"""


def _go(tmp_path, est, ag):
    from test_dispatch_evict import go, pool_file
    p = tmp_path / "plan.md"
    p.write_text(PLAN.format(est=f" · Est. context {est}k" if est else ""), encoding="utf-8")
    base = {"id": "A1", "tier": "sonnet", "tasks": ["x0"], "files": [], "idle_min": 0, "busy": False}
    return go(tmp_path, p, pool_file(tmp_path, [{**base, **ag}]))


def test_evict_line_carries_the_numbers(tmp_path):
    cp = _go(tmp_path, 38, {"context_k": 190.0, "baseline_k": 30.0})
    assert "evict=A1 context over 80k (held 190k, at READY 30k, next 20k)" in cp.err


def test_default_estimate_keeps_its_prefix(tmp_path):
    cp = _go(tmp_path, None, {"context_k": 92.0, "baseline_k": 30.0})  # 62 + 20 > 80
    assert "evict=A1 context over 80k (held 92k, at READY 30k, next 20k)" in cp.err
    ok = tmp_path / "ok"
    ok.mkdir()
    assert "evict=" not in _go(ok, None, {"context_k": 88.0, "baseline_k": 30.0}).err  # 58 + 20 <= 80


def test_pinned_model_worker_registers_under_its_tier(world):
    import run_config
    from test_fleet import REAL, fleet
    if REAL:
        pytest.skip("reads the in-process fake")
    cfg = run_config.active(world.sd, world.proj)
    cfg["workers"] = {**cfg["workers"], "implementer": "sonnet-pinned"}
    (world.sd / "run-config.json").write_text(json.dumps(cfg), encoding="utf-8")
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    agent = json.loads((world.sd / "pool.json").read_text())["agents"][0]
    assert agent["tier"] == "sonnet"
