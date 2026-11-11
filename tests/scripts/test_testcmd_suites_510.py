"""testcmd: brace-depth Swift type scanning (#510): indented suites, nested types, ranges."""
from __future__ import annotations

import sys

from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

KIT = FIXTURES / "xcode" / "kit" / "Tests" / "KitTests"


def _read(name):
    return (KIT / name).read_text()


def test_indented_suite_in_if():
    assert testcmd.swift_suites(_read("Indented.swift")) == ["HALInputCaptureTests"]


def test_indented_attribute_lines():
    t = "#if os(macOS)\n    @Suite(\"Name\")\n    @MainActor\n    struct X {\n        @Test func a() {}\n    }\n#endif\n"
    assert testcmd.swift_suites(t) == ["X"]


def test_indented_free_test():
    assert testcmd.swift_suites("#if DEBUG\n    @Test func lone() {}\n#endif\n") == ["lone()"]


def test_nested_not_listed():
    assert testcmd.swift_suites(_read("Nested.swift")) == ["Outer"]


def test_spoken_text_fixture():
    assert testcmd.swift_suites(_read("SpokenTextTests.swift")) == ["SpokenTextTests", "freeFails()"]


def test_types_nested_ranges():
    assert testcmd.swift_types("struct A {\n  struct B {\n    @Test func x() {}\n  }\n}\n") == [("A", 1, 5), ("B", 2, 4)]


def test_types_indented_in_if():
    assert testcmd.swift_types("#if os(macOS)\n    @Suite struct H {\n        @Test func c() {}\n    }\n#endif\n") == [("H", 2, 4)]


def test_types_one_line():
    assert testcmd.swift_types("struct One { @Test func a() {} }\n") == [("One", 1, 1)]


def test_types_brace_in_string():
    assert testcmd.swift_types('struct S {\n  let t = "}"\n}\n') == [("S", 1, 3)]


def test_types_unclosed():
    assert testcmd.swift_types("struct U {\n  func f() {}\n") == [("U", 1, 2)]


def test_only_testing_indented_file(tmp_path):
    (tmp_path / "Package.swift").write_text('let p = [.testTarget(name: "MediaTests")]\n')
    f = tmp_path / "Tests" / "MediaTests" / "HAL.swift"
    f.parent.mkdir(parents=True)
    f.write_text(_read("Indented.swift"))
    notes: list = []
    assert testcmd.only_testing(["Tests/MediaTests/HAL.swift"], str(tmp_path), notes) == "-only-testing:MediaTests/HALInputCaptureTests"
    assert notes == []
