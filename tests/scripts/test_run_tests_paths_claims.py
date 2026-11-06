"""run_tests: a missing --fast path is a usage error (#235), claimed files reach the --task tree (#239), a no-count run is a stop (#240)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS, make_plan
from test_run_tests_plan_fallback import OUT, git, setup, summary

RUN_TESTS = SCRIPTS / "run_tests.py"
COMMIT_TASK = SCRIPTS / "commit_task.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests as rt  # noqa: E402


def go(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def pyproj(tmp_path):
    root = tmp_path.resolve() / "proj"
    (root / ".superlite").mkdir(parents=True)
    (root / "sub").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    return root


def incidents(root):
    p = root / ".superlite" / "incidents.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_missing_fast_paths_example(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert rt.missing_fast_paths(["tests/test_a.py::test_x[1]", "tests/nope.py"]) == ["tests/nope.py"]


def test_missing_fast_path_is_a_usage_error(tmp_path):
    root = pyproj(tmp_path)
    cp = go(root / "sub", "--fast", "tests/test_a.py")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "run_tests: test path not found: sub/tests/test_a.py" in cp.stderr
    assert f"cwd {root}/sub" in cp.stderr
    assert f"root {root}" in cp.stderr
    assert not [r for r in incidents(root) if r.get("kind") == "no-result"]
    assert summary(root)["error"].startswith("test path not found")


def test_node_suffix_is_stripped(tmp_path):
    root = pyproj(tmp_path)
    cp = go(root, "--fast", "tests/test_a.py::test_a")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["1", "0", "0"]


def test_background_parent_refuses_missing_path(tmp_path):
    root = pyproj(tmp_path)
    cp = go(root, "--fast", "tests/nope.py", "--background")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "summary:" not in cp.stdout
    assert not (root / ".superlite" / "test-summary.latest").exists()


def two_tasks(tmp_path):
    setup(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("base", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "b")
    return make_plan(tmp_path / "docs" / "plans", [{"id": "T1", "owns": "src/a.txt"}, {"id": "T2", "owns": "src/b.txt"}], name="p.md")


def fast_t1(tmp_path, plan):
    cp = go(tmp_path, "--fast", "src/a.txt", "--task", "T1", "--plan", str(plan))
    assert cp.returncode == 0, cp.stdout + cp.stderr
    return tmp_path / ".superlite" / "trees" / "T1"


def test_claimed_file_reaches_the_tree(tmp_path):
    plan = two_tasks(tmp_path)
    cp = subprocess.run([sys.executable, str(COMMIT_TASK), "T1", "--claim", "src/b.txt", "--ruling", "x", "--plan", str(plan),
                         "--ledger", str(tmp_path / ".superlite" / "progress.md")],
                        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    (tmp_path / "src" / "b.txt").write_text("new", encoding="utf-8")
    tree = fast_t1(tmp_path, plan)
    assert (tree / "src" / "b.txt").read_text(encoding="utf-8") == "new"


def test_also_dir_entry_reaches_the_tree(tmp_path):
    plan = two_tasks(tmp_path)
    with (tmp_path / ".superlite" / "progress.md").open("a", encoding="utf-8") as f:
        f.write("- Ruling: T1 also commits src/c/ - why\n")
    (tmp_path / "src" / "c").mkdir()
    (tmp_path / "src" / "c" / "x.txt").write_text("c", encoding="utf-8")
    tree = fast_t1(tmp_path, plan)
    assert (tree / "src" / "c" / "x.txt").read_text(encoding="utf-8") == "c"


def test_unclaimed_file_stays_at_base(tmp_path):
    plan = two_tasks(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("edited", encoding="utf-8")
    tree = fast_t1(tmp_path, plan)
    assert (tree / "src" / "b.txt").read_text(encoding="utf-8") == "base"


def swift_proj(tmp_path, printed, code=0):
    (tmp_path / ".superlite").mkdir()
    cmd = f'{sys.executable} -c "import sys; print({printed!r}); sys.exit({code})"'
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd}), encoding="utf-8")


def test_no_count_run_is_a_no_result_stop(tmp_path):
    swift_proj(tmp_path, "Executed 0 tests, with 0 failures (0 unexpected) in 0.0 (0.0) seconds")
    cp = go(tmp_path, "--fast", "Tests/AppTests/FooTests.swift")
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["0", "0", "0"]
    err = summary(tmp_path)["error"]
    assert err.startswith("no tests ran:") and "Executed 0 tests" in err
    assert len([r for r in incidents(tmp_path) if r.get("kind") == "no-result"]) == 1


def test_counted_run_unchanged(tmp_path):
    swift_proj(tmp_path, OUT)
    cp = go(tmp_path, "--fast", "Tests/AppTests/FooTests.swift")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["2", "0", "0"]


def test_green_exit_without_count_stays_green(tmp_path):
    swift_proj(tmp_path, "Build succeeded")
    cp = go(tmp_path, "--fast", "Tests/AppTests/FooTests.swift")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["1", "0", "0"]
