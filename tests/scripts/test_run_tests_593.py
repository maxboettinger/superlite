"""run_tests: --record keeps its scope and never counts as the full run; a foreground full run keeps a copy;
--fast honours a test file's marker the addopts deselect (#593)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

PYPROJECT = "[tool.pytest.ini_options]\naddopts = \"-m 'not integration'\"\nmarkers = [\"integration\"]\n"


def rt(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SUPERLITE_FLEET_", "SUPERLITE_STATE_DIR"))}
    env.update(SUPERLITE_HOME=str(Path(cwd) / "_home"), PYTHONIOENCODING="utf-8")
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *map(str, args)], cwd=cwd, capture_output=True,
                        text=True, env=env, timeout=120)
    cp.both = cp.stdout + cp.stderr
    return cp


def summary(cwd, name="test-summary.json"):
    return json.loads((Path(cwd) / ".superlite" / name).read_text(encoding="utf-8"))


def ledger(cwd):
    return (Path(cwd) / ".superlite" / "progress.md").read_text(encoding="utf-8")


def test_record_keeps_its_scope_and_is_not_a_full_run(tmp_path):
    cp = rt(tmp_path, "--record", "--passed", "1", "--scope", "integration", "--command", "pytest -m integration")
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert (s["mode"], s["scope"], s["recorded"], s["passed"]) == ("recorded", "integration", "pytest -m integration", 1)
    assert "- tests integration passed=1 failed=0 skipped=0 seconds=0 recorded" in ledger(tmp_path)
    assert not (tmp_path / ".superlite" / "test-summary-full.json").exists()


def test_record_scope_defaults_to_external(tmp_path):
    assert rt(tmp_path, "--record", "--passed", "3", "--command", "x.sh").returncode == 0
    assert (summary(tmp_path)["mode"], summary(tmp_path)["scope"]) == ("recorded", "external")
    assert "- tests external passed=3 failed=0 skipped=0 seconds=0 recorded" in ledger(tmp_path)


def test_record_refuses_a_full_fast_or_bad_scope(tmp_path):
    for bad in ("full", "fast", "two words", "a-b", ""):
        cp = rt(tmp_path, "--record", "--passed", "1", "--scope", bad, "--command", "x.sh")
        assert cp.returncode == 2 and "--scope must be one word other than full or fast" in cp.stderr, (bad, cp.both)
    assert not (tmp_path / ".superlite" / "test-summary.json").exists()


def test_scope_without_record_exits_2(tmp_path):
    cp = rt(tmp_path, "--scope", "integration")
    assert cp.returncode == 2 and "run_tests: --scope needs --record" in cp.stderr


def test_write_summary_copies_only_a_foreground_full_result(tmp_path):
    c = {"passed": 2, "failed": 0, "skipped": 0, "skipped_tests": []}
    copy = tmp_path / "test-summary-full.json"
    run_tests.write_summary(tmp_path / "test-summary.json", "full", c, [], 1.0)
    assert json.loads(copy.read_text(encoding="utf-8"))["passed"] == 2
    run_tests.write_summary(tmp_path / "test-summary.json", "full", c, [], 1.0, error="boom")
    assert "error" not in json.loads(copy.read_text(encoding="utf-8"))
    run_tests.write_summary(tmp_path / "test-summary.json", "fast", {**c, "passed": 5}, [], 1.0)
    assert json.loads(copy.read_text(encoding="utf-8"))["passed"] == 2
    run_tests.write_summary(tmp_path / "test-summary-20261112T101010-1-abcdef.json", "full", c, [], 1.0)
    assert sorted(p.name for p in tmp_path.glob("*-full.json")) == ["test-summary-full.json"]


def test_a_later_fast_run_keeps_the_full_copy(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    assert rt(tmp_path, "--full").returncode == 0
    full = summary(tmp_path, "test-summary-full.json")
    assert (full["mode"], full["passed"]) == ("full", 1)
    assert rt(tmp_path, "--fast", "tests/test_a.py").returncode == 0
    assert summary(tmp_path)["mode"] == "fast" and summary(tmp_path, "test-summary-full.json") == full


def marker_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    t = tmp_path / "tests"
    t.mkdir()
    (t / "test_i.py").write_text("import pytest\n\npytestmark = pytest.mark.integration\n\n\ndef test_i():\n    assert True\n", encoding="utf-8")
    (t / "test_mixed.py").write_text("import pytest\n\n\n@pytest.mark.integration\ndef test_i():\n    assert True\n\n\n"
                                     "def test_u():\n    assert True\n", encoding="utf-8")
    (t / "test_u.py").write_text("def test_u():\n    assert True\n", encoding="utf-8")
    return tmp_path


def test_file_markers_reads_decorators_and_pytestmark(tmp_path):
    p = marker_project(tmp_path)
    assert run_tests.file_markers(p / "tests" / "test_i.py") == {"integration"}
    assert run_tests.file_markers(p / "tests" / "test_mixed.py") == {"integration"}
    assert run_tests.file_markers(p / "tests" / "test_u.py") == set()
    (p / "bad.py").write_text("def (:\n", encoding="utf-8")
    assert run_tests.file_markers(p / "bad.py") == set() and run_tests.file_markers(p / "none.py") == set()


def test_honoured_marker_expression(tmp_path):
    p = marker_project(tmp_path)
    assert run_tests.honoured_marker(["tests/test_i.py::test_i"], p) == (
        "integration or (not integration)",
        "run_tests: tests/test_i.py is marked integration, which addopts -m 'not integration' in pyproject.toml deselects; "
        "running with -m 'integration or (not integration)'")
    assert run_tests.honoured_marker(["tests/test_u.py"], p) is None
    assert run_tests.honoured_marker(["tests"], p) is None
    (p / "tests" / "test_s.py").write_text("import pytest\n\n\n@pytest.mark.slow\n@pytest.mark.integration\ndef test_s():\n    pass\n", encoding="utf-8")
    (p / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = \"-m 'not integration and not slow'\"\n", encoding="utf-8")
    assert run_tests.honoured_marker(["tests/test_s.py"], p)[0] == "integration or slow or (not integration and not slow)"
    (p / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers = [\"integration\"]\n", encoding="utf-8")
    assert run_tests.honoured_marker(["tests/test_i.py"], p) is None


def test_fast_run_of_an_integration_file_runs_its_tests(tmp_path):
    p = marker_project(tmp_path)
    cp = rt(p, "--fast", "tests/test_mixed.py")
    assert cp.returncode == 0, cp.both
    s = summary(p)
    assert (s["mode"], s["passed"], s["failed"]) == ("fast", 2, 0)
    assert "running with -m 'integration or (not integration)'" in cp.stderr


def test_an_explicit_marker_wins(tmp_path):
    p = marker_project(tmp_path)
    cp = rt(p, "--fast", "tests/test_mixed.py", "-m", "not integration")
    assert cp.returncode == 0, cp.both
    assert summary(p)["passed"] == 1 and "running with -m" not in cp.stderr


def test_file_markers_counts_other_mark_spellings(tmp_path):
    f = tmp_path / "test_m.py"
    f.write_text("from pytest import mark\nimport pytest as pt\n\n\n@mark.slow\n@pt.mark.integration\ndef test_m():\n    pass\n", encoding="utf-8")
    assert run_tests.file_markers(f) == {"slow", "integration"}


def test_bad_scope_message_names_the_value(tmp_path):
    cp = rt(tmp_path, "--record", "--passed", "1", "--scope", "full", "--command", "x.sh")
    assert cp.returncode == 2 and "(a recorded run never counts as the full run): full" in cp.stderr


def test_write_summary_copies_any_non_run_file_name(tmp_path):
    c = {"passed": 2, "failed": 0, "skipped": 0, "skipped_tests": []}
    run_tests.write_summary(tmp_path / "mine.json", "full", c, [], 1.0)
    assert (tmp_path / "mine-full.json").is_file()
    run_tests.write_summary(tmp_path / "mine-full.json", "full", c, [], 1.0)
    assert not (tmp_path / "mine-full-full.json").exists()


def test_fast_marker_reaches_a_pytest_test_cmd_json(tmp_path):
    p = marker_project(tmp_path)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "other", "test": "pytest -q"}), encoding="utf-8")
    cp = rt(p, "--fast", "tests/test_mixed.py")
    assert "running with -m 'integration or (not integration)'" in cp.stderr, cp.both
