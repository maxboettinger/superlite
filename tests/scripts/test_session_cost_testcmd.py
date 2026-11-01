"""Session-cost: resolve_related maps source paths to tests for --fast."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import testcmd  # noqa: E402
from test_plan_tools import run  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"


def _py_project(tmp_path: Path, src: str, test: str | None):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    sp = tmp_path / src
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("x = 1\n", encoding="utf-8")
    if test is not None:
        tp = tmp_path / test
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text("def test_ok():\n    assert True\n", encoding="utf-8")


def test_related_name_convention_py(tmp_path):
    _py_project(tmp_path, "src/foo.py", "tests/test_foo.py")
    assert testcmd.resolve_related(str(tmp_path), "src/foo.py") == ["tests/test_foo.py"]


def test_related_path_with_spaces(tmp_path):
    """Review Focus: encoding — paths with spaces."""
    _py_project(tmp_path, "src/my module.py", "tests/test_my module.py")
    assert testcmd.resolve_related(str(tmp_path), "src/my module.py") == [
        "tests/test_my module.py"
    ]


def test_related_missing_raises(tmp_path):
    """Review Focus: file — missing related tests."""
    _py_project(tmp_path, "src/missing.py", None)
    with pytest.raises(FileNotFoundError, match=r"no tests found for src/missing\.py"):
        testcmd.resolve_related(str(tmp_path), "src/missing.py")


def test_fast_source_path_fails_loud(tmp_path):
    _py_project(tmp_path, "src/gone.py", None)
    cp = run(RUN_TESTS, "--fast", "src/gone.py", cwd=tmp_path)
    assert cp.returncode != 0
    assert "no tests found" in (cp.err + cp.out)


def test_related_template_from_config(tmp_path):
    _py_project(tmp_path, "src/foo.py", "spec/unit_foo.py")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / "test-cmd.json").write_text(
        json.dumps({
            "language": "python",
            "test": "pytest",
            "related": "spec/unit_{src}.py",
        }),
        encoding="utf-8",
    )
    # name-convention file must NOT win when related template is set
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_foo.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert testcmd.resolve_related(str(tmp_path), "src/foo.py") == ["spec/unit_foo.py"]


@pytest.mark.parametrize("path", [
    "Tests/FooTests/BarTests.swift", "src/foo.test.ts", "src/foo.spec.tsx", "__tests__/a.ts",
    "test/a.go", "Spec/a.rb", "x/foo_spec.rb", "x/FooTest.java", "tests/test_a.py", "a/b_test.go",
])
def test_is_test_path_true(path):
    assert testcmd.is_test_path(path)


@pytest.mark.parametrize("path", ["Sources/App/Foo.swift", "src/foo.ts", "src/foo.py", "src/contest.py"])
def test_is_test_path_false(path):
    assert not testcmd.is_test_path(path)


def test_expand_fast_paths_passes_non_python_through(tmp_path, monkeypatch):
    import run_tests
    for rel in ("Sources/App/Foo.swift", "Tests/FooTests/BarTests.swift", "src/foo.ts", "src/foo.test.ts"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    paths = ["Sources/App/Foo.swift", "Tests/FooTests/BarTests.swift", "src/foo.ts", "src/foo.test.ts"]
    assert run_tests.expand_fast_paths(paths) == paths


def test_expand_fast_paths_python_without_test_fails(tmp_path, monkeypatch):
    import run_tests
    _py_project(tmp_path, "src/gone.py", None)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        run_tests.expand_fast_paths(["src/gone.py"])


def test_expand_fast_paths_maps_with_related_template(tmp_path, monkeypatch):
    import run_tests
    _py_project(tmp_path, "src/foo.ts", "spec/unit_foo.ts")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"related": "spec/unit_{src}.ts"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_tests.expand_fast_paths(["src/foo.ts"]) == ["spec/unit_foo.ts"]


def test_swift_fast_keeps_only_testing(tmp_path):
    (tmp_path / "Tests" / "CoreTests").mkdir(parents=True)
    p = tmp_path / "Tests" / "CoreTests" / "LibraryTests.swift"
    p.write_text("x\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({
        "language": "swift", "test": "xcodebuild test -scheme X",
        "test_file": "xcodebuild test -scheme X {only_testing}"}), encoding="utf-8")
    spec = testcmd.resolve(str(tmp_path), ["Tests/CoreTests/LibraryTests.swift"])
    assert "-only-testing:CoreTests/LibraryTests" in spec["command"]


def test_expand_fast_paths_non_python_spec_passes_py_source_through(tmp_path, monkeypatch):
    import run_tests
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.py").write_text("x\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "go", "test": "make test"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert run_tests.expand_fast_paths(["src/b.py"]) == ["src/b.py"]
