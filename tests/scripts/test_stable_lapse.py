from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run
from test_stable_split import NEXT_TASKS

sys.path.insert(0, str(SCRIPTS))
import next_tasks  # noqa: E402

PLAN = """# Plan

**Goal:** g.
**Wave0:** none

```mermaid
flowchart LR
%% taskgraph
T1 --> T3
T2 --> T3
T3 --> T4
```

### T1 a · Complexity 2 · Est. context 20k
**Owns:** src/a.py
**Est. time:** 2 min

### T2 b · Complexity 2 · Est. context 20k
**Owns:** src/b.py
**Est. time:** 2 min

### T3 c · Complexity 2 · Est. context 20k
**Owns:** src/c.py
**Est. time:** 2 min

### T4 d · Complexity 2 · Est. context 20k
**Owns:** src/d.py
**Est. time:** 2 min
"""

STABLE = {"stable": ["T1"], "fix": [
    {"task": "T2", "reasons": ["T2: Owns has a  placeholder"]},
    {"task": "T3", "reasons": ["depends on unstable T2"]},
    {"task": "T4", "reasons": ["depends on unstable T3"]}]}


def cli_plan(tmp_path, stable=STABLE):
    p = tmp_path / "plan.md"
    p.write_text(PLAN, encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    if stable is not None:
        (sl / "stable.json").write_text(json.dumps(stable), encoding="utf-8")
    return p


def stable_plan(tmp_path, stable, wave0=None):
    p = tmp_path / "plan.md"
    p.write_text("# Plan\n", encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    if stable is not None:
        (sl / "stable.json").write_text(json.dumps(stable), encoding="utf-8")
    if wave0:
        (sl / "briefs").mkdir(exist_ok=True)
        (sl / "briefs" / "wave0.json").write_text(json.dumps(wave0), encoding="utf-8")
    return p


def test_task_ids_commas_and_spaces():
    assert next_tasks.task_ids("T1, T2 T3,,T4\tT5 T1") == ["T1", "T2", "T3", "T4", "T5"]
    assert next_tasks.task_ids("") == []
    assert next_tasks.task_ids(None) == []


def test_unknown_ids():
    assert next_tasks.unknown_ids(["T1", "T0", "T99"], {"T1": []}) == ["T99"]


def test_lapse_needs_every_dep():
    fix = [{"task": "T8", "reasons": ["depends on unstable T5, T6"]}]
    assert next_tasks.lapsed_fix(fix, {"T5", "T6"}) == {"T8"}
    assert next_tasks.lapsed_fix(fix, {"T5"}) == set()


def test_own_issue_never_lapses():
    fix = [{"task": "T8", "reasons": ["SIZE: T5 predicted 7 min > 6 max", "depends on unstable T4"]}]
    assert next_tasks.lapsed_fix(fix, {"T4"}) == set()
    assert next_tasks.lapsed_fix([{"task": "T8", "reasons": ["on flagged CHAIN"]}], {"T4"}) == set()


def test_lapse_malformed_entries():
    fix = [{"task": "T9", "reasons": []}, "junk", {"task": "T7", "reasons": ["depends on unstable"]}, {"task": "T6"}]
    assert next_tasks.lapsed_fix(fix, {"T1"}) == set()


def test_stable_filter_releases_chain(tmp_path):
    p = stable_plan(tmp_path, {"stable": ["M1", "T2", "T3"], "fix": [
        {"task": "T8", "reasons": ["depends on unstable T5, T6"]},
        {"task": "T15", "reasons": ["depends on unstable T8"]}]})
    assert next_tasks.stable_filter(p) == {"M1", "T2", "T3"}
    assert next_tasks.stable_filter(p, {"T5", "T6"}) == {"M1", "T2", "T3", "T8"}
    assert next_tasks.stable_filter(p, {"T5", "T6", "T8"}) == {"M1", "T2", "T3", "T8", "T15"}


def test_lapsed_task_still_waits_for_wave0(tmp_path):
    p = stable_plan(tmp_path, {"stable": ["M1"], "fix": [
        {"task": "T8", "reasons": ["depends on unstable T5, T6"]}]}, {"id": "T0", "wait": ["T8"]})
    assert "T8" not in next_tasks.stable_filter(p, {"T5", "T6"})
    assert "T8" in next_tasks.stable_filter(p, {"T0", "T5", "T6"})


def test_stable_blocked_reasons(tmp_path):
    graph = {"T1": [], "T2": [], "T3": ["T1", "T2"], "T4": ["T3"], "T9": []}
    p = stable_plan(tmp_path, STABLE)
    sb = next_tasks.stable_blocked
    r = sb(p, graph, [], [])
    assert r == {"T2": "T2: Owns has a placeholder", "T9": "not in stable.json"}
    assert list(r) == ["T2", "T9"]
    assert sb(p, graph, ["T1", "T2"], []) == {"T9": "not in stable.json"}
    assert "T9" not in sb(p, graph, [], ["T9"])
    assert "T2" not in sb(p, graph, [], [], held={"T2": "x"})
    assert "T9" not in sb(p, graph, [], [], status={"T9": "draft"})
    (tmp_path / "x").mkdir()
    assert sb(stable_plan(tmp_path / "x", None), graph, [], []) == {}


def test_stable_blocked_skips_wave0_wait(tmp_path):
    p = stable_plan(tmp_path, {"stable": ["T1"]}, {"id": "T0", "wait": ["T1"]})
    assert next_tasks.stable_blocked(p, {"T1": []}, [], []) == {}


def test_next_tasks_cli_spaces_and_unstable(tmp_path):
    p = cli_plan(tmp_path)
    cp = run(NEXT_TASKS, "--plan", p, "--committed", "T1 T2", cwd=tmp_path)
    assert cp.out.split() == ["T3"]
    assert "unstable=" not in cp.err
    cp = run(NEXT_TASKS, "--plan", p, "--committed", "T1", cwd=tmp_path)
    assert cp.out.strip() == ""
    assert "unstable=T2 T2: Owns has a placeholder; rerun sl lint --stable" in cp.err
    cp = run(NEXT_TASKS, "--plan", p, "--committed", "T1,T7", cwd=tmp_path)
    assert "warning: --committed: T7 is not a task of the plan" in cp.err
    cp = run(NEXT_TASKS, "--plan", p, "--committed", "T0,T1", cwd=tmp_path)
    assert "warning:" not in cp.err


def test_lapse_trailing_text_keeps_held():
    fix = [{"task": "T8", "reasons": ["depends on unstable T4 and a lint error"]},
           {"task": "T9", "reasons": ["depends on unstable T4,  T5\n"]}]
    assert next_tasks.lapsed_fix(fix, {"T4", "T5"}) == {"T9"}
