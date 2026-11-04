"""Coordinator guard: a stdin shell's program (a heredoc body, a here-string) is judged like a -c body (#121)."""
import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401


def idle_proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    return tmp_path


@pytest.mark.parametrize("cmd", [
    "bash <<'EOF'\necho x > src/a.py\nEOF",
    "sh -s <<'EOF'\nrm src/a.py\nEOF",
    "bash <<EOF\nrm src/a.py\nEOF",
    "bash <<\"EOF\"\nrm src/a.py\nEOF",
    "bash -e <<-EOF\n\trm src/a.py\n\tEOF",
    "zsh<<'EOF'\nrm src/a.py\nEOF",
    "bash << 'EOF'\nrm src/a.py\nEOF",
    "bash <<- EOF\n\trm src/a.py\n\tEOF",
    "bash 2> /dev/null <<'EOF'\nrm src/a.py\nEOF",
    "bash --norc -x <<'EOF'\nrm src/a.py\nEOF",
    "echo hi && bash <<'EOF'\nrm src/a.py\nEOF",
    "sudo bash <<'EOF'\nrm src/a.py\nEOF",
    "env X=1 sh <<'EOF'\nrm src/a.py\nEOF",
    "bash -s -- arg <<'EOF'\nrm src/a.py\nEOF",
    "bash -o pipefail <<'EOF'\nrm src/a.py\nEOF",
    "bash /dev/stdin <<'EOF'\nrm src/a.py\nEOF",
    "bash - <<'EOF'\nrm src/a.py\nEOF",
    "source /dev/stdin <<'EOF'\nrm src/a.py\nEOF",
    ". /dev/stdin <<'EOF'\nrm src/a.py\nEOF",
    "bash <<'EOF'\nsed -i s/a/b/ src/a.py\nEOF",
    "bash <<'EOF'\necho ok\ncp /tmp/x src/a.py\nEOF",
    "bash <<'EOF' && echo done\nrm src/a.py\nEOF",
    # the same tag twice: the second body is the shell's program
    "cat > /tmp/notes <<'EOF'\nhello\nEOF\nbash <<'EOF'\nrm src/a.py\nEOF",
    "bash <<< 'rm src/a.py'",
    'sh <<< "echo x > src/a.py"',
    "bash <<<'rm src/a.py'",
])
def test_stdin_shell_program_is_judged(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    "cat <<'EOF'\nrm src/a.py\nEOF",
    "cat > /tmp/x.sh <<'EOF'\nrm src/a.py\nEOF",
    "bash script.sh <<'EOF'\nrm src/a.py\nEOF",
    "bash -c 'cat' <<'EOF'\nrm src/a.py\nEOF",
    "bash <<'EOF'\necho x > docs/plans/p.md\nEOF",
    "bash <<'EOF'\necho x > .superlite/fixes/F.md\nEOF",
    "bash <<'EOF'\necho x > /tmp/out.txt\nEOF",
    "cat > /tmp/a <<'EOF'\nrm src/a.py\nEOF\nbash <<'EOF'\necho hi\nEOF",
    "bash <<< 'echo hi'",
    "grep -c x <<< 'rm src/a.py'",
])
def test_stdin_data_and_allowed_programs_pass(proj, cmd):
    assert bash(proj, cmd).returncode == 0, cmd


def test_outside_a_run_only_protected_files_block(tmp_path):
    p = idle_proj(tmp_path)
    assert bash(p, "bash <<'EOF'\nrm src/a.py\nEOF").returncode == 0
    assert bash(p, "bash <<'EOF'\necho x > .superlite/orchestrator.json\nEOF").returncode == 2


def test_hooks_doc_names_the_stdin_shell_rule_and_its_limit():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text()
    line = [x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`")][0]
    for s in ("stdin shell's program", "piped into a shell", "`nohup`, `timeout`, `nice` and `exec`"):
        assert s in line, s
