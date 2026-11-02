import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401  (proj is a fixture)

PY = "open('src/a.py','w').write('x')"


@pytest.mark.parametrize("name,cmd", [
    ("issue_body_double_quoted", "gh issue create --body \"see python3 -c \\\"open('src/a.py','w')\\\"\""),
    ("issue_body_heredoc_substitution",
     "gh issue create --title t --body \"$(cat <<'EOF'\npython3 -c \"open(sys.argv[1],'w')\"\nEOF\n)\""),
    ("commit_message_quotes_writer", "git commit -m \"fix python3 Path('a.py').write_text('x')\""),
    ("heredoc_into_plan_quotes_writer",
     "cat > docs/plans/p.md <<'EOF'\npython3 -c \"open('src/a.py','w')\"\nEOF"),
    ("feedback_add_quotes_writer",
     "bash \"$SL\" feedback add \"guard hit node -e writeFileSync('a.js')\""),
    ("quoted_protected_name_not_flagged",
     "gh issue comment 1 --body \"python3 wrote orchestrator.json via open('x','w')\""),
])
def test_quoted_text_allowed(proj, name, cmd):  # noqa: F811
    assert bash(proj, cmd).returncode == 0


def test_real_interpreter_still_blocked(proj):  # noqa: F811
    assert bash(proj, f'python3 -c "{PY}"').returncode == 2


@pytest.mark.parametrize("sh", ["bash -c", "sh -c", "zsh -lc"])
def test_shell_c_wrapper_blocked(proj, sh):  # noqa: F811
    assert bash(proj, f'{sh} "python3 -c \\"{PY}\\""').returncode == 2


def test_eval_wrapper_blocked(proj):  # noqa: F811
    assert bash(proj, f'eval "python3 -c \\"{PY}\\""').returncode == 2


def test_dollar_paren_substitution_blocked(proj):  # noqa: F811
    assert bash(proj, f'echo "$(python3 -c "{PY}")"').returncode == 2


def test_pipe_into_interpreter_blocked(proj):  # noqa: F811
    assert bash(proj, f"cat <<'EOF' | python3\n{PY}\nEOF").returncode == 2


HEREDOC_BODY = "gh issue create --body \"$(cat <<'EOF'\nbody\nEOF\n)\""


def test_command_after_quoted_heredoc_judged(proj):  # noqa: F811
    assert bash(proj, HEREDOC_BODY + " && rm src/a.py").returncode == 2


def test_interpreter_after_quoted_heredoc_judged(proj):  # noqa: F811
    assert bash(proj, HEREDOC_BODY + f' && python3 -c "{PY}"').returncode == 2


@pytest.mark.parametrize("cmd", [
    f'"python3" -c "{PY}"',
    f"'python3' -c \"{PY}\"",
    f"echo \\' ; python3 -c \"{PY}\"",
    f'echo \\" ; python3 -c "{PY}"',
    f"echo hi # it's\npython3 -c \"{PY}\"",
    f'python3 -c "{PY}" # "',
    f"echo $'a\\'b' ; python3 -c \"{PY}\"",
])
def test_stripper_evasions_still_scanned(proj, cmd):  # noqa: F811
    assert bash(proj, cmd).returncode == 2


def test_protected_write_through_shell_c_blocked(proj):  # noqa: F811
    r = bash(proj, "sh -c \"python3 -c \\\"open('.superlite/orchestrator.json','w')\\\"\"")
    assert r.returncode == 2 and "sl orchestrator" in r.stderr


@pytest.mark.parametrize("cmd", [
    f"bash <<'EOF'\npython3 -c \"{PY}\"\nEOF",
    f"cat <<'EOF' | sh\npython3 -c \"{PY}\"\nEOF",
    f"cat <<'EOF' | bash -s\npython3 -c \"{PY}\"\nEOF",
    f"bash -s <<'EOF'\npython3 -c \"{PY}\"\nEOF",
])
def test_stdin_shell_body_scanned(proj, cmd):  # noqa: F811
    assert bash(proj, cmd).returncode == 2


@pytest.mark.parametrize("head", [
    "bash <<'EOF' 2>&1", "bash <<'EOF' > log", "bash -euo pipefail <<'EOF'", "VAR=x bash <<'EOF'",
    "timeout 60 bash <<'EOF'", "bash <<'EOF' >> log 2>&1", "env A=1 bash -s <<'EOF'",
])
def test_stdin_shell_forms_scanned(proj, head):  # noqa: F811
    assert bash(proj, f"{head}\npython3 -c \"{PY}\"\nEOF").returncode == 2


def test_stdin_shell_without_writer_allowed(proj):  # noqa: F811
    assert bash(proj, "cat <<'EOF' | sh\necho hi\nEOF").returncode == 0


@pytest.mark.parametrize("wrapper", ["uv run python", "env A=1 python3", "timeout 5 python3", "python3"])
def test_substitution_with_wrapper_blocked(proj, wrapper):  # noqa: F811
    assert bash(proj, f'x="$({wrapper} -c "{PY}")"').returncode == 2


def test_quoted_interpreter_name_inside_argument_allowed(proj):  # noqa: F811
    cmd = "gh pr create --body \"runs 'python3' ... open('x','w')\""
    assert bash(proj, cmd).returncode == 0
    assert bash(proj, f"x=1; 'python3' -c \"{PY}\"").returncode == 2
