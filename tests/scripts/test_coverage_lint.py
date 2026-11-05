"""Lint COVERAGE issues (plan level) and packet section 0c (#144)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest
from _fixtures import FIXTURES as _FIXTURES

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan_tools  # noqa: E402

# Import by path under a private name so an installed `coverage` package (pytest-cov) is never shadowed.
if "sl_coverage" in sys.modules:
    coverage = sys.modules["sl_coverage"]
else:
    _spec = importlib.util.spec_from_file_location("sl_coverage", SCRIPTS / "coverage.py")
    coverage = importlib.util.module_from_spec(_spec)
    sys.modules["sl_coverage"] = coverage
    _spec.loader.exec_module(coverage)

BASE = (_FIXTURES / "plans" / "minisheet.md").read_text(encoding="utf-8")
NOTE_START = "NOTE: no ## Coverage section"
PACKET_PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n"


def table(states: dict[str, str] | None = None, default: str = "settled") -> str:
    states = states or {}
    rows = [f"| {n} | {states.get(n, default)} | spec section 1 |" for n, _ in coverage.categories()]
    return "## Coverage\n\n| Category | State | Basis |\n|---|---|---|\n" + "\n".join(rows) + "\n"


def write(tmp_path: Path, text: str, name: str = "plan.md") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def lint(p: Path, *extra: str):
    return subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--plan", str(p), *extra],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


def test_open_coverage_is_plan_level(tmp_path):
    p = write(tmp_path, BASE + "\n" + table({"Error handling and recovery": "open"}))
    plan = plan_tools.Plan.load(str(p))
    issues, _ = plan_tools.lint_plan(plan, plan_tools.build_parser().parse_args(["lint", "--plan", str(p)]))
    hits = [i for i in issues if str(i).startswith("COVERAGE: 'Error handling and recovery' is open")]
    assert len(hits) == 1
    assert hits[0].scope == "plan" and tuple(hits[0].tasks) == ()
    stable, _fix, _pi = plan_tools.stable_partition(plan, issues, [])
    assert "T1" in stable


def test_open_coverage_survives_a_foreign_coverage_module(tmp_path, monkeypatch):
    """The PyPI `coverage` package in sys.modules must not shadow scripts/coverage.py (lint_plan)."""
    monkeypatch.setitem(sys.modules, "coverage", types.ModuleType("coverage"))
    p = write(tmp_path, BASE + "\n" + table({"Error handling and recovery": "open"}))
    plan = plan_tools.Plan.load(str(p))
    issues, _ = plan_tools.lint_plan(plan, plan_tools.build_parser().parse_args(["lint", "--plan", str(p)]))
    assert any(str(i).startswith("COVERAGE: 'Error handling and recovery' is open") for i in issues)


def test_lint_exit_codes(tmp_path):
    p = write(tmp_path, BASE + "\n" + table({"Error handling and recovery": "open"}))
    cp = lint(p)
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert "ISSUE: COVERAGE:" in cp.stdout
    q = write(tmp_path, BASE, "plain.md")
    cp = lint(q)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert NOTE_START in cp.stdout


def test_full_table_lints_clean(tmp_path):
    cp = lint(write(tmp_path, BASE + "\n" + table()))
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "COVERAGE" not in cp.stdout and NOTE_START not in cp.stdout


def test_off_in_plan_or_spec(tmp_path):
    cp = lint(write(tmp_path, BASE + "\n**Coverage:** off\n"))
    assert NOTE_START not in cp.stdout and "COVERAGE" not in cp.stdout
    spec = write(tmp_path, "# Spec\n\n**Coverage:** off\n", "spec.md")
    cp = lint(write(tmp_path, BASE, "other.md"), "--spec", str(spec))
    assert NOTE_START not in cp.stdout


def test_spec_coverage_heading_needs_no_task(tmp_path):
    spec = write(tmp_path, "# Spec\n\n## Coverage\n\n| a | b |\n", "spec.md")
    cp = lint(write(tmp_path, BASE), "--spec", str(spec))
    assert "SPEC section 'Coverage'" not in cp.stdout


# ---------------------------------------------------------------- packet

def packet(tmp_path: Path, plan_text: str, *extra: str, inline: bool = False) -> str:
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                    capture_output=True, text=True, check=True)
    if not (tmp_path / ".git").exists():
        git("init", "-q")
    f = write(tmp_path, plan_text, "spec.md" if inline else "plan.md")
    src = ["--inline", "--spec", str(f)] if inline else ["--plan", str(f)]
    base = ["--base", "HEAD"] if inline else []
    if inline:
        (tmp_path / "x.txt").write_text("x\n", encoding="utf-8")
        git("add", "x.txt")
        git("commit", "-qm", "base")
        base = ["--base", git("rev-parse", "HEAD").stdout.strip()]
    r = subprocess.run([sys.executable, str(SCRIPTS / "pt_review.py"), "packet", "--root", str(tmp_path),
                        "--out", str(tmp_path / "packet.md"), "--wait-timeout", "1", *src, *base, *extra],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    return (tmp_path / "packet.md").read_text(encoding="utf-8")


def test_packet_carries_coverage(tmp_path):
    s = packet(tmp_path, PACKET_PLAN + "\n" + table({"Rollout": "ruled"}))
    assert "## 0c. Coverage (decision categories from the plan)" in s
    assert "| Rollout | ruled |" in s


def test_packet_without_coverage_has_no_0c(tmp_path):
    assert "## 0c." not in packet(tmp_path, PACKET_PLAN)


def test_inline_packet_unchanged(tmp_path):
    spec = "# Spec\n\nRuling: flat.\n\n" + table() + "\n## Review Focus\n\n- a: b\n"
    s = packet(tmp_path, spec, inline=True)
    assert "## 0c." not in s
    assert s.count("| Rollout | settled |") == 1


def test_packet_coverage_section_is_capped(tmp_path):
    big = PACKET_PLAN + "\n## Coverage\n\n" + "\n".join(f"| row{i} | settled | " + "x" * 80 + " |" for i in range(200)) + "\n"
    s = packet(tmp_path, big)
    sec = s.split("## 0c.", 1)[1].split("\n## ", 1)[0]
    assert len(sec) < 3300 and "truncated" in sec


def test_packet_section_0c_survives_a_foreign_coverage_module(tmp_path, monkeypatch):
    """cmd_packet in-process, with a foreign `coverage` module in sys.modules, still writes section 0c."""
    import pt_review
    monkeypatch.setitem(sys.modules, "coverage", types.ModuleType("coverage"))
    (tmp_path / ".superlite").mkdir()
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], capture_output=True, check=True)
    f = write(tmp_path, PACKET_PLAN + "\n" + table({"Rollout": "ruled"}), "plan.md")
    rc = pt_review.main(["packet", "--root", str(tmp_path), "--out", str(tmp_path / "packet.md"),
                         "--wait-timeout", "1", "--plan", str(f)])
    assert rc == 0
    assert "## 0c. Coverage (decision categories from the plan)" in (tmp_path / "packet.md").read_text(encoding="utf-8")
