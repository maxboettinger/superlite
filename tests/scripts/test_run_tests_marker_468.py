"""run_tests -m EXPR passes a pytest marker; a pytest exit 5 names its cause (#468)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)
PYPROJECT = "[tool.pytest.ini_options]\naddopts = \"-m 'not integration'\"\nmarkers = [\"integration\"]\n"


def run(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "tests" / "integration").mkdir(parents=True)
    (tmp_path / "tests" / "integration" / "test_i.py").write_text(
        "import pytest\n\n@pytest.mark.integration\ndef test_i():\n    assert True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_u.py").write_text("def test_u():\n    assert True\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    return tmp_path


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def rows(tmp_path):
    f = tmp_path / ".superlite" / "incidents.jsonl"
    if not f.exists():
        return []
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_with_marker_cases():
    assert run_tests.with_marker("uv run pytest -q", "not slow") == "uv run pytest -q -m 'not slow'"
    assert run_tests.with_marker("python -m pytest", "integration") == "python -m pytest -m integration"
    assert run_tests.with_marker("go test ./...", "integration") is None
    assert run_tests.with_marker("/opt/venv/bin/py.test", "a or b") == "/opt/venv/bin/py.test -m 'a or b'"


def test_addopts_marker_sources(tmp_path):
    p = tmp_path / "a"
    p.mkdir()
    assert run_tests.addopts_marker(p) is None
    (p / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = \"-q -m 'not integration'\"\n", encoding="utf-8")
    assert run_tests.addopts_marker(p) == ("not integration", "pyproject.toml")
    q = tmp_path / "b"
    q.mkdir()
    (q / "pytest.ini").write_text("[pytest]\naddopts = -mslow\n", encoding="utf-8")
    assert run_tests.addopts_marker(q) == ("slow", "pytest.ini")
    r = tmp_path / "c"
    r.mkdir()
    (r / "setup.cfg").write_text("[tool:pytest]\naddopts = -m \"not slow\"\n", encoding="utf-8")
    assert run_tests.addopts_marker(r) == ("not slow", "setup.cfg")
    s = tmp_path / "d"
    s.mkdir()
    (s / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = [\"-m\", \"fast\"]\n", encoding="utf-8")
    assert run_tests.addopts_marker(s) == ("fast", "pyproject.toml")
    t = tmp_path / "e"
    t.mkdir()
    (t / "pytest.ini").write_text("[pytest]\nmarkers = x\n", encoding="utf-8")
    (t / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = \"-m slow\"\n", encoding="utf-8")
    assert run_tests.addopts_marker(t) is None
    u = tmp_path / "f"
    u.mkdir()
    (u / "pyproject.toml").write_text("[tool.pytest.ini_options\naddopts = = =\n", encoding="utf-8")
    assert run_tests.addopts_marker(u) is None


def test_nothing_collected_cases(tmp_path):
    p = tmp_path / "a"
    p.mkdir()
    q = tmp_path / "b"
    q.mkdir()
    (q / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = \"-q -m 'not integration'\"\n", encoding="utf-8")
    nc = run_tests.nothing_collected
    assert nc("4 deselected in 0.01s", ["tests/integration"], None, q) == (
        "all 4 collected tests deselected by addopts -m 'not integration' in pyproject.toml; pass run_tests -m EXPR to select them")
    assert nc("4 deselected in 0.01s", [], "slow", p) == "all 4 collected tests deselected by -m 'slow'"
    assert nc("4 deselected in 0.01s", [], None, p) == "all 4 collected tests deselected by a -m or -k filter"
    assert nc("no tests ran in 0.01s", ["src/app", "src/lib"], None, p) == "no tests found in src/app, src/lib"
    assert nc("no tests ran in 0.01s", [], None, p) == "no tests found (check testpaths and python_files in the pytest config)"


def test_marker_overrides_addopts(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--fast", "tests/integration", "-m", "integration")
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert s["passed"] == 1 and s["mode"] == "fast"
    last = (tmp_path / ".superlite" / "ledger.md").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert last.startswith("- tests fast passed=1")


def test_marker_only_run_is_fast(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "-m", "integration")
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert s["mode"] == "fast" and s["passed"] == 1
    assert "unit layer stamped" not in cp.stderr
    assert not [r for r in rows(tmp_path) if r.get("kind") == "verified"]


def test_marker_with_space_is_one_arg(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "-m", "not integration")
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_exit5_names_addopts_marker(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--fast", "tests/integration")
    assert cp.returncode == 1, cp.both
    s = summary(tmp_path)
    assert s["error"].startswith("pytest collected nothing (exit 5): all 1 collected tests deselected by addopts -m 'not integration' in pyproject.toml")
    assert s["failed"] == 1
    (inc,) = [r for r in rows(tmp_path) if r.get("kind") == "no-result"]
    assert inc["target"].startswith("nothing collected: all 1 collected tests deselected")
    assert "exit 5 from " in inc["target"]


def test_exit5_source_folder_without_tests(tmp_path):
    project(tmp_path)
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    cp = run(tmp_path, "--fast", "src/app")
    assert cp.returncode == 1, cp.both
    assert "no tests found in src/app" in summary(tmp_path)["error"]


def test_marker_refused_for_non_pytest_command(tmp_path):
    project(tmp_path)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "go", "test": "go test ./..."}), encoding="utf-8")
    cp = run(tmp_path, "-m", "integration")
    assert cp.returncode == 2, cp.both
    assert "-m EXPR selects pytest markers" in cp.stderr
    assert rows(tmp_path) == []


def test_marker_appended_to_pytest_test_cmd(tmp_path):
    project(tmp_path)
    cmd = f"{sys.executable} -m pytest -q tests"
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": cmd}), encoding="utf-8")
    cp = run(tmp_path, "-m", "integration")
    assert cp.returncode == 0, cp.both
    log = Path(summary(tmp_path)["output"]).read_text(encoding="utf-8")
    assert "-m integration" in log


def test_background_pointer_mode_fast_with_marker(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--background", "-m", "integration")
    assert cp.returncode == 0, cp.both
    ptr = json.loads((tmp_path / ".superlite" / "test-summary.latest").read_text(encoding="utf-8"))
    assert ptr["mode"] == "fast"
    wait = next(x for x in cp.stdout.splitlines() if x.startswith("wait:"))
    path = re.search(r"--wait (\S+)$", wait).group(1)
    w = subprocess.run([sys.executable, str(RUN_TESTS), "--wait", path], capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert w.returncode == 0, w.stdout + w.stderr


def test_exit3_text_unchanged(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_a():\n    import os; os._exit(3)\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    cp = run(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    assert summary(tmp_path)["error"].startswith("pytest produced no results (exit 3): ")


def test_with_marker_refuses_shell_operators_after_pytest():
    for cmd in ("pytest -q | tee log", "pytest -q|tee log", "pytest -q; echo done", "pytest -q && echo ok", "pytest -q > out.txt"):
        assert run_tests.with_marker(cmd, "x") is None, cmd
    assert run_tests.with_marker("pytest -q -k 'a|b'", "x") == "pytest -q -k 'a|b' -m x"
