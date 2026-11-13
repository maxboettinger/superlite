import json
import os
import subprocess
import sys

import pytest

from test_block_coordinator_edits import ROOT, bash, proj, run  # noqa: F401

JUDGE = ROOT / "skills" / "subagent-driven-development" / "scripts" / "guard_judge.py"


@pytest.mark.parametrize("cmd", [
    'eval "$(echo rm -rf src)"',
    "eval $(echo rm -rf src)",
    'eval "`echo rm -rf src`"',
    "eval \"$(printf 'rm -rf src')\"",
    "eval \"$(printf '%s ' rm -rf src)\"",
    "x='rm -rf src'; eval \"$x\"",
])
def test_eval_echo_substitution_blocks(proj, cmd):
    r = bash(proj, cmd)
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src"


@pytest.mark.parametrize("cmd", [
    'eval "$(some-tool --print)"',
    'eval "$Y"',
    'x=$(date); eval "$x"',
    "eval \"$(echo -e 'rm src')\"",
])
def test_eval_unresolved_refused(proj, cmd):
    r = bash(proj, cmd)
    assert r.returncode == 2, r.stderr
    assert "text the guard cannot resolve" in r.stderr


@pytest.mark.parametrize("cmd", [
    "eval 'ls'",
    "eval ls -la",
    'eval "$(echo ls docs)"',
    "x='ls docs'; eval \"$x\"",
    'eval "$(ssh-agent -s)"',
    "eval \"$(cat)\" <<'EOF'\nls\nEOF",
])
def test_eval_still_passes(proj, cmd):
    assert bash(proj, cmd).returncode == 0


def test_eval_cat_heredoc_judged(proj):
    assert bash(proj, "eval \"$(cat)\" <<'EOF'\nrm -rf src\nEOF").returncode == 2


def test_eval_idle_not_judged(proj):
    (proj / ".superlite" / "pool.json").unlink()
    assert bash(proj, 'eval "$(some-tool --print)"').returncode == 0


def _hook(proj, cmd, cwd=None, env_extra=None):
    import test_block_coordinator_edits as t
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, **({"cwd": str(cwd)} if cwd else {})})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), **(env_extra or {})}
    return subprocess.run([t.BASH, str(t.HOOK)], input=raw, capture_output=True, text=True, env=env)


@pytest.mark.parametrize("var", ["TMPDIR", "CLAUDE_PROJECT_DIR", "PWD"])
def test_unquoted_vars_with_space_unknown(tmp_path, var):
    if var == "CLAUDE_PROJECT_DIR":
        p = tmp_path / "p q"
        p.mkdir()
    else:
        p = tmp_path / "proj"
        p.mkdir()
    (p / ".superlite").mkdir(exist_ok=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    cwd, env = p, {}
    tail = "docs/plans/n.md"
    if var == "TMPDIR":
        spaced = tmp_path / "t d"   # outside the project, so the quoted form writes nothing the guard judges
        spaced.mkdir()
        env["TMPDIR"] = str(spaced)
        tail = "n.txt"
    elif var == "PWD":
        cwd = p / "docs" / "plans" / "a b"
        cwd.mkdir(parents=True)
        tail = "n.md"
    unq = f"echo x > ${var}/{tail}"
    quo = f'echo x > "${var}"/{tail}'
    r = _hook(p, unq, cwd, env)
    assert r.returncode == 2, r.stderr
    assert f"Unresolved word: ${var}/{tail}" in r.stderr   # an unknown word, as for $HOME
    assert _hook(p, quo, cwd, env).returncode == 0
    if var == "TMPDIR":
        plain = tmp_path / "td"
        plain.mkdir()
        assert _hook(p, unq, cwd, {"TMPDIR": str(plain)}).returncode == 0


def test_code_message_carries_scratch_hint(proj):
    cmd = "cat > src/x.py <<'EOF'\nprint(1)\nEOF"
    r = bash(proj, cmd)
    assert r.returncode == 2
    lines = r.stderr.splitlines()
    hints = [i for i, ln in enumerate(lines) if ln.startswith("- A throwaway script")]
    assert len(hints) == 1 and ".superlite/scratch/" in lines[hints[0]]
    assert lines[hints[0] + 1].startswith("- After the run, ")
    j = subprocess.run([sys.executable, "-I", str(JUDGE), "--mode", "active", "--project", str(proj),
                        "--sd", str(proj / ".superlite")],
                       input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
                       capture_output=True, text=True)
    assert j.returncode == 2
    assert j.stderr.count("- A throwaway script") == 1 and ".superlite/scratch/" in j.stderr
    p = bash(proj, "echo x > .superlite/orchestrator.json")
    assert p.returncode == 2 and "throwaway script" not in p.stderr
