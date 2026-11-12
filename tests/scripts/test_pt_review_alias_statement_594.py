"""#594: the contract check skips statement lines and expands module-level type aliases."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

KEY = "tuple[str, tuple[tuple[str, str], ...], int]"


def write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def run(tmp_path: Path, code: str, produces: str, extra: dict | None = None):
    write(tmp_path, "dm/__init__.py", "")
    write(tmp_path, "dm/series.py", code)
    for rel, text in (extra or {}).items():
        write(tmp_path, rel, text)
    write(tmp_path, "plan.md", "# Plan\n\n### T1 series\n**Owns:** dm/series.py\n"
                              f"**Produces:** {produces}\n")
    plan = pt_review.parse_plan(tmp_path / "plan.md")
    return pt_review.check_interfaces(plan, tmp_path, None)


def test_alias_return_matches_expansion(tmp_path):
    code = f"SeriesKey = {KEY}\n\ndef key_of(row: dict) -> {KEY}:\n    return ('a', (), 1)\n"
    mism, n = run(tmp_path, code, "dm.series.key_of(row: dict) -> SeriesKey")
    assert mism == [] and n == 1


def test_alias_mismatch_still_reported(tmp_path):
    code = f"SeriesKey = {KEY}\n\ndef key_of(row: dict) -> tuple[str, int]:\n    return ('a', 1)\n"
    mism, _n = run(tmp_path, code, "dm.series.key_of(row: dict) -> SeriesKey")
    assert len(mism) == 1 and "SeriesKey" in mism[0].msg


def test_fixture_statement_line_skipped(tmp_path):
    write(tmp_path, "Package.swift", "// swift-tools-version:5.9\n")
    write(tmp_path, "Sources/App/CardSamples.swift", "struct Sample {}\n")
    write(tmp_path, "plan.md", "# Plan\n\n### T1 samples\n**Owns:** Sources/App/CardSamples.swift\n"
          "**Produces:** weekly:heart:2026-W37 card ranges == [7d, 30d, 90d]\n")
    plan = pt_review.parse_plan(tmp_path / "plan.md")
    mism, _n = pt_review.check_interfaces(plan, tmp_path, None)
    assert not any("not declared" in m.msg for m in mism)


def test_alias_param_matches(tmp_path):
    code = f"SeriesKey = {KEY}\n\ndef f(k: {KEY}) -> int:\n    return 1\n"
    mism, _n = run(tmp_path, code, "dm.series.f(k: SeriesKey) -> int")
    assert mism == []


def test_code_alias_plan_expansion(tmp_path):
    code = f"SeriesKey = {KEY}\n\ndef key_of(row: dict) -> SeriesKey:\n    return ('a', (), 1)\n"
    mism, _n = run(tmp_path, code, f"dm.series.key_of(row: dict) -> {KEY}")
    assert mism == []


def test_typealias_annotation(tmp_path):
    f = tmp_path / "m.py"
    write(tmp_path, "m.py", "from typing import TypeAlias\nRows: TypeAlias = list[dict[str, int]]\n"
                            "LIMIT = 3\nname = 'x'\n")
    assert pt_review.module_aliases(f) == {"Rows": "list[dict[str, int]]"}


def test_alias_examples(tmp_path):
    write(tmp_path, "a.py", f"SeriesKey = {KEY}\nLIMIT = 3\nname = 'x'\n")
    assert pt_review.module_aliases(tmp_path / "a.py") == {"SeriesKey": KEY}


def test_imported_alias(tmp_path):
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/kinds.py", f"SeriesKey = {KEY}\n")
    write(tmp_path, "pkg/use.py", "from .kinds import SeriesKey\n")
    assert pt_review.module_aliases(tmp_path / "pkg" / "use.py") == {"SeriesKey": KEY}


def test_symbol_names_statement():
    assert pt_review.symbol_names("weekly:heart:2026-W37 card ranges == [7d, 30d, 90d]") == []
    assert pt_review.symbol_names("total: Int") == ["total"]
    assert pt_review.symbol_names("`weekly: [Card]` fixture == 3 cards") == ["weekly"]
