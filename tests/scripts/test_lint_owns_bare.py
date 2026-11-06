"""Lint: a bare file name in an Owns list after a path entry names no folder (#195)."""
from __future__ import annotations

from test_plan_tools import make_plan, pt


def lint(tmp_path, owns, *extra):
    p = make_plan(tmp_path, [{"id": "T1", "owns": owns}])
    return pt("lint", "--plan", p, *extra, cwd=tmp_path)


def test_bare_name_after_path_flagged(tmp_path):
    cp = lint(tmp_path, "Sources/A/x.swift, y.swift, z.swift (same folder)")
    assert "T1: Owns entry `y.swift` has no folder" in cp.both
    assert "Sources/A/y.swift" in cp.both
    assert "(after `Sources/A/x.swift`)" in cp.both
    assert "list root-level files before paths" in cp.both
    p = tmp_path / "plan.md"
    st = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    fix = st.out.split("FIX:")[1]
    assert "T1:" in fix and "has no folder" in fix


def test_existing_root_file_not_flagged(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert "has no folder" not in lint(tmp_path, "src/a.py, package.json").both


def test_root_files_first_not_flagged(tmp_path):
    assert "has no folder" not in lint(tmp_path, "Makefile, src/a.py").both


def test_glob_and_dir_not_flagged(tmp_path):
    assert "has no folder" not in lint(tmp_path, "src/a.py, *.csproj, docs/").both
