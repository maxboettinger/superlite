"""Tests for pt_review norm_path: a doubled multi-folder prefix collapses (#822)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_822", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_822"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** a.py\n\n## Review Focus\n- none\n"


def touch(root: Path, rel: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("X\n", encoding="utf-8")


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    touch(tmp_path, "Packages/P/Tests/x.swift")
    return tmp_path


def test_two_folder_prefix_collapsed(proj):
    assert pt.norm_path(proj, "Packages/P/Packages/P/Tests/x.swift") == "Packages/P/Tests/x.swift"


def test_one_folder_prefix_still_collapsed(tmp_path):
    touch(tmp_path, "pkg/src/a.py")
    assert pt.norm_path(tmp_path, "pkg/pkg/src/a.py") == "pkg/src/a.py"


def test_neither_exists_kept(proj):
    assert pt.norm_path(proj, "Packages/Q/Packages/Q/Tests/y.swift") == "Packages/Q/Packages/Q/Tests/y.swift"


def test_doubled_exists_kept(tmp_path):
    touch(tmp_path, "src/src/x.py")
    touch(tmp_path, "src/x.py")
    assert pt.norm_path(tmp_path, "src/src/x.py") == "src/src/x.py"


def test_section4_incident_path(proj):
    (proj / ".superlite").mkdir()
    (proj / "plan.md").write_text(PLAN, encoding="utf-8")
    touch(proj, "a.py")
    e = {"file": "Packages/P/Packages/P/Tests/x.swift", "line": 3, "context": "boom", "agent": "T1",
         "kind": "test-failure", "ts": "2026-01-01T00:00:00Z"}
    (proj / ".superlite" / "incidents.jsonl").write_text(json.dumps(e) + "\n", encoding="utf-8")
    cmd = [sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"), "--root", str(proj),
           "--out", str(proj / "packet.md"), "--wait-timeout", "1"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    text = (proj / "packet.md").read_text(encoding="utf-8")
    assert "Packages/P/Tests/x.swift" in text
    assert "Packages/P/Packages/P" not in text
