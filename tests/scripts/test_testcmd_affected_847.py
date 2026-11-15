"""#847: testcmd.select_affected picks the tests a change touches, on a Python and a Swift package fixture."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

PY = {
    "pyproject.toml": '[project]\nname = "calc"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    "src/calc/adder.py": "def add(a, b):\n    return a + b\n",
    "src/calc/fmt.py": "def show(x):\n    return str(x)\n",
    "src/calc/orphan.py": "X = 1\n",
    "tests/conftest.py": "",
    "tests/fixtures/sample.txt": "1 2\n",
    "tests/test_adder.py": "from calc.adder import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    "tests/test_report.py": "from calc import fmt\n\n\ndef test_show():\n    assert fmt.show(1) == '1'\n",
    "tests/test_misc.py": "def test_true():\n    assert True\n",
    "bench/test_speed.py": "from calc.adder import add\n\n\ndef test_speed():\n    assert add(0, 0) == 0\n",
}
SWIFT_PKG = {
    "Package.swift": ('// swift-tools-version:5.9\nimport PackageDescription\n\nlet package = Package(\n    name: "Calc",\n'
                      '    targets: [\n        .target(name: "Calc"),\n        .testTarget(name: "CalcTests", dependencies: ["Calc"]),\n'
                      '        .target(name: "Fmt"),\n        .testTarget(name: "FmtTests", dependencies: ["Fmt"]),\n    ]\n)\n'),
    "Sources/Calc/Adder.swift": "public func add(_ a: Int, _ b: Int) -> Int { a + b }\n",
    "Sources/Calc/Parser.swift": "public struct Parser { public init() {} }\n",
    "Sources/Fmt/Pretty.swift": "public func pretty(_ x: Int) -> String { String(x) }\n",
    "Tests/CalcTests/AdderTests.swift": ("import XCTest\n@testable import Calc\n\nfinal class AdderTests: XCTestCase {\n"
                                         "    func testAdd() { XCTAssertEqual(add(1, 2), 3) }\n}\n"),
    "Tests/CalcTests/ParserTests.swift": ("import XCTest\n@testable import Calc\n\nfinal class ParserTests: XCTestCase {\n"
                                          "    func testInit() { _ = Parser() }\n}\n"),
    "Tests/FmtTests/PrettyTests.swift": ("import XCTest\n@testable import Fmt\n\nfinal class PrettyTests: XCTestCase {\n"
                                         "    func testPretty() { XCTAssertEqual(pretty(1), \"1\") }\n}\n"),
}
SWIFT_CFG = {"language": "swift", "test": "swift test"}


def make(tmp_path, files, cfg=None):
    root = tmp_path / "repo"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    if cfg is not None:
        (root / ".superlite").mkdir(exist_ok=True)
        (root / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    return root


def test_changed_test_file_selects_itself(tmp_path):
    root = make(tmp_path, PY)
    assert testcmd.select_affected(str(root), ["tests/test_misc.py"]) == {
        "full": False, "selected": ["tests/test_misc.py"], "reasons": {"tests/test_misc.py": "changed"}, "untested": []}


def test_a_deleted_test_is_neither_selected_nor_untested(tmp_path):
    root = make(tmp_path, PY)
    assert testcmd.select_affected(str(root), ["tests/test_gone.py"]) == {
        "full": False, "selected": [], "reasons": {}, "untested": []}


def test_source_selects_its_test_by_name_and_testpaths_drop_bench(tmp_path):
    root = make(tmp_path, PY)
    assert testcmd.select_affected(str(root), ["src/calc/adder.py"]) == {
        "full": False, "selected": ["tests/test_adder.py"], "reasons": {"tests/test_adder.py": "name"}, "untested": []}


def test_source_selects_tests_that_mention_its_module(tmp_path):
    root = make(tmp_path, PY)
    r = testcmd.select_affected(str(root), ["src/calc/fmt.py"])
    assert r["selected"] == ["tests/test_report.py"]
    assert r["reasons"] == {"tests/test_report.py": "mention"}


def test_related_template_maps_a_source(tmp_path):
    files = {**PY, "tests/test_orphan_extra.py": "def test_x():\n    pass\n"}
    root = make(tmp_path, files, cfg={"related": "tests/test_{src}_extra.py"})
    assert testcmd.select_affected(str(root), ["src/calc/orphan.py"]) == {
        "full": False, "selected": ["tests/test_orphan_extra.py"],
        "reasons": {"tests/test_orphan_extra.py": "related"}, "untested": []}


def test_untested_lists_changed_files_no_test_covers(tmp_path):
    root = make(tmp_path, {**PY, "README.md": "# calc\n"})
    r = testcmd.select_affected(str(root), ["src/calc/orphan.py", "README.md", "tests/test_misc.py", "src/calc/orphan.py"])
    assert r["selected"] == ["tests/test_misc.py"]
    assert r["untested"] == ["src/calc/orphan.py", "README.md"]


def test_shared_setup_selects_everything(tmp_path):
    root = make(tmp_path, PY)
    for p in ("tests/conftest.py", "pyproject.toml", "tests/fixtures/sample.txt", "uv.lock", "Package.swift"):
        r = testcmd.select_affected(str(root), ["src/calc/adder.py", p])
        assert r == {"full": True, "trigger": p, "selected": [], "reasons": {}, "untested": []}, p


def test_the_test_command_and_its_config_select_everything(tmp_path):
    files = {**PY, "scripts/run-tests.sh": "pytest -q\n"}
    root = make(tmp_path, files, cfg={"language": "python", "test": "bash scripts/run-tests.sh"})
    for p in ("scripts/run-tests.sh", ".superlite/test-cmd.json"):
        r = testcmd.select_affected(str(root), ["src/calc/adder.py", p])
        assert r == {"full": True, "trigger": p, "selected": [], "reasons": {}, "untested": []}, p


def test_map_file_adds_tests_and_full_globs(tmp_path):
    root = make(tmp_path, PY)
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-map.json").write_text(json.dumps(
        {"src/calc/orphan.py": ["tests/test_misc.py"], "docs/*.md": ["tests/test_r*.py"], "_full": ["config/*.yml"]}),
        encoding="utf-8")
    assert testcmd.select_affected(str(root), ["src/calc/orphan.py", "docs/guide.md"]) == {
        "full": False, "selected": ["tests/test_misc.py", "tests/test_report.py"],
        "reasons": {"tests/test_misc.py": "map", "tests/test_report.py": "map"}, "untested": []}
    r = testcmd.select_affected(str(root), ["config/app.yml"])
    assert r["full"] is True and r["trigger"] == "config/app.yml"


def test_pytest_testpaths_reads_each_config(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n    more\n", encoding="utf-8")
    assert testcmd.pytest_testpaths(str(tmp_path)) == ["tests", "more"]
    (tmp_path / "pytest.ini").unlink()
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n', encoding="utf-8")
    assert testcmd.pytest_testpaths(str(tmp_path)) == ["tests"]
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert testcmd.pytest_testpaths(str(tmp_path)) == []


def test_swift_source_selects_its_module_test_target(tmp_path):
    root = make(tmp_path, SWIFT_PKG, cfg=SWIFT_CFG)
    assert testcmd.select_affected(str(root), ["Sources/Calc/Parser.swift"]) == {
        "full": False,
        "selected": ["Tests/CalcTests/AdderTests.swift", "Tests/CalcTests/ParserTests.swift"],
        "reasons": {"Tests/CalcTests/AdderTests.swift": "module", "Tests/CalcTests/ParserTests.swift": "name"},
        "untested": []}


def test_swift_changed_test_and_manifest(tmp_path):
    root = make(tmp_path, SWIFT_PKG, cfg=SWIFT_CFG)
    r = testcmd.select_affected(str(root), ["Tests/FmtTests/PrettyTests.swift"])
    assert r["selected"] == ["Tests/FmtTests/PrettyTests.swift"]
    assert r["reasons"] == {"Tests/FmtTests/PrettyTests.swift": "changed"}
    assert testcmd.select_affected(str(root), ["Package.swift"])["trigger"] == "Package.swift"


def test_swift_source_outside_every_test_target_is_untested(tmp_path):
    root = make(tmp_path, {**SWIFT_PKG, "Sources/Tool/Runner.swift": "struct Runner {}\n"}, cfg=SWIFT_CFG)
    assert testcmd.select_affected(str(root), ["Sources/Tool/Runner.swift"]) == {
        "full": False, "selected": [], "reasons": {}, "untested": ["Sources/Tool/Runner.swift"]}


def test_changed_test_file_selects_tests_that_mention_it(tmp_path):
    files = {**PY, "tests/test_user.py": "from test_misc import helper\n\n\ndef test_u():\n    pass\n"}
    root = make(tmp_path, files)
    r = testcmd.select_affected(str(root), ["tests/test_misc.py"])
    assert r["reasons"] == {"tests/test_misc.py": "changed", "tests/test_user.py": "mention"}


def test_a_deleted_source_is_never_untested_but_still_selects_by_name(tmp_path):
    root = make(tmp_path, PY)
    assert testcmd.select_affected(str(root), ["src/calc/gone.py"]) == {
        "full": False, "selected": [], "reasons": {}, "untested": []}
    (root / "src/calc/adder.py").unlink()
    assert testcmd.select_affected(str(root), ["src/calc/adder.py"])["selected"] == ["tests/test_adder.py"]


def test_fixture_project_tests_are_never_selected(tmp_path):
    files = dict(PY, **{"tests/fixtures/proj/tests/test_adder.py": "from calc.adder import add\n\n\ndef test_x():\n    assert False\n"})
    root = make(tmp_path, files)
    assert testcmd.select_affected(str(root), ["src/calc/adder.py"])["selected"] == ["tests/test_adder.py"]


def test_without_testpaths_only_tests_folder_is_selected(tmp_path):
    body = "from calc.adder import add\n"
    root = make(tmp_path, {"pyproject.toml": '[project]\nname = "calc"\n', "src/calc/adder.py": "def add(a, b):\n    return a + b\n",
                           "tests/test_adder.py": body, "bench/test_speed.py": body})
    assert testcmd.select_affected(str(root), ["src/calc/adder.py"])["selected"] == ["tests/test_adder.py"]


def test_without_testpaths_and_tests_folder_bench_is_ignored(tmp_path):
    body = "from calc.adder import add\n"
    root = make(tmp_path, {"pyproject.toml": '[project]\nname = "calc"\n', "src/calc/adder.py": "def add(a, b):\n    return a + b\n",
                           "test_adder.py": body, "bench/test_speed.py": body})
    assert testcmd.select_affected(str(root), ["src/calc/adder.py"])["selected"] == ["test_adder.py"]


def test_dot_slash_changed_paths_are_normalised(tmp_path):
    root = make(tmp_path, PY)
    assert testcmd.select_affected(str(root), ["./tests/test_misc.py"])["selected"] == ["tests/test_misc.py"]
    assert testcmd.select_affected(str(root), ["./.superlite/test-cmd.json"])["trigger"] == ".superlite/test-cmd.json"
