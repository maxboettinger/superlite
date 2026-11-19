"""Tests for the packet's base-skips tag (#886): SKIPPED rows the base commit skips too."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
from _fixtures import FIXTURES  # noqa: E402

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

BASE_FILE = {"mode": "base", "base": "abc1234def5678", "skipped_tests": ["t.py::a"], "compared": ["t.py::a", "t.py::b"]}


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(FIXTURES / "review_basic", dest)
    return dest


def make_run(proj: Path, base_file: dict | str | None) -> Path:
    run = proj / "run"
    run.mkdir()
    (run / "test-summary-full.json").write_text(json.dumps({
        "mode": "full", "passed": 5, "failed": 0, "skipped": 2, "started": 1.0,
        "skipped_tests": ["t.py::a", "t.py::b"]}), encoding="utf-8")
    if base_file is not None:
        text = base_file if isinstance(base_file, str) else json.dumps(base_file)
        (run / "test-summary-base.json").write_text(text, encoding="utf-8")
    return run


def packet(proj: Path, run: Path, base: str, capsys) -> tuple[str, str]:
    out = proj / "packet.md"
    rc = pt_review.main(["packet", "--plan", str(proj / "plan.md"), "--root", str(proj), "--log", str(proj / "incidents.jsonl"),
                         "--out", str(out), "--tests", str(run / "test-summary-full.json"), "--base", base])
    assert rc in (0, 1)
    return out.read_text(encoding="utf-8"), capsys.readouterr().out


def test_skipped_rows_tagged(proj, capsys):
    run = make_run(proj, BASE_FILE)
    text, _ = packet(proj, run, "abc1234", capsys)
    assert "- SKIPPED: t.py::a (base skips too)\n" in text
    assert "- SKIPPED: t.py::b\n" in text


def test_base_mismatch_no_tag(proj, capsys):
    run = make_run(proj, BASE_FILE)
    text, out = packet(proj, run, "fff0000", capsys)
    assert "(base skips too)" not in text
    assert "note: skipped tests not compared with the base" in out


def test_no_base_file_note(proj, capsys):
    run = make_run(proj, None)
    _, out = packet(proj, run, "abc1234", capsys)
    assert "note: skipped tests not compared with the base; run " in out
    assert "run_tests --base-skips" in out
    run2 = proj / "run2"
    run2.mkdir()
    (run2 / "test-summary-full.json").write_text(json.dumps({"mode": "full", "passed": 5, "failed": 0, "skipped": 0, "started": 1.0}), encoding="utf-8")
    _, out2 = packet(proj, run2, "abc1234", capsys)
    assert "not compared with the base" not in out2


def test_base_file_not_a_run_summary(proj):
    run = make_run(proj, BASE_FILE)
    runs = pt_review.run_summaries(run / "test-summary-full.json")
    assert runs and not any(r.get("mode") == "base" for r in runs)


def test_base_skipped_bad_file(proj):
    run = make_run(proj, "not json")
    assert pt_review.base_skipped(run / "test-summary.json", "abc1234") is None
    (run / "test-summary-base.json").write_text(json.dumps({**BASE_FILE, "mode": "fast"}), encoding="utf-8")
    assert pt_review.base_skipped(run / "test-summary.json", "abc1234") is None
    (run / "test-summary-base.json").write_text(json.dumps(BASE_FILE), encoding="utf-8")
    assert pt_review.base_skipped(run / "test-summary.json", "abc1234") == {"t.py::a"}
    assert pt_review.base_skipped(run / "test-summary.json", "fff0000") is None
    assert pt_review.base_skipped(run / "test-summary.json", None) == {"t.py::a"}
