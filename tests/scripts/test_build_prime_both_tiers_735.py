"""build_prime writes the haiku prime next to the main one when the plan has a haiku task (#735)."""
from __future__ import annotations

import hashlib
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402
import routing  # noqa: E402

PLAN = """# Plan
**Goal:** g
**Spec:** s

Global constraints:
- c

### T1 one · Complexity 2 · Est. context 26k
**Owns:** a.py
**Components:** 1
**Model:** haiku
**Produces:** a.f() -> int

### T2 two · Complexity 2 · Est. context 26k
**Owns:** b.py
**Model:** sonnet
**Consumes:** `a.f()`
"""


def setup(tmp_path, monkeypatch, tiers=None):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    t = {"T1": "haiku", "T2": "sonnet"} if tiers is None else tiers
    monkeypatch.setattr(routing, "read_tiers", lambda _p: t)
    return plan


def run(plan, out, capsys, *extra):
    code = build_prime.main(["--plan", str(plan), "--out", str(out), *extra])
    return code, capsys.readouterr().out.splitlines()


def test_plain_build_writes_the_haiku_prime_too(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch)
    out = tmp_path / ".superlite" / "prime.md"
    code, lines = run(plan, out, capsys)
    assert code == 0 and out.is_file() and (out.parent / "prime-haiku.md").is_file()
    assert len(lines) == 2 and lines[1].endswith(" prime-haiku.md")
    data = (out.parent / "prime-haiku.md").read_bytes()
    assert lines[1] == f"{hashlib.sha256(data).hexdigest()} {len(data)} prime-haiku.md"


def test_haiku_prime_bytes_match_tier_haiku(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch)
    out = tmp_path / "a" / "prime.md"
    run(plan, out, capsys)
    other = tmp_path / "b" / "prime.md"
    assert run(plan, other, capsys, "--tier", "haiku")[0] == 0
    assert (out.parent / "prime-haiku.md").read_bytes() == other.read_bytes()


def test_no_haiku_task_writes_no_haiku_prime(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch, {"T1": "sonnet", "T2": "sonnet"})
    out = tmp_path / "a" / "prime.md"
    code, lines = run(plan, out, capsys)
    assert code == 0 and len(lines) == 1 and not (out.parent / "prime-haiku.md").exists()


def test_existing_haiku_prime_left_alone_without_haiku_task(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch, {"T1": "sonnet", "T2": "sonnet"})
    out = tmp_path / "a" / "prime.md"
    out.parent.mkdir()
    (out.parent / "prime-haiku.md").write_text("old", encoding="utf-8")
    run(plan, out, capsys)
    assert (out.parent / "prime-haiku.md").read_text(encoding="utf-8") == "old"


def test_haiku_prime_over_cap_writes_neither(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch)
    a = tmp_path / "x" / "prime.md"
    run(plan, a, capsys)
    big, small = sorted([a.stat().st_size, (a.parent / "prime-haiku.md").stat().st_size])
    out = tmp_path / "y" / "prime.md"
    with pytest.raises(SystemExit) as e:
        run(plan, out, capsys, "--max-bytes", str((big + small) // 2))
    assert e.value.code == 1 and not out.exists() and not (out.parent / "prime-haiku.md").exists()


def test_tier_haiku_unchanged(tmp_path, monkeypatch, capsys):
    plan = setup(tmp_path, monkeypatch)
    out = tmp_path / "z" / "prime.md"
    code, lines = run(plan, out, capsys, "--tier", "haiku")
    assert code == 0 and len(lines) == 1
    assert out.is_file() and not (out.parent / "prime-haiku.md").exists()


def test_plan_without_taskgraph_builds_only_the_main_prime(tmp_path, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    out = tmp_path / "a" / "prime.md"
    code, lines = run(plan, out, capsys)
    assert code == 0 and len(lines) == 1 and out.is_file()
    assert not (out.parent / "prime-haiku.md").exists()
