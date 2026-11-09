"""Tests for pt_review packet: a run whose code changed afterwards is outdated, not open (#366)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_outdated", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_outdated"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** src/mod.py\n\n## Review Focus\n- none\n"
NOW = time.time()
FAIL = "tests/test_mod.py::test_x: AssertionError"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    (tmp_path / "src" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "src" / "other.py").write_text("Y = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_mod.py").write_text("import mod\n\n\ndef test_x():\n    assert mod.X == 2\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", ":!.superlite")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return tmp_path


def setup(proj: Path, mtimes: dict[str, float], agent: str = "run_tests", change: tuple[str, ...] = ("src/mod.py",)) -> str:
    base = git(proj, "rev-parse", "HEAD")
    for f in change:
        p = proj / f
        p.write_text(p.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    for f, t in mtimes.items():
        os.utime(proj / f, (t, t))
    inc = {"file": "tests/test_mod.py", "line": 3, "context": "test_x: AssertionError", "agent": agent,
           "kind": "test-failure", "resolution": "open", "epoch": NOW - 100}
    (proj / ".superlite" / "incidents.jsonl").write_text(json.dumps(inc) + "\n", encoding="utf-8")
    summ = {"passed": 0, "failed": 1, "skipped": 0, "mode": "fast", "started": NOW - 110, "failures": [FAIL],
            "skipped_tests": [], "files": {"tests/test_mod.py": [0, 1]}}
    (proj / ".superlite" / "test-summary.json").write_text(json.dumps(summ), encoding="utf-8")
    return base


def packet(proj: Path, base: str | None) -> str:
    cmd = [sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"), "--root", str(proj),
           "--out", str(proj / "packet.md")] + (["--base", base] if base else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (proj / "packet.md").read_text(encoding="utf-8")


def sec(t: str, n: int) -> str:
    return t.split(f"## {n}. ")[1].split("\n## ")[0]


OLD = {"tests/test_mod.py": NOW - 200}


def test_redstep_incident_is_outdated(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 50})
    t = packet(proj, base)
    assert "FAST PATH" in t
    assert "- none" in sec(t, 1) and "moved 1 outdated test-failure incident(s) to section 4" in sec(t, 1)
    s4 = sec(t, 4)
    assert "- passed 0 · failed 1 (1 outdated) · skipped 0" in s4
    assert f"- OUTDATED: {FAIL} (src/mod.py changed after this run; the full suite decides)" in s4
    assert "- OUTDATED incident: tests/test_mod.py:3 test_x: AssertionError (src/mod.py changed after it)" in s4
    assert "FAILING" not in s4


def test_outdated_incident_not_counted_as_stale(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 50})
    assert "dropped" not in sec(packet(proj, base), 1)


def test_failure_after_last_change_stays_open(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 200})
    t = packet(proj, base)
    assert "failing tests 1" in t and "tests/test_mod.py" in sec(t, 1)
    assert "OUTDATED" not in t


def test_unrelated_change_keeps_failure_open(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 200, "src/other.py": NOW - 50}, change=("src/mod.py", "src/other.py"))
    t = packet(proj, base)
    assert "failing tests 1" in t and "OUTDATED" not in t


def test_edited_test_file_makes_failure_outdated(proj):
    base = setup(proj, {"tests/test_mod.py": NOW - 50, "src/mod.py": NOW - 200})
    t = packet(proj, base)
    assert "(tests/test_mod.py changed after this run" in sec(t, 4)
    assert "FAST PATH" in t


def test_agent_logged_failure_never_outdated(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 50}, agent="T1")
    t = packet(proj, base)
    assert "test_x: AssertionError" in sec(t, 1) and "moved" not in sec(t, 1)
    assert "FAST PATH" not in t


def test_no_base_checks_only_test_file(proj):
    setup(proj, {**OLD, "src/mod.py": NOW - 50})
    t = packet(proj, None)
    assert "OUTDATED" not in t and "failing tests 1" in t


def test_summary_without_started_never_outdated(proj):
    base = setup(proj, {**OLD, "src/mod.py": NOW - 50})
    p = proj / ".superlite" / "test-summary.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    del d["started"]
    p.write_text(json.dumps(d), encoding="utf-8")
    t = packet(proj, base)
    assert "FAILING: " + FAIL in sec(t, 4)


def test_test_inputs_values(proj):
    changed = {"src/mod.py", "src/other.py", "tests/conftest.py"}
    (proj / "tests" / "conftest.py").write_text("", encoding="utf-8")
    assert pt.test_inputs(proj, "tests/test_mod.py", changed) == ["tests/test_mod.py", "src/mod.py", "tests/conftest.py"]
    assert pt.test_inputs(proj, "tests/test_mod.py", None) == ["tests/test_mod.py"]
    assert pt.test_inputs(proj, "tests/missing.py", changed) == ["tests/missing.py"]


def test_test_inputs_dotted_prefix(proj):
    (proj / "tests" / "test_pkg.py").write_text("from pkg.sub import thing\n", encoding="utf-8")
    (proj / "src" / "pkg").mkdir()
    (proj / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "src" / "pkg" / "sub.py").write_text("", encoding="utf-8")
    got = pt.test_inputs(proj, "tests/test_pkg.py", {"src/pkg/__init__.py", "src/pkg/sub.py", "src/other.py"})
    assert got == ["tests/test_pkg.py", "src/pkg/__init__.py", "src/pkg/sub.py"]


def test_changed_after_values(proj):
    for f in ("tests/test_mod.py", "src/mod.py"):
        os.utime(proj / f, (900, 900))
    os.utime(proj / "src" / "mod.py", (1100, 1100))
    assert pt.changed_after(proj, ["tests/test_mod.py", "src/mod.py"], 1000.0) == "src/mod.py"
    assert pt.changed_after(proj, ["tests/test_mod.py"], 1000.0) is None
    assert pt.changed_after(proj, ["tests/test_mod.py", "gone.py"], 1000.0) == "gone.py"
