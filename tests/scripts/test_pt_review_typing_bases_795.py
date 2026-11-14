"""Tests for pt_review: a typing base (NamedTuple, TypedDict) reads as a base (#795)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_795", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_795"] = pt_review
_spec.loader.exec_module(pt_review)

GATE = '''from typing import NamedTuple, TypedDict


class Admission(NamedTuple):
    gate: str
    ok: bool


class Opts(TypedDict):
    name: str
'''


def project(root: Path) -> Path:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "full_gate.py").write_text(GATE, encoding="utf-8")
    return root


def check(root: Path, produces: str) -> list[str]:
    project(root)
    (root / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        f"### T1 gate · Complexity 3\n**Owns:** src/pkg/full_gate.py\n**Produces:** {produces}\n\n"
        "## Review Focus\n- gate: state\n", encoding="utf-8")
    out, _ = pt_review.check_interfaces(pt_review.parse_plan(root / "plan.md"), root, None)
    return [m.msg for m in out]


def test_namedtuple_base_matches(tmp_path):
    assert check(tmp_path, "pkg.full_gate.Admission(NamedTuple)") == []


def test_typeddict_base_matches(tmp_path):
    assert check(tmp_path, "pkg.full_gate.Opts(TypedDict)") == []


def test_namedtuple_fields_still_compared(tmp_path):
    assert check(tmp_path / "a", "pkg.full_gate.Admission(gate: str, ok: bool)") == []
    msgs = check(tmp_path / "b", "pkg.full_gate.Admission(gate: str)")
    assert any("extra parameter 'ok'" in m for m in msgs)


def test_wrong_base_still_reported(tmp_path):
    assert len(check(tmp_path, "pkg.full_gate.Admission(Exception)")) >= 1
