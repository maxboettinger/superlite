"""Tests for pt_review packet: stale, ruled, gone and killed-run incidents are not open findings (#592)."""
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
_spec = importlib.util.spec_from_file_location("pt_review_592", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_592"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** a.py\n\n## Review Focus\n- none\n"
NOW = time.time()
KILLED = "run_tests stopped by SIGTERM; its test processes were killed"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "pkg" / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    for f in ("a.py", "b.py", "pkg/src/a.py", "tests/test_m.py"):
        (tmp_path / f).write_text("X = 1\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", ":!.superlite")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return tmp_path


def log(proj: Path, *entries: dict) -> None:
    (proj / ".superlite" / "incidents.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def summary(proj: Path, d: dict, name: str = "test-summary.json", age: float = 0) -> None:
    p = proj / ".superlite" / name
    p.write_text(json.dumps(d), encoding="utf-8")
    if age:
        os.utime(p, (NOW - age, NOW - age))


def packet(proj: Path, base: str | None = None) -> str:
    cmd = [sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"), "--root", str(proj),
           "--out", str(proj / "packet.md"), "--wait-timeout", "1"] + (["--base", base] if base else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (proj / "packet.md").read_text(encoding="utf-8")


def sec(t: str, n: int) -> str:
    return t.split(f"## {n}. ")[1].split("\n## ")[0]


def exc(file: str, line: int, **kw) -> dict:
    return {"file": file, "line": line, "kind": "exception", "agent": "package-reviewer", "resolution": "open",
            "context": "boom", "epoch": NOW - 100, **kw}


def nores(**kw) -> dict:
    return {"file": "-", "line": 0, "kind": "no-result", "agent": "run_tests", "task": "T1", "resolution": "open",
            "context": "no tests ran: x", "epoch": NOW - 100, **kw}


def later(**kw) -> dict:
    return {"passed": 4, "failed": 0, "skipped": 0, "mode": "fast", "task": "T1", "started": NOW - 50,
            "failures": [], "files": {"tests/test_m.py": [4, 0]}, **kw}


def test_norm_path_values(proj):
    assert pt.norm_path(proj, f"{proj}/pkg/src/a.py") == "pkg/src/a.py"
    assert pt.norm_path(proj, "pkg/pkg/src/a.py") == "pkg/src/a.py"
    assert pt.norm_path(proj, "-") == "-"
    assert pt.norm_path(proj, "./a.py") == "a.py"


def test_ruled_and_killed_values():
    assert pt.ruled({"file": "a.py", "line": 3, "kind": "exception"}, ["a.py:3 is out of plan"]) is True
    assert pt.ruled({"file": "a.py", "line": 3}, ["a.py:30 waits"]) is False
    assert pt.ruled({"file": "tests/t.py", "line": 0, "kind": "test-failure", "context": "tests/t.py::test_x: boom"},
                    ["tests/t.py::test_x fails on main too"]) is True
    assert pt.killed({"error": KILLED}) is True
    assert pt.killed({"error": "no test command found: ..."}) is False
    assert pt.killed({"passed": 3}) is False


def test_doubled_package_path_resolved_once(proj):
    log(proj, exc("pkg/pkg/src/a.py", 2))
    s1 = sec(packet(proj), 1)
    assert "pkg/src/a.py:2" in s1 and "pkg/pkg/" not in s1


def test_incident_on_deleted_file_left_out_and_named(proj):
    log(proj, exc("tests/test_tmp.py", 4))
    t = packet(proj)
    assert "left out 1 incident(s) on files no longer on disk: tests/test_tmp.py" in sec(t, 1)
    assert "### [" not in sec(t, 1) and "FAST PATH" in t


def test_ledger_ruling_leaves_incident_out(proj):
    log(proj, exc("a.py", 3))
    (proj / ".superlite" / "progress.md").write_text("- Ruling: a.py:3 is out of plan - pre-existing - none\n", encoding="utf-8")
    s1 = sec(packet(proj), 1)
    assert "left out 1 incident(s) a ledger Ruling: names" in s1 and "### [" not in s1
    (proj / ".superlite" / "progress.md").write_text("- Ruling: a.py:30 is out of plan - pre-existing - none\n", encoding="utf-8")
    assert "a.py:3 " in sec(packet(proj), 1)


@pytest.mark.parametrize("extra,gone", [({}, True), ({"task": "T2"}, False), ({"task": None, "mode": "full"}, True)])
def test_no_result_closed_by_later_task_run(proj, extra, gone):
    log(proj, nores())
    d = later(**{k: v for k, v in extra.items() if v is not None})
    if extra.get("task", 1) is None:
        d.pop("task")
    summary(proj, d)
    assert ("-:0" not in sec(packet(proj), 1)) is gone


def test_dash_failure_closed_by_later_green_task_run(proj):
    e = nores(kind="test-failure", context="boom")
    log(proj, e)
    summary(proj, later())
    assert "-:0" not in sec(packet(proj), 1)
    summary(proj, later(failed=1, failures=["tests/test_m.py::test_x: boom"]))
    assert "-:0" in sec(packet(proj), 1)


def test_dash_entry_never_outdated(proj):
    log(proj, nores(kind="test-failure", context="boom"))
    summary(proj, {"passed": 0, "failed": 1, "skipped": 0, "mode": "fast", "started": NOW - 110,
                   "failures": ["tests/test_m.py::test_x: boom"], "files": {"tests/test_m.py": [0, 1]}})
    base = git(proj, "rev-parse", "HEAD")
    (proj / "a.py").write_text("X = 2\n", encoding="utf-8")
    assert "OUTDATED incident: -:0" not in sec(packet(proj, base), 4)


def test_run_tests_close_is_no_claimed_fix(proj):
    o = {"file": "tests/test_m.py", "line": 0, "kind": "test-failure", "agent": "run_tests", "resolution": "open",
         "context": "tests/test_m.py::test_x: boom", "epoch": NOW - 100}
    log(proj, o, {**o, "resolution": "fixed", "context": "fixed: passed on a later run", "epoch": NOW - 10})
    base = git(proj, "rev-parse", "HEAD")
    (proj / "a.py").write_text("X = 2\n", encoding="utf-8")
    assert "claimed fixed by" not in packet(proj, base)


def test_claim_naming_changed_file_is_no_claimed_fix(proj):
    base = git(proj, "rev-parse", "HEAD")
    (proj / "b.py").write_text("X = 2\n", encoding="utf-8")
    log(proj, exc("a.py", 3), exc("a.py", 3, resolution="fixed", context="fixed in b.py: moved the guard"))
    assert "claimed fixed by" not in packet(proj, base)
    log(proj, exc("a.py", 3), exc("a.py", 3, resolution="fixed", context="fixed"))
    assert "a.py:3  claimed fixed by package-reviewer, file unchanged since base" in packet(proj, base)


def test_killed_run_shows_no_result(proj):
    summary(proj, {"passed": 0, "failed": 1, "skipped": 0, "mode": "fast", "error": KILLED, "failures": [KILLED], "files": {}})
    t = packet(proj)
    assert sec(t, 4).split("\n", 1)[1].startswith("- killed run, no result: run_tests stopped by SIGTERM")
    assert "FAILING" not in sec(t, 4) and "FAST PATH" in t


def test_error_summary_shows_newest_result_run(proj):
    summary(proj, {"passed": 0, "failed": 1, "skipped": 0, "mode": "fast",
                   "error": "no test command found: add one", "failures": ["no test command found: add one"], "files": {}}, age=100)
    summary(proj, {"passed": 5, "failed": 1, "mode": "full", "failures": ["tests/test_m.py::test_y: boom"],
                   "files": {"tests/test_m.py": [5, 1]}, "started": NOW - 50}, "test-summary-b2.json", age=200)
    os.utime(proj / "tests" / "test_m.py", (NOW - 500, NOW - 500))
    t = packet(proj)
    s4 = sec(t, 4)
    assert "- run without a result: no test command found" in s4
    assert "- newest run with a result:" in s4
    assert "- FAILING: tests/test_m.py::test_y: boom" in s4
    assert "failing tests 2" in t
