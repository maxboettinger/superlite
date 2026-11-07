"""The implementer primes and agent files tell the agent to run the wait: line in the foreground."""
from __future__ import annotations

import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))

import build_prime  # noqa: E402
import routing  # noqa: E402
import plan_tools as pt  # noqa: E402

AGENTS = Path(__file__).resolve().parents[2] / "agents"
FG = "- Run the verify command your task message names; start it with --background, then run its printed `wait:` line in the foreground (never as a background command) and end your turn only after that line reports."
AGENT_RULE = "then run the `wait:` line it prints (`<abs sl> run_tests --wait <path>`) in the foreground, never as a background command, and end your turn only after it reports; read only its summary."
OLD = "then the `wait:` line it prints (`"

PLAN = """# Plan
**Goal:** g

Global constraints:
- c

### T1 one · Complexity 2 · Est. context 26k
**Owns:** a.py, tests/test_a.py
**Components:** 1
**Model:** haiku
**Produces:** a.f() -> int
**Steps:** 1 failing tests
"""


def _plan(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(PLAN, encoding="utf-8")
    return str(p)


def test_preambles_carry_foreground_rule():
    assert build_prime.FG == FG
    for pre in (build_prime.PREAMBLE, build_prime.PREAMBLE_SLIM, build_prime.PREAMBLE_MINI):
        assert FG in pre.split("\n")


def test_built_primes_carry_foreground_rule(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    monkeypatch.setattr(routing, "read_tiers", lambda _p: {"T1": "haiku"})
    outs = [build_prime.build_slim(plan), build_prime.build_mini(plan, "haiku"), build_prime.build(plan, None, [])]
    for out in outs:
        assert FG in out.decode("utf-8").split("\n")


def test_agents_run_wait_in_foreground():
    for name in ("implementer.md", "implementer-haiku.md"):
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert AGENT_RULE in text
        assert OLD not in text
