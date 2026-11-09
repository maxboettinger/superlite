"""run_tests refuses a test-cmd.json {only_testing} placeholder in a project without Swift files (#373)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import testcmd  # noqa: E402

CFG = {"language": "swift", "test": "xcodebuild test -scheme X", "test_file": "xcodebuild test -scheme X {only_testing}"}
TEXT = ("test-cmd.json uses {only_testing}, the Xcode (Swift) placeholder, but this python project has no Swift files: "
        "in .superlite/test-cmd.json write the python form {files} (e.g. \"test_file\": \"python -m pytest {files}\"), "
        "or delete that file so run_tests runs pytest itself")


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def py_repo(tmp_path, git=True, marker="pyproject.toml", cfg=CFG):
    if git:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    if marker == "pyproject.toml":
        (tmp_path / marker).write_text('[project]\nname = "x"\n', encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    else:
        (tmp_path / marker).write_text("module x\n", encoding="utf-8")
    if cfg is not None:
        (tmp_path / ".superlite").mkdir()
        (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def summary_error(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))["error"]


def test_python_project_refuses_only_testing_fast(tmp_path):
    py_repo(tmp_path)
    r = rt(tmp_path, "--fast", "tests/test_a.py")
    assert r.returncode == 2
    assert "run_tests: test-cmd.json uses {only_testing}" in r.stderr and "python form {files}" in r.stderr
    assert summary_error(tmp_path) == TEXT
    assert not (tmp_path / ".superlite" / "incidents.jsonl").exists()


def test_python_project_refuses_only_testing_full(tmp_path):
    py_repo(tmp_path)
    r = rt(tmp_path, "--full")
    assert r.returncode == 2
    assert summary_error(tmp_path) == TEXT


def test_background_parent_refuses(tmp_path):
    py_repo(tmp_path)
    for args in (("--full", "--background"), ("--fast", "tests/test_a.py", "--background")):
        r = rt(tmp_path, *args)
        assert r.returncode == 2, r.stderr
        assert "summary:" not in r.stdout
        assert "run_tests: test-cmd.json uses {only_testing}" in r.stderr
        assert not list((tmp_path / ".superlite").glob("test-summary-*.json"))


def test_mixed_repo_keeps_xcode_command(tmp_path):
    py_repo(tmp_path)
    (tmp_path / "App" / "App.xcodeproj").mkdir(parents=True)
    (tmp_path / "App" / "App.xcodeproj" / "project.pbxproj").write_text("x", encoding="utf-8")
    assert run_tests.has_swift(tmp_path) is True
    assert run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path))) is None


def test_swift_source_alone_keeps_xcode_command(tmp_path):
    py_repo(tmp_path)
    (tmp_path / "Sources" / "A").mkdir(parents=True)
    (tmp_path / "Sources" / "A" / "a.swift").write_text("x", encoding="utf-8")
    assert run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path))) is None


def test_go_project_names_go_form(tmp_path):
    py_repo(tmp_path, marker="go.mod")
    text = run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path)))
    assert "this go project has no Swift files" in text
    assert '"test_file": "go test {files}"' in text


def test_markers_spec_untouched(tmp_path):
    py_repo(tmp_path, cfg=None)
    assert run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path))) is None
    other = {"language": "swift", "test": "swift test", "test_file": "swift test --filter {names}"}
    py_repo_dir = tmp_path / ".superlite"
    py_repo_dir.mkdir()
    (py_repo_dir / "test-cmd.json").write_text(json.dumps(other), encoding="utf-8")
    assert run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path))) is None


def test_not_a_git_repo_refuses_nothing(tmp_path):
    py_repo(tmp_path, git=False)
    assert run_tests.has_swift(tmp_path) is None
    assert run_tests.placeholder_line(tmp_path, testcmd.resolve(str(tmp_path))) is None
