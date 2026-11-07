import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

P = "import Testing\n\nstruct ParserTests {\n    let s = %s\n    @Test func parse() {}\n}\n"


def test_brace_in_multiline_string_keeps_suite():
    assert testcmd.swift_suites(P % '"""\n}\n"""') == ["ParserTests"]


def test_brace_in_block_comment_keeps_suite():
    assert testcmd.swift_suites(P % "/*\n}\n*/") == ["ParserTests"]


def test_nested_block_comment():
    assert testcmd.swift_suites(P % "/* a /* b */\n}\n*/") == ["ParserTests"]


def test_raw_multiline_string():
    assert testcmd.swift_suites(P % '#"""\n"""\n}\n"""#') == ["ParserTests"]


def test_trailing_line_comment_not_one_line_type():
    assert testcmd.swift_suites("struct ParserTests { // {}\n    @Test func parse() {}\n}\n") == ["ParserTests"]


def test_suite_inside_comment_ignored():
    t = "/*\nstruct FakeTests {\n    @Test func fake() {}\n}\n*/\nstruct RealTests {\n    @Test func real() {}\n}\n"
    assert testcmd.swift_suites(t) == ["RealTests"]


def test_free_test_inside_string_ignored():
    assert testcmd.swift_suites('let doc = """\n@Test func fake() {}\n"""\n@Test func real() {}\n') == ["real()"]


def test_attribute_string_with_brace():
    assert testcmd.swift_suites('@Suite("Parser } tests")\nstruct ParserTests {\n    @Test func parse() {}\n}\n') == ["ParserTests"]


def test_hash_directive_is_code():
    assert testcmd.swift_suites("#if DEBUG\nstruct ParserTests {\n    @Test func parse() {}\n}\n#endif\n") == ["ParserTests"]


def test_strip_keeps_shape():
    src = 'let s = "a \\"}\\" \\(f("x")) b" // note }\nlet t = 1\n'
    out = testcmd.strip_swift(src)
    assert len(out) == len(src)
    assert out.count("\n") == 2
    assert out.splitlines()[1] == "let t = 1"
    assert "note" not in out
    assert out.startswith('let s = "')


def test_unterminated_comment_no_raise():
    assert testcmd.swift_suites("struct A {\n/* never closed\n    @Test func x() {}\n}\n") == []


def test_only_testing_reads_stripped_suite(tmp_path):
    f = tmp_path / "Tests" / "AppTests" / "ParserTests.swift"
    f.parent.mkdir(parents=True)
    f.write_text(P % '"""\n}\n"""')
    assert testcmd.only_testing(["Tests/AppTests/ParserTests.swift"], tmp_path) == "-only-testing:AppTests/ParserTests"


def test_interpolation_with_nested_string_holding_paren():
    src = 'let a = "\\(")")" + "}"\n}\n'
    out = testcmd.strip_swift(src)
    assert out == 'let a = "      " + " "\n}\n'


def test_carriage_returns_kept_and_end_line_comment():
    src = "a // c\r}\r"
    out = testcmd.strip_swift(src)
    assert out == "a     \r}\r"
    assert len(out) == len(src)
