import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


def node_project(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}, "devDependencies": {"vitest": "1"}}))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.test.ts").write_text("")


def config(tmp_path, cfg, rel):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg))
    f = tmp_path / rel
    f.parent.mkdir(parents=True)
    f.write_text("")


def test_node_fast_no_only_testing_warning(tmp_path, capsys):
    node_project(tmp_path)
    spec = testcmd.resolve(tmp_path, ["src/a.test.ts"])
    assert capsys.readouterr().err == ""
    assert "src/a.test.ts" in spec["command"]


def test_cli_fast_node_stderr_clean(tmp_path):
    node_project(tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPTS / "testcmd.py"), "--root", str(tmp_path), "--fast", "src/a.test.ts"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "-only-testing" not in r.stderr
    assert "declares no test suite" not in r.stderr


def test_names_template_no_warning(tmp_path, capsys):
    config(tmp_path, {"language": "swift", "test": "swift test", "test_file": "swift test --filter {names}"},
           "Tests/AppTests/FooTests.swift")
    spec = testcmd.resolve(tmp_path, ["Tests/AppTests/FooTests.swift"])
    assert spec["command"] == "swift test --filter FooTests"
    assert capsys.readouterr().err == ""


def test_only_testing_template_still_warns(tmp_path, capsys):
    config(tmp_path, {"language": "swift", "test": "xcodebuild test -scheme X {only_testing}"},
           "Tests/AppTests/Empty.swift")
    spec = testcmd.resolve(tmp_path, ["Tests/AppTests/Empty.swift"])
    assert spec["command"] == "xcodebuild test -scheme X -only-testing:AppTests"
    assert "testcmd: Tests/AppTests/Empty.swift declares no test suite; using -only-testing:AppTests" in capsys.readouterr().err


def test_full_run_blanks_only_testing(tmp_path):
    config(tmp_path, {"language": "swift", "test": "xcodebuild test -scheme X {only_testing}"},
           "Tests/AppTests/Empty.swift")
    command = testcmd.resolve(tmp_path)["command"]
    assert "{only_testing}" not in command
    assert command == "xcodebuild test -scheme X "
