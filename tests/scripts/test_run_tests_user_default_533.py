"""#533: run_tests runs the user-level default through a wrapper (placement CLI) and parses the wrapped output."""
from __future__ import annotations

import json
import shlex
import subprocess
import sys

from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
PY = shlex.quote(sys.executable)
WRAP = """import subprocess, sys
open("placed.txt", "w").write(" ".join(sys.argv[1:]))
sys.stdout.write("placement: host-a\\n"); sys.stdout.flush()
sys.exit(subprocess.call(sys.argv[1:]))
"""
FAKE_XCODE = """import sys
open("placed.txt", "w").write(" ".join(sys.argv[2:]))
sys.stdout.write("placement: host-b\\n" + open(sys.argv[1]).read())
sys.exit(65)
"""
MIXED = "final class AlphaTests: XCTestCase {\n  func testA() {}\n}\nclass BetaTests: XCTestCase {\n  func testB() {}\n}\n"


def user(tmp_path, monkeypatch, data):
    p = tmp_path / "home-config" / "test-cmd.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(p))
    return p


def summary(root):
    return json.loads((root / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True, text=True).stdout


def test_wrapped_python_full_and_fast(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "pyproject.toml").write_text("[project]\nname = 'p'\n", encoding="utf-8")
    (proj / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    (proj / "wrap.py").write_text(WRAP, encoding="utf-8")
    base = f"{PY} wrap.py {PY} -m pytest -q -p no:cacheprovider"
    user(tmp_path, monkeypatch, {"python": {"test": base + " tests", "test_file": base + " {files}"}})
    cp = run(RUN_TESTS, "--full", cwd=proj)
    assert cp.returncode == 0, cp.both
    assert summary(proj)["passed"] == 1 and "pytest" in (proj / "placed.txt").read_text()
    cp = run(RUN_TESTS, "--fast", "tests/test_a.py", cwd=proj)
    assert cp.returncode == 0, cp.both
    assert (proj / "placed.txt").read_text().endswith("tests/test_a.py")


def test_wrapped_xcodebuild_output_is_parsed(tmp_path, monkeypatch):
    proj = tmp_path / "kit"
    (proj / "Tests" / "KitTests").mkdir(parents=True)
    (proj / "Package.swift").write_text('let package = Package(name: "Kit", targets: [.testTarget(name: "KitTests")])\n', encoding="utf-8")
    (proj / "Tests" / "KitTests" / "Mixed.swift").write_text(MIXED, encoding="utf-8")
    (proj / "fake.py").write_text(FAKE_XCODE, encoding="utf-8")
    out = shlex.quote(str(FIXTURES / "xcode" / "xctest_two_suites.txt"))
    user(tmp_path, monkeypatch, {"swift": {"test": f"{PY} fake.py {out}", "test_file": f"{PY} fake.py {out} {{only_testing}}"}})
    cp = run(RUN_TESTS, "--fast", "Tests/KitTests/Mixed.swift", cwd=proj)
    s = summary(proj)
    assert cp.returncode == 1 and (s["passed"], s["failed"]) == (4, 1), cp.both
    assert (proj / "placed.txt").read_text() == "-only-testing:KitTests/AlphaTests -only-testing:KitTests/BetaTests"


def test_user_template_notes_get_the_run_tests_prefix(tmp_path, monkeypatch):
    proj = tmp_path / "kit"
    (proj / "Tests" / "KitTests").mkdir(parents=True)
    (proj / "Package.swift").write_text('let package = Package(name: "Kit", targets: [.testTarget(name: "KitTests")])\n', encoding="utf-8")
    (proj / "Tests" / "KitTests" / "Helpers.swift").write_text("import XCTest\n", encoding="utf-8")
    user(tmp_path, monkeypatch, {"swift": {"test": f"{PY} -c pass", "test_file": f"{PY} -c pass {{only_testing}}"}})
    cp = run(RUN_TESTS, "--fast", "Tests/KitTests/Helpers.swift", cwd=proj)
    assert "run_tests: Tests/KitTests/Helpers.swift declares no test suite" in cp.err


PLAN = "# P\n\n## Section A\n\n### T1 first\n**Owns:** src/a.py\n**Produces:** x\n\n### T2 second\n**Owns:** src/b.py\n**Produces:** y\n"


def test_task_tree_runs_the_user_command(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    git(repo, "init", "-q")
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_text(".superlite/\n")
    (repo / "Package.swift").write_text("// swift-tools-version:5.9\n")
    (repo / "src" / "a.py").write_text("A = 1\n")
    (repo / "src" / "b.py").write_text("B = 1\n")
    (repo / "plan.md").write_text(PLAN)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    (repo / "src" / "a.py").write_text("A = (\n")  # a sibling's half edit stays out of T2's tree
    cmd = (f"{PY} -c \"import src.a, src.b; open('ran-here.txt','w').write('x'); "
           "print('Executed 1 test, with 0 failures (0 unexpected) in 0.001 (0.002) seconds')\"")
    user(tmp_path, monkeypatch, {"swift": {"test": cmd, "test_file": cmd}})
    monkeypatch.chdir(repo)
    rc = run_tests.main(["--fast", "src/b.py", "--task", "T2", "--plan", "plan.md", "--summary", ".superlite/test-summary.json",
                         "--log", ".superlite/incidents.jsonl", "--ledger", ".superlite/progress.md"])
    assert rc == 0
    assert (repo / ".superlite" / "trees" / "T2" / "ran-here.txt").exists() and not (repo / "ran-here.txt").exists()
    assert summary(repo)["passed"] == 1


def test_placeholder_refusal_names_the_user_entry(tmp_path, monkeypatch):
    proj = tmp_path / "py"
    (proj / "tests").mkdir(parents=True)
    git(proj, "init", "-q")
    (proj / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (proj / "tests" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    p = user(tmp_path, monkeypatch, {"python": {"test": "pytest", "test_file": "pytest {only_testing}"}})
    cp = run(RUN_TESTS, "--fast", "tests/test_a.py", cwd=proj)
    assert cp.returncode == 2, cp.both
    assert 'the "python" entry of ' in cp.err and "delete that entry" in cp.err
    spec = {"python": False, "source": "user", "language": "python", "origin": str(p), "command": "pytest"}
    assert run_tests.placeholder_line(proj, spec) is not None
