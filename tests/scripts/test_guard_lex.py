"""guard_lex.split: command text to segments (words, redirects, heredocs, substitution bodies, subshells)."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import guard_lex  # noqa: E402
from guard_lex import Redirect, Segment, split  # noqa: E402


def seg(words=(), dyn=None, redirects=(), heredocs=(), bodies=(), subshell=None, sep=""):  # O(w)
    words = list(words)  # O(w)
    return Segment(words, [False] * len(words) if dyn is None else list(dyn), list(redirects), list(heredocs),
                   list(bodies), subshell, sep)  # O(w)


def words_of(text):  # O(n)
    return [s.words for s in split(text)]  # O(n)


def test_example_redirect_and_chain():  # O(1)
    assert split("cp a 'b c' > out.txt && cd src") == [
        seg(["cp", "a", "b c"], redirects=[Redirect(">", "out.txt")], sep="&&"),
        seg(["cd", "src"]),
    ]  # O(1)


def test_example_heredoc():  # O(1)
    assert split("cat <<'EOF' > f\nhi $x\nEOF\n") == [
        seg(["cat"], redirects=[Redirect("<<", "EOF"), Redirect(">", "f")], heredocs=["hi $x\n"]),
    ]  # O(1)


def test_example_dollar_quote_substitution_comment():  # O(1)
    assert split("echo $'a\\tb' x=$(rm -rf src) # c") == [
        seg(["echo", "a\tb", "x=$(rm -rf src)"], dyn=[False, False, True], bodies=["rm -rf src"]),
    ]  # O(1)


def test_example_attached_redirect_and_subshell():  # O(1)
    assert split("rm>/dev/null x; (cd y && rm z) | sh") == [
        seg(["rm", "x"], redirects=[Redirect(">", "/dev/null")], sep=";"),
        seg(subshell="cd y && rm z", sep="|"),
        seg(["sh"]),
    ]  # O(1)


def test_redirect_forms():  # O(1)
    (s,) = split("a 2>&1 >>log &>all >|clob <in <<<word 3<>rw")  # O(1)
    assert s.words == ["a"]  # O(1)
    assert [(r.op, r.target) for r in s.redirects] == [
        (">&", "1"), (">>", "log"), ("&>", "all"), (">|", "clob"), ("<", "in"), ("<<<", "word"), ("<>", "rw"),
    ]  # O(1)


def test_unterminated_quote_is_one_dyn_word():  # O(1)
    (s,) = split("rm 'src/a.py")  # O(1)
    assert len(s.words) == 2 and s.words[0] == "rm"  # O(1)
    assert "src/a.py" in s.words[1] and s.dyn == [False, True]  # O(1)
    (s,) = split('rm "src/a.py; touch b')  # O(1)
    assert len(s.words) == 2 and s.dyn[1] is True  # O(1)
    (s,) = split("echo $(rm src/a.py")  # O(1)
    assert s.dyn[-1] is True  # O(1)


def test_heredoc_dash_and_order():  # O(1)
    a, b = split("cat <<-A >x; cat <<B\n\tone\nA\ntwo\nB\n")  # O(1)
    assert a.heredocs == ["one\n"] and b.heredocs == ["two\n"]  # O(1)
    assert a.sep == ";" and b.sep == ""  # O(1)


def test_backslash_and_dollar_quotes():  # O(1)
    (s,) = split(r'''printf x\ y "a\"b" $'\x41' "$HOME/x"''')  # O(1)
    assert s.words == ["printf", "x y", 'a"b', "A", "$HOME/x"]  # O(1)
    assert s.dyn == [False, False, False, False, True]  # O(1)


def test_continuation_and_comments():  # O(1)
    assert words_of("rm \\\n  a # rm b") == [["rm", "a"]]  # O(1)
    assert words_of("echo a#b") == [["echo", "a#b"]]  # O(1)
    assert words_of("# only a comment\nrm x") == [["rm", "x"]]  # O(1)


def test_braces_flatten():  # O(1)
    assert words_of("{ cd x; rm y; }") == [["cd", "x"], ["rm", "y"]]  # O(1)
    assert words_of("echo {} '{' x") == [["echo", "{}", "{", "x"]]  # O(1)


def test_backticks_and_procsub():  # O(1)
    (s,) = split("a `rm b` <(rm c) >(tee d)")  # O(1)
    assert s.bodies == ["rm b", "rm c", "tee d"]  # O(1)
    assert s.words[0] == "a" and all(s.dyn[1:]) and s.redirects == []  # O(1)


def test_crlf():  # O(1)
    assert split("rm a\r\nrm b\r\n") == split("rm a\nrm b\n")  # O(1)
    assert [s.words for s in split("rm a\r\nrm b\r\n")] == [["rm", "a"], ["rm", "b"]]  # O(1)


def test_separators():  # O(1)
    segs = split("a && b || c ; d | e & f\ng")  # O(1)
    assert [s.sep for s in segs] == ["&&", "||", ";", "|", "&", "\n", ""]  # O(1)
    assert [s.sep for s in split("a |& b")] == ["|", ""]  # O(1)
    assert [s.sep for s in split("a;\n\nb &&\nc")] == [";", "&&", ""]  # O(1)
    assert [s.sep for s in split("a\n")] == [""]  # O(1)


def test_empty_and_blank():  # O(1)
    assert split("") == [] and split("  \n \t ") == [] and split("# x") == []  # O(1)


def test_single_quote_dollar_is_literal():  # O(1)
    (s,) = split("echo '$HOME' \"\\$HOME\" \"$HOME\" `x` $((1+2)) ${a:-b} $1 $")  # O(1)
    assert s.words == ["echo", "$HOME", "$HOME", "$HOME", "`x`", "$((1+2))", "${a:-b}", "$1", "$"]  # O(1)
    assert s.dyn == [False, False, False, True, True, True, True, True, False]  # O(1)


def test_nested_substitution_bodies():  # O(1)
    (s,) = split('echo "$(echo $(rm a))" ${x:-$(rm b)} "${y:-`rm c`}"')  # O(1)
    assert s.bodies == ["echo $(rm a)", "rm b", "rm c"]  # O(1)
    assert s.words[1] == "$(echo $(rm a))"  # O(1)


def test_substitution_body_hides_operators_and_quotes():  # O(1)
    (s,) = split("echo $(echo ')' ; rm 'a b') after")  # O(1)
    assert s.words == ["echo", "$(echo ')' ; rm 'a b')", "after"]  # O(1)
    assert s.bodies == ["echo ')' ; rm 'a b'"]  # O(1)


def test_unquoted_heredoc_runs_substitutions():  # O(1)
    (s,) = split("cat <<EOF\nhi $(rm -rf src) `rm b` \\$(no)\nEOF\n")  # O(1)
    assert s.bodies == ["rm -rf src", "rm b"] and len(s.heredocs) == 1  # O(1)
    (s,) = split("cat <<'EOF'\nhi $(rm -rf src)\nEOF\n")  # O(1)
    assert s.bodies == []  # O(1)


def test_heredoc_ends_only_on_exact_delimiter():  # O(1)
    a, b = split("cat <<EOF\n EOF\nEOF x\nEOF\nrm y\n")  # O(1)
    assert a.heredocs == [" EOF\nEOF x\n"] and a.sep == "\n"  # O(1)
    assert b.words == ["rm", "y"]  # O(1)
    (s,) = split("cat <<EOF\nabc")  # O(1)
    assert s.heredocs == ["abc\n"]  # O(1)
    (s,) = split("cat <<-E\n\t\tx\n\tE\n")  # O(1)
    assert s.heredocs == ["x\n"]  # O(1)


def test_two_heredocs_on_one_line():  # O(1)
    (s,) = split("cat <<A <<B\n1\nA\n2\nB\n")  # O(1)
    assert s.heredocs == ["1\n", "2\n"]  # O(1)


def test_fd_prefix_dropped_only_when_glued():  # O(1)
    (s,) = split("echo 2 >f a2>g '3'>h {fd}>i")  # O(1)
    assert s.words == ["echo", "2", "a2", "3"] and [r.target for r in s.redirects] == ["f", "g", "h", "i"]  # O(1)
    (s,) = split("echo 2>f")  # O(1)
    assert s.words == ["echo"]  # O(1)


def test_redirect_target_substitution_is_a_body():  # O(1)
    (s,) = split("echo x > $(echo f)")  # O(1)
    assert s.redirects == [Redirect(">", "$(echo f)")] and s.bodies == ["echo f"]  # O(1)


def test_subshell_forms():  # O(1)
    (s,) = split("(cd y; rm z) > out")  # O(1)
    assert s.subshell == "cd y; rm z" and s.redirects == [Redirect(">", "out")]  # O(1)
    a, b = split("(cat <<EOF\n)\nEOF\n); rm x")  # O(1)
    assert a.subshell == "cat <<EOF\n)\nEOF" and b.words == ["rm", "x"]  # O(1)
    assert words_of("f() { rm x; }") == [["f"], ["rm", "x"]]  # O(1)


def test_case_patterns_split_commands():  # O(1)
    assert words_of("case $x in a) rm y;; (b) rm z;; esac") == [
        ["case", "$x", "in", "a"], ["rm", "y"], [], ["rm", "z"], ["esac"],
    ]  # O(1)


def test_quote_escapes_in_ansi_c():  # O(1)
    (s,) = split(r"""echo $'\\' $'\'' $'\101\x4a\u00e4' $'\xc3\xa4' $'a\0b' $'\q'""")  # O(1)
    assert s.words == ["echo", "\\", "'", "AJä", "ä", "a", "\\q"]  # O(1)


def test_deep_nesting_does_not_raise():  # O(1)
    for text in ("echo " + "$(" * 3000 + "x" + ")" * 3000, "(" * 3000 + "x" + ")" * 3000):  # O(1)
        segs = split(text)  # O(1)
        assert any(s.subshell is not None or any(s.dyn) for s in segs)  # O(1)


def test_types_are_shared():  # O(1)
    assert guard_lex.Segment is Segment and guard_lex.Redirect is Redirect  # O(1)


def test_single_quote_in_dquoted_brace_is_literal():  # O(1)
    segs = split("echo \"${a:-'}\"; rm x; echo '}'")
    assert [s.words[0] for s in segs] == ["echo", "rm", "echo"]


def test_function_keyword_and_control_brace_group():  # O(1)
    assert [s.words for s in split("function f { rm x; }; f")] == [["function", "f"], ["rm", "x"], ["f"]]
    assert [s.words for s in split("if t; then { rm y; }; fi")] == [["if", "t"], ["then", "rm", "y"], ["fi"]]
    assert split("time { rm x; }")[0].words == ["time", "rm", "x"]


def test_deep_quote_brace_nesting_does_not_raise():  # O(1)
    segs = split('"${a:-' * 3000)
    assert segs and any(s.dyn and s.dyn[-1] for s in segs)


def test_brace_expansion_and_command_glob_are_dyn():  # O(1)
    assert split("{rm,x} y")[0].dyn == [True, False]
    assert split("x=1 /bin/r? y")[0].dyn == [False, True, False]
    assert split("ls *.py")[0].dyn == [False, False]


def test_glob_and_brace_flags_per_word_and_redirect():  # O(1)
    s = split("tee .superlite/{a,b} x 'q*' a{b}c > .superlite/o*")[0]
    assert s.globs == ["", "b", "", "", "b"]
    assert s.redirects[0].glob == "g"
    assert split("[ -f x ] && [[ -d y ]]")[0].globs == ["", "", "", ""]
    assert split("[ -f x ]")[0].dyn == [False, False, False, False]  # a lone `[` is the test command, no glob
    assert split("echo 'a'{b,c} \"{a,b}\" x[ab]")[0].globs == ["", "u", "", "g"]
    assert split("cat <(rm x) 2>/dev/null y*")[0].globs == ["", "", "g"]
