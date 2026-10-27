"""Tests for pt_review noise fixes: one Produces parser, member names, no duplicate incidents."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from _fixtures import FIXTURES

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)


def proj(tmp_path: Path) -> Path:
    dest = tmp_path / "noiseproj"
    shutil.copytree(FIXTURES / "review_noise", dest)
    return dest


def contract(p: Path, *extra: str) -> int:
    return pt_review.main(["contract", "--plan", str(p / "plan.md"), "--root", str(p), *extra])


def mismatch_lines(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith("MISMATCH")]


def test_eg_lines_not_produces(tmp_path, capsys):
    p = proj(tmp_path)
    plan = pt_review.parse_plan(p / "plan.md")
    assert plan.tasks["T1"].produces() == ["Strings.libraryMoreTags(_ n: Int) -> String", "Theme.Symbol.libraryTag"]
    assert contract(p, "--seam", "T1,T2") == 0
    out = capsys.readouterr().out
    assert mismatch_lines(out) == []


def test_dotted_member_checked_by_leaf(tmp_path, capsys):
    p = proj(tmp_path)
    assert contract(p, "--seam", "T1,T2") == 0
    capsys.readouterr()
    (p / "Sources/Kit/ThemeSymbol.swift").write_text("extension Mode {\n    case dark\n}\n")
    assert contract(p, "--seam", "T1,T2") == 1
    lines = mismatch_lines(capsys.readouterr().out)
    assert len(lines) == 1 and "`libraryTag`" in lines[0]


def test_swift_extension_and_case_declare(tmp_path):
    p = proj(tmp_path)
    plan = pt_review.parse_plan(p / "plan.md")
    files = ["Sources/Kit/ThemeSymbol.swift"]
    assert pt_review.find_declaration(p, files, "Mode")
    assert pt_review.find_declaration(p, files, "dark")
    assert pt_review.find_declaration(p, files, "nothere") is None
    assert pt_review.code_owns(plan, "T1") == ["Sources/Kit/Strings.swift", "Sources/Kit/ThemeSymbol.swift"]


def test_docs_only_task_skipped(tmp_path, capsys):
    p = proj(tmp_path)
    plan = pt_review.parse_plan(p / "plan.md")
    assert pt_review.code_owns(plan, "T3") == []
    assert contract(p) == 0
    out = capsys.readouterr().out
    assert "note: part1: T3 has no code files; Produces not checked" in out
    assert mismatch_lines(out) == []


def test_seam_run_does_not_duplicate_open_incident(tmp_path, capsys):
    p = proj(tmp_path)
    (p / "Sources/Kit/ThemeSymbol.swift").write_text("extension Mode {\n}\n")
    assert contract(p, "--seam", "T1,T2") == 1
    assert contract(p, "--seam", "T1,T2") == 1
    capsys.readouterr()
    log = [json.loads(ln) for ln in (p / ".superlite" / "incidents.jsonl").read_text().splitlines()]
    open_ = [e for e in log if e["agent"] == "pt_review" and e["resolution"] == "open"]
    assert len(open_) == 1


def test_packet_counts_distinct_items(tmp_path):
    entry = {"file": "a.swift", "line": 3, "context": "same", "agent": "pt_review", "kind": "exception",
             "resolution": "open"}
    items = pt_review.incident_items([dict(entry), dict(entry)])
    assert len(items) == 1
    assert "1 entry" in items[0].title
    other = dict(entry, context="different")
    assert "2 entries" in pt_review.incident_items([dict(entry), other])[0].title


def test_adapter_without_probe_entries_exits_0(tmp_path, capsys):
    p = proj(tmp_path)
    out_file = tmp_path / "adapter.py"
    rc = pt_review.main(["adapter", "--plan", str(p / "plan.md"), "--root", str(p), "--out", str(out_file)])
    assert rc == 0
    assert "adapter: no Probe entry lines; probes skipped" in capsys.readouterr().out
    assert not out_file.exists()


def test_same_mismatch_twice_in_one_run_logs_once(tmp_path, capsys):
    p = proj(tmp_path)
    plan = (p / "plan.md").read_text()
    (p / "Sources/Kit/ThemeSymbol.swift").write_text("extension Mode {\n}\n")
    m = pt_review.Mismatch(1, "Sources/Kit/ThemeSymbol.swift", 1, "T1 Produces: `x` not declared in a", "T1")
    orig = pt_review.check_interfaces
    pt_review.check_interfaces = lambda *a, **k: ([m, m], 2)
    try:
        assert contract(p, "--seam", "T1,T2") == 1
    finally:
        pt_review.check_interfaces = orig
    capsys.readouterr()
    log = [json.loads(ln) for ln in (p / ".superlite" / "incidents.jsonl").read_text().splitlines()]
    assert len([e for e in log if e["agent"] == "pt_review" and e["resolution"] == "open"]) == 1
