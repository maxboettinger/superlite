"""build_mini builds its stub spec with the plan's root, like the wave0 brief."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))

import build_prime  # noqa: E402
import routing  # noqa: E402
import wave0  # noqa: E402
import plan_tools as pt  # noqa: E402

PLAN = """# Plan
**Goal:** g

Global constraints:
- c

### T1 one · Complexity 2 · Est. context 26k
**Owns:** pkg/a.py, pkg/b.py, tests/test_a.py
**Components:** 1
**Model:** haiku
**Produces:** pkg.a.f() -> int
**Steps:** 1 failing tests

### T2 two · Complexity 2 · Est. context 26k
**Owns:** c.py
**Model:** haiku
**Consumes:** `pkg.a.f()`
"""


def mini(tmp_path, existing, monkeypatch):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    for f in existing:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("", encoding="utf-8")
    monkeypatch.setattr(routing, "read_tiers", lambda _p: {"T1": "haiku", "T2": "haiku"})
    return str(plan), build_prime.build_mini(str(plan), "haiku").decode("utf-8")


def stub(text):
    return text.split("## Stub spec")[1].split("```yaml")[1].split("```")[0]


def test_mini_stub_spec_skips_existing_file(tmp_path, monkeypatch):
    _, text = mini(tmp_path, ["pkg/a.py"], monkeypatch)
    sec = text.split("## Stub spec")[1].split("## Interfaces")[0]
    assert "pkg/b.py" in sec
    assert "pkg/a.py" not in sec


def test_mini_stub_spec_drops_task_whose_files_exist(tmp_path, monkeypatch):
    _, text = mini(tmp_path, ["pkg/a.py", "pkg/b.py"], monkeypatch)
    assert "id: T1" not in text.split("## Stub spec")[1].split("## Interfaces")[0]


def test_mini_and_wave0_brief_same_stub_spec(tmp_path, monkeypatch):
    plan, text = mini(tmp_path, ["pkg/a.py"], monkeypatch)
    pl = pt.Plan.load(plan)
    want = build_prime.normalize(wave0.stub_spec(pl, pt.stable_root(plan)))
    assert stub(text).strip("\n") == want.strip("\n")
