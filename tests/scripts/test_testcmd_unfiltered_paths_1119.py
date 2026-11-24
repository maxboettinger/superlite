"""testcmd.unfiltered_paths names the paths a --fast resolve would widen to the unfiltered suite (#1119)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import testcmd  # noqa: E402
from test_testcmd_swift_targets_431 import config, project  # noqa: E402

XC = "xcodebuild test -scheme App {only_testing}"


def xcode(tmp_path):
    root = project(tmp_path)
    config(root, {"language": "swift", "test": XC, "test_file": XC})
    return root


def test_only_testing_keeps_mapped_drops_unmapped(tmp_path):
    root = xcode(tmp_path)
    assert testcmd.unfiltered_paths(root, ["Tests/Unit/FooTests.swift", "Support/Shared.swift", "App/Model.swift"]) == ["App/Model.swift"]


def test_names_drops_suite_less_source(tmp_path):
    (tmp_path / "Package.swift").write_text('.target(name: "App")\n.testTarget(name: "AppTests")\n')
    (tmp_path / "Sources" / "App").mkdir(parents=True)
    (tmp_path / "Sources" / "App" / "Model.swift").write_text("struct Model {}\n")
    (tmp_path / "Tests" / "AppTests").mkdir(parents=True)
    (tmp_path / "Tests" / "AppTests" / "FooTests.swift").write_text("import XCTest\nfinal class FooTests: XCTestCase {}\n")
    config(tmp_path, {"language": "swift", "test": "swift test --filter {names}", "test_file": "swift test --filter {names}"})
    assert testcmd.unfiltered_paths(tmp_path, ["Sources/App/Model.swift"]) == ["Sources/App/Model.swift"]
    assert testcmd.unfiltered_paths(tmp_path, ["Tests/AppTests/FooTests.swift"]) == []


def test_files_template_drops_nothing(tmp_path):
    config(tmp_path, {"language": "python", "test": "pytest", "test_file": "pytest {files}"})
    assert testcmd.unfiltered_paths(tmp_path, ["tests/test_a.py"]) == []


def test_no_config_drops_nothing(tmp_path):
    assert testcmd.unfiltered_paths(tmp_path, ["a.swift"]) == []


def test_order_and_duplicates_kept(tmp_path):
    root = xcode(tmp_path)
    assert testcmd.unfiltered_paths(root, ["b.swift", "a.swift", "b.swift"]) == ["b.swift", "a.swift", "b.swift"]


def test_prints_nothing(tmp_path, capsys):
    root = xcode(tmp_path)
    testcmd.unfiltered_paths(root, ["Tests/Unit/FooTests.swift", "App/Model.swift"])
    out = capsys.readouterr()
    assert out.err == "" and out.out == ""


def test_resolve_unchanged(tmp_path, capsys):
    root = xcode(tmp_path)
    assert testcmd.resolve(root, ["App/ContentView.swift"])["command"] == "xcodebuild test -scheme App "
    assert "App/ContentView.swift is not in a test target; running the unfiltered test command" in capsys.readouterr().err
