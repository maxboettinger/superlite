import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401

PYW = "python3 -c \"open('src/a.py','w')\""


def blocked(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


def allowed(proj, cmd):
    assert bash(proj, cmd).returncode == 0, cmd


def test_trailing_comment(proj):
    blocked(proj, "rm src/a.py # don't")


def test_quoted_heredoc_marker(proj):
    blocked(proj, 'echo "<<EOF"\nrm src/a.py')
    blocked(proj, "cat <<< hi\nrm src/a.py")
    blocked(proj, 'echo "<<EOF"\n' + PYW)
    blocked(proj, "cat <<< hi\n" + PYW)


def test_unterminated_heredoc(proj):
    blocked(proj, "cat <<EOF\nrm src/a.py")


def test_background_and_groups(proj):
    blocked(proj, "true & rm src/a.py")
    blocked(proj, "(rm src/a.py)")
    blocked(proj, "{ rm src/a.py; }")
    blocked(proj, "if x; then rm src/a.py; fi")
    blocked(proj, "while x; do rm src/a.py; done")


def test_clobber_redirect(proj):
    blocked(proj, "echo x >| src/a.py")


def test_shell_c_body_judged(proj):
    blocked(proj, 'bash -c "rm src/a.py"')
    blocked(proj, "sh -c 'rm src/a.py'")
    blocked(proj, 'bash -o pipefail -c "rm src/a.py"')
    blocked(proj, 'ksh -c "rm src/a.py"')
    blocked(proj, 'zsh -c "rm src/a.py"')


def test_substitution_body_judged(proj):
    blocked(proj, 'echo "$(true; python3 -c "open(\'src/a.py\',\'w\')")"')
    blocked(proj, 'echo "$(rm src/a.py)"')
    blocked(proj, "echo `rm src/a.py`")


def test_harmless_stays_allowed(proj):
    allowed(proj, 'echo "a & b"')
    allowed(proj, 'echo "if x; then rm src/a.py; fi"')
    allowed(proj, 'git commit -m "rm src/a.py"')
    allowed(proj, "cat <<EOF\nrm src/a.py\nEOF")
    allowed(proj, "echo hi # rm src/a.py")
    allowed(proj, "grep '<<EOF' src/a.py")
    allowed(proj, "gh issue create --title 'x > y' --body-file -")


def test_quoted_words_keep_order_across_segments(proj):
    # the regex engine may match the first or the last quoted text first; each Q mark must get its own text
    blocked(proj, 'echo "x" && bash -c "echo hi > src/a.py"')
    blocked(proj, "echo 'x' && sh -c \"echo hi > src/a.py\"")
    blocked(proj, 'echo "a" "b" && sh -c "echo hi > src/a.py"')
    blocked(proj, 'echo "x" | bash -c "cat > src/a.py"')
    blocked(proj, 'echo "a" > "docs/plans/p.md" && echo "b" > "src/a.py"')
    allowed(proj, 'echo "src/a.py" "x" > "docs/plans/p.md"')
    allowed(proj, 'echo "x" && bash -c "echo hi > docs/a.md"')


def test_eval_body_judged(proj):
    blocked(proj, 'eval "echo x > src/a.py"')
    blocked(proj, "echo 'a' && eval 'sed -i s/a/b/ src/a.py'")
    allowed(proj, 'eval "echo x > docs/a.md"')
    allowed(proj, 'eval "$(ssh-agent -s)"')


def test_sl_exemption_reads_the_raw_segment(proj):
    # the exemption must not read a quoted text: a path in a string is not an sl call (F-T8-1 #1)
    blocked(proj, 'sed -i "s#subagent-driven-development/scripts#x#" src/a.py')
    blocked(proj, 'echo "see subagent-driven-development/scripts" > src/app.py')
    allowed(proj, "/x/skills/subagent-driven-development/scripts/sl run_tests --fast tests/a.py")
    allowed(proj, "$SL run_tests --fast tests/a.py")


def test_open_rb_plus_is_a_write(proj):
    # F-T8-1 #2
    blocked(proj, "python3 -c \"open('src/a.py','rb+')\"")
    blocked(proj, "python3 -c \"open('src/a.py','r+b')\"")
    allowed(proj, "python3 -c \"open('src/a.py','rb')\"")


def test_quote_marks_survive_multiline_and_comments(proj):
    # F-T8-1 #3: a multi-line quote or a comment with a quote must not unpair the quoted texts
    blocked(proj, 'bash -c "rm src/a.py" # "x"')
    blocked(proj, 'echo "a" "multi\nline" && bash -c "rm src/a.py"')
    blocked(proj, 'echo "a" "multi\nline" && echo hi > "src/a.py"')
    blocked(proj, 'echo "multi\nline" # "c"\nbash -c "rm src/a.py"')
    allowed(proj, 'echo "a" "multi\nline" && bash -c "echo hi > docs/a.md"')


def test_eval_unquoted_words_judged(proj):
    # F-T8-1 #4
    blocked(proj, "eval rm src/a.py")
    blocked(proj, 'eval rm "src/a.py"')
    blocked(proj, "eval echo x > src/a.py")
    allowed(proj, "eval echo hi")


def test_escaped_substitutions_in_quotes_do_not_run(proj):
    # F-T8-1 #5
    allowed(proj, 'git commit -m "see \\`rm src/a.py\\` and \\$(rm src/a.py)"')
    blocked(proj, 'echo "$(rm src/a.py)"')
    blocked(proj, 'echo "x \\\\$(rm src/a.py)"')


def test_sed_empty_suffix_counts(proj):
    # F-T8-1 #6
    allowed(proj, "sed -i '' 's/x$/y/' /tmp/f")
    blocked(proj, "sed -i '' s/a/b/ src/a.py")
    blocked(proj, "sed -i '' 's/x$/y/' src/a.py")
    blocked(proj, "sed -i '' -e 's/x$/y/' src/a.py")
