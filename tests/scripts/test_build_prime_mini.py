"""Mini (haiku) prime: whole plan lines, the Global constraints bullets, balanced backticks."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import wave0  # noqa: E402
import plan_tools as pt  # noqa: E402

REAL = ROOT / "docs" / "plans" / "2026-10-27-field-report-fixes.md"

PLAN = """# Plan
**Goal:** g
**Tech stack:** Python 3

Global constraints:
- first bullet `a`
- second bullet
  continued

```mermaid
flowchart LR
  T1 --> T2
  %% taskgraph
  T1 --> T2
```

## Section A

### T1 finish: group open incidents · Complexity 2 · Est. context 26k
**Owns:** a.py, tests/test_a.py
**Components:** 1
**Model:** haiku
**Consumes:** existing `finish.open_incidents(path)`
**Produces:** finish.group_incidents(incidents: list[dict], limit: int = 15) -> list[str]
e.g. `group_incidents([])` -> `[]`
**Steps:** 1 failing tests

### T2 other · Complexity 2 · Est. context 26k
**Owns:** b.py
**Model:** sonnet
**Consumes:** `finish.group_incidents(incidents)`
"""


def mini(tmp_path, text=PLAN, monkeypatch=None):
    import build_prime
    import routing
    plan = tmp_path / "plan.md"
    plan.write_text(text, encoding="utf-8")
    ids = [t.id for t in pt.Plan.load(str(plan)).tasks]
    routing_read = lambda _p: {i: "haiku" for i in ids}  # noqa: E731
    old = routing.read_tiers
    routing.read_tiers = routing_read
    try:
        return build_prime.build_mini(str(plan), "haiku").decode("utf-8")
    finally:
        routing.read_tiers = old


def test_constraints_bullets_after_label_kept(tmp_path):
    lines = wave0.constraint_lines(pt.Plan.load(str(_write(tmp_path))))
    assert "- first bullet `a`" in lines and "- second bullet" in lines
    assert "Global constraints:" in lines


def _write(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(PLAN, encoding="utf-8")
    return p


def test_backticks_balanced_in_interfaces(tmp_path):
    text = mini(tmp_path)
    assert "Consumes: existing `finish.open_incidents(path)`" in text
    for ln in text.split("## Interfaces your tasks touch")[1].split("\n"):
        assert ln.count("`") % 2 == 0, ln
    for ln in text.split("```yaml")[1].split("```")[0].split("\n"):
        assert ln.replace("\\`", "").count("`") % 2 == 0, ln


def test_constraints_section_holds_bullets(tmp_path):
    sec = mini(tmp_path).split("## Constraints")[1].split("## Stub spec")[0]
    assert "- first bullet `a`" in sec


@pytest.mark.skipif(not REAL.exists(), reason="this run's plan is absent")
def test_no_line_cut_mid_word(tmp_path):
    plan_lines = set(l.strip() for l in REAL.read_text(encoding="utf-8").split("\n"))
    text = mini(tmp_path, REAL.read_text(encoding="utf-8"))
    iface = text.split("## Interfaces your tasks touch")[1]
    for ln in iface.strip().split("\n"):
        if ln.startswith("###") or not ln.strip():
            continue
        label, _, body = ln.partition(": ")
        assert label in ("Owns", "Produces", "Consumes"), ln
        assert any(body in pl for pl in plan_lines), ln
        assert ln.count("`") % 2 == 0, ln
    assert "one docs ta\n" not in text
    sec = text.split("## Constraints")[1].split("## Stub spec")[0]
    assert sec.count("\n- ") >= 5


def test_mini_prime_still_small(tmp_path):
    tasks = "".join(PLAN.split("## Section A")[1].replace("T1", f"T{i}") for i in range(1, 9))
    text = mini(tmp_path, PLAN.split("## Section A")[0] + "## Section A" + tasks)
    assert len(text.encode()) < 8192
