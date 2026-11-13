"""#712: plan lint warns once per task that owns package files commit_task cannot import by their package name."""
import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools as ptm  # noqa: E402

PLAN = """# Plan
**Goal:** x.

### T1 tool · Complexity 2 · Est. context 30k
**Owns:** tools/pkg/__init__.py, tools/pkg/a.py, tools/pkg/b.py, tests/test_a.py

### T2 app · Complexity 2 · Est. context 30k
**Owns:** app/main.py, tests/test_main.py, docs/x.md
"""
WARN = ("WARNING: PYTHONPATH: T1 owns tools/pkg/__init__.py and 2 more, not importable by their own package name from the repo root, "
        "src/ or a pythonpath root; commit_task's import check fails on them unless you ")


def proj(tmp_path, text=PLAN, cfg=None):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".git").mkdir()
    if cfg is not None:
        (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    (tmp_path / "plan.md").write_text(text, encoding="utf-8")
    return ptm.Plan.load(str(tmp_path / "plan.md"))


def test_warns_once_per_task(tmp_path):
    assert ptm.pythonpath_warnings(proj(tmp_path), tmp_path) == [
        WARN + 'add "pythonpath": ["tools"] to .superlite/test-cmd.json']


def test_configured_root_is_quiet(tmp_path):
    assert ptm.pythonpath_warnings(proj(tmp_path, cfg={"test": "pytest", "pythonpath": ["tools"]}), tmp_path) == []


def test_other_configured_root_names_the_entry_to_add(tmp_path):
    assert ptm.pythonpath_warnings(proj(tmp_path, cfg={"test": "pytest", "pythonpath": ["lib"]}), tmp_path) == [
        WARN + 'add "tools" to "pythonpath" in .superlite/test-cmd.json']


def test_existing_file_with_root_imports_is_quiet(tmp_path):
    text = PLAN.replace("tools/pkg/__init__.py, tools/pkg/a.py, tools/pkg/b.py, tests/test_a.py", "tools/pkg/a.py")
    plan = proj(tmp_path, text)
    (tmp_path / "tools" / "pkg").mkdir(parents=True)
    (tmp_path / "tools" / "pkg" / "a.py").write_text("from tools.pkg import b\n", encoding="utf-8")
    (tmp_path / "tools" / "pkg" / "b.py").write_text("Y = 1\n", encoding="utf-8")
    assert ptm.pythonpath_warnings(plan, tmp_path) == []


def test_draft_task_and_no_root_are_skipped(tmp_path):
    text = PLAN.replace("**Owns:** tools/pkg", "**Status:** draft\n**Owns:** tools/pkg")
    assert ptm.pythonpath_warnings(proj(tmp_path, text), tmp_path) == []
    assert ptm.pythonpath_warnings(ptm.Plan.load(str(tmp_path / "plan.md")), None) == []


def test_lint_prints_the_warning(tmp_path):
    proj(tmp_path)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(tmp_path / "home"))
    out = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--plan", str(tmp_path / "plan.md")],
                         capture_output=True, text=True, cwd=tmp_path, env=env, timeout=120).stdout
    assert out.count("WARNING: PYTHONPATH: T1 owns tools/pkg/__init__.py and 2 more") == 1
