"""The prime is not counted in an agent's context against the 80k ceiling."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run
from test_stable_split import DISPATCH
from test_wave0 import PY, plan

sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
import dispatch  # noqa: E402

ASSIGN = SCRIPTS / "assign.py"


def _setup(tmp_path, context_k, prime_bytes=44000):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    p.write_text(p.read_text(encoding="utf-8").replace("Est. context 30k", "Est. context 6k"), encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / "prime.md").write_bytes(b"x" * prime_bytes)
    pool = sl / "pool.json"
    pool.write_text(json.dumps({"agents": [{"id": "a1", "tasks": ["T0"], "files": ["src/pkg/slug.py"], "context_k": context_k,
                                            "idle_min": 1}]}), encoding="utf-8")
    return p, pool


def _line(cp, t="T1"):
    return next(ln for ln in cp.out.splitlines() if ln.startswith(t + " "))


def test_prime_k_from_size(tmp_path):
    (tmp_path / "prime.md").write_bytes(b"x" * 44000)
    (tmp_path / "prime-haiku.md").write_bytes(b"x" * 8000)
    assert dispatch.prime_k(tmp_path, "sonnet") == 11.0
    assert dispatch.prime_k(tmp_path, "haiku") == 2.0
    assert dispatch.prime_k(tmp_path / "nope", "sonnet") == 0.0


def test_eligibility_examples():
    assert assign.eligibility({"context_k": 85}, 6, None, 11.0) is None
    assert assign.eligibility({"context_k": 85}, 6) == "context over 80k"


def test_agent_reused_after_one_task(tmp_path):
    p, pool = _setup(tmp_path, 85)
    cp = run(DISPATCH, "--plan", p, "--pool", pool, "--ledger", tmp_path / "l.md", cwd=tmp_path)
    assert "agent=a1" in _line(cp), cp.both
    assert "evict=" not in cp.err


def test_still_evicts_over_budget(tmp_path):
    p, pool = _setup(tmp_path, 120)
    cp = run(DISPATCH, "--plan", p, "--pool", pool, "--ledger", tmp_path / "l.md", cwd=tmp_path)
    assert "agent=a1" not in _line(cp) and "evict=a1" in cp.err, cp.both


def test_assign_cli_uses_prime(tmp_path):
    p, pool = _setup(tmp_path, 85)
    cp = run(ASSIGN, "--task", "T1", "--plan", p, "--pool", pool, cwd=tmp_path)
    assert "evict=" not in cp.err, cp.both
    (tmp_path / ".superlite" / "prime.md").unlink()
    cp = run(ASSIGN, "--task", "T1", "--plan", p, "--pool", pool, cwd=tmp_path)
    assert "evict=a1 context over 80k" in cp.err
