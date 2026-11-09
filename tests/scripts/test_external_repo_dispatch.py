"""next_tasks and dispatch know external repository tasks (#332)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, run
from test_stable_split import DISPATCH

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import next_tasks  # noqa: E402

PLAN = """# Plan
**Goal:** test.
**Wave0:** none

```mermaid
flowchart LR
  T1[a]
  T2[b]
  T3[c]
  T4[d]
  %% taskgraph
  T1 --> T4
```

### T1 shared helper · Est. time 2 min
**Owns:** src/helper.py, tests/test_helper.py
**Repo:** /abs/shared
**Repo test:** `pytest -q`
**Repo ship:** `maxapp ship -C {tree}`

### T2 local a · Est. time 2 min
**Owns:** src/a.py

### T3 local b · Est. time 2 min
**Owns:** src/b.py

### T4 user · Est. time 2 min
**Owns:** src/helper.py
"""
HINT = ("external=T1 root=/abs/shared: the worker edits its tree (plan_tools external T1); after DONE run "
        "plan_tools external T1 --commit, the printed ship: line, then --done, not commit_task")


def write(tmp_path):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    p = tmp_path / "plan.md"
    p.write_text(PLAN, encoding="utf-8")
    return p


def offered(cp):
    return {t for ln in cp.out.splitlines() if ln.strip() for t in ln.split()[0].split(",")}


def disp(tmp_path, p):
    return run(DISPATCH, "--plan", p, "--pool", tmp_path / "pool.json", "--ledger",
               tmp_path / ".superlite" / "progress.md", cwd=tmp_path)


def test_parse_plan_repo_info(tmp_path):
    info = next_tasks.parse_plan(write(tmp_path))
    assert info["T1"]["repo"] == {"root": "/abs/shared", "test": "pytest -q", "ship": "maxapp ship -C {tree}"}
    assert info["T1"]["owns"] == []
    assert info["T4"]["repo"] is None and info["T4"]["owns"] == ["src/helper.py"]


def test_external_task_never_batched():
    times = {"T1": 2.0, "T2": 2.0, "T3": 2.0}
    local = {t: {"repo": None} for t in times}
    ctrl = dispatch.make_batches(["T1", "T2", "T3"], lambda t: "sonnet", local, times, lambda tr: 200.0)
    assert any(len(g) > 1 and "T1" in g for g in ctrl)
    info = {**local, "T1": {"repo": {"root": "/r", "test": "t", "ship": "s"}}}
    got = dispatch.make_batches(["T1", "T2", "T3"], lambda t: "sonnet", info, times, lambda tr: 200.0)
    assert ["T1"] in got
    assert all(g == ["T1"] or "T1" not in g for g in got)
    assert sorted(t for g in got for t in g) == ["T1", "T2", "T3"]


def test_external_hints_unit():
    info = {"T1": {"repo": {"root": "/abs/shared"}}, "T2": {"repo": None}}
    assert dispatch.external_hints([("T1", "fresh tier=sonnet"), ("T2", "agent=W1 tier=sonnet")], info) == [HINT]
    assert dispatch.external_hints([("T2,T3", "fresh tier=sonnet")], {**info, "T3": {"repo": None}}) == []


def test_dispatch_prints_external_hint(tmp_path):
    p = write(tmp_path)
    cp = disp(tmp_path, p)
    assert cp.returncode == 0, cp.err
    assert any(ln.split()[0] == "T1" for ln in cp.out.splitlines() if ln.strip())
    assert "T4" not in offered(cp)
    assert HINT in cp.err
    assert "external=T2" not in cp.err


def test_dependent_waits_for_ledger_line(tmp_path):
    p = write(tmp_path)
    (tmp_path / ".superlite" / "progress.md").write_text(
        "- commit T1 abcdef1234 shared helper (repo /abs/shared)\n", encoding="utf-8")
    cp = disp(tmp_path, p)
    assert "T4" in offered(cp) and "T1" not in offered(cp)
    assert "external=T1" not in cp.err
