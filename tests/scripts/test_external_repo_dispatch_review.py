"""Review checks for external repository tasks in next_tasks and dispatch (#332)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import next_tasks  # noqa: E402

EXT = {"repo": {"root": "/r", "test": "t", "ship": "s"}}
MB = lambda ready, info, **kw: dispatch.make_batches(  # noqa: E731
    ready, lambda t: "sonnet", info, {t: 2.0 for t in ready}, lambda tr: 200.0, **kw)


def test_all_external_ready_one_batch_each():
    got = MB(["T1", "T2"], {"T1": EXT, "T2": EXT})
    assert sorted(got) == [["T1"], ["T2"]]


def test_solo_mode_and_critical_path_keep_external_alone():
    info = {"T1": EXT, "T2": {"repo": None}, "T3": {"repo": None}}
    assert MB(["T1", "T2", "T3"], info, solo_mode=True) == [["T1"], ["T2"], ["T3"]]
    got = MB(["T1", "T2", "T3"], info, cp={"T1"})
    assert ["T1"] in got and sorted(t for g in got for t in g) == ["T1", "T2", "T3"]


def test_hint_for_batch_line_and_unknown_task():
    info = {"T1": {"repo": {"root": "/a"}}, "T2": {"repo": None}, "T3": {"repo": {"root": "/b"}}}
    got = dispatch.external_hints([("T2,T3", "fresh tier=sonnet"), ("T0", "wave0")], info)
    assert len(got) == 1 and got[0].startswith("external=T3 root=/b:")


def test_repo_fields_not_confused_and_fence_ignored(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("""# Plan
**Goal:** g.

```mermaid
flowchart LR
  T1[a]
  T2[b]
  %% taskgraph
  T1 --> T2
```

### T1 a · Est. time 2 min
**Owns:** a.py
**Repo test:** `pytest -q`

### T2 b · Est. time 2 min
**Owns:** b.py

```text
**Repo:** /fenced
```
""", encoding="utf-8")
    info = next_tasks.parse_plan(p)
    assert info["T1"]["repo"] is None and info["T1"]["owns"] == ["a.py"]
    assert info["T2"]["repo"] is None and info["T2"]["owns"] == ["b.py"]
