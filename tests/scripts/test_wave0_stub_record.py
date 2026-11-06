"""wave0.json records the stub files and the tasks that wait for T0; the brief checks stubs without the suite."""
from __future__ import annotations

import json

from test_plan_tools import run
from test_wave0 import HEAD, PY, WAVE0, brief, plan


def meta(tmp_path):
    return json.loads((tmp_path / ".superlite" / "briefs" / "wave0.json").read_text(encoding="utf-8"))


def test_wave0_json_records_stubs_and_wait(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python 3.12; pytest", "root `pyproject.toml`", PY)
    assert run(WAVE0, "--plan", p, cwd=tmp_path).returncode == 0
    m = meta(tmp_path)
    assert m["stubs"] == ["src/pkg/slug.py"]
    assert m["wait"] == ["T1"]


def test_no_consumed_produces_records_empty(tmp_path):
    tasks = [dict(PY[0]), {"tid": "T2", "title": "feed", "owns": "src/pkg/feed.py", "produces": "pkg.feed.build(items: list[str]) -> str"}]
    p = plan(tmp_path, "**Tech stack:** Python 3.12", "x", tasks)
    assert run(WAVE0, "--plan", p, cwd=tmp_path).returncode == 0
    m = meta(tmp_path)
    assert m["stubs"] == [] and m["wait"] == []


def test_brief_checks_stubs_without_suite(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python 3.12", "x", PY)
    run(WAVE0, "--plan", p, cwd=tmp_path)
    b = brief(tmp_path)
    assert '"$SL" testcmd' in b and "prints null" in b and "never create, change or narrow" in b
    assert "run_tests --full" not in b


def test_brief_keeps_pythonpath_rule(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python 3.12", "x", PY)
    run(WAVE0, "--plan", p, cwd=tmp_path)
    b = brief(tmp_path)
    assert '"pythonpath"' in b and "neither the repository root nor `src/`" in b
