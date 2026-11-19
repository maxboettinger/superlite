"""#987: fleet_roles holds a researcher's Bash command to RESEARCH_BASH and RESEARCH_DENY."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fleet_roles as fr  # noqa: E402

_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
HEAD = "Blocked: the researcher runs only read-only commands (hooks/researcher-bash, #987): "
LIST = ("Allowed, alone or joined by &&, ||, ;, & or |: git log, git show, git diff, git status, git blame, "
        "git ls-files, git rev-parse, git merge-base, git cat-file, git worktree list, git apply --check, ls, "
        "xcrun simctl list; never --output; git apply --check only with read-only options (no --apply, --no-check, "
        "--build-fake-ancestor, --3way or --reject); no $(...), backticks, <(...), variables, subshells, heredocs or "
        "redirects into a file (2>/dev/null, 2>&1 and < file are fine).")
TAIL = "A refused command is an answer: say what you could not check and never retry it another way."

ALLOWED = [
    "", "git log", "git log --oneline -5", "git status --short", "git show HEAD~1:docs/hooks.md",
    "git diff main...HEAD -- hooks/", "git log --grep='a|b' -3", "git log -5 2>/dev/null", "git log -5 2>&1",
    "git log -1 &>/dev/null", "git log -1 && git status", "git log -1; ls hooks", "git diff HEAD~1 | git apply --check",
    "git apply --check < x.patch", "ls", "ls -la hooks ~", "ls src/*.py", "xcrun simctl list devices",
    "git worktree list --porcelain", "git cat-file -p HEAD", "git log -1  # why", "git log \\\n -1",
    "git log HEAD@{1}", "git log --oneline -3", "git log -- src/*.py",
    "git apply --check -p1 --stat x.patch", "git apply --check --reverse --whitespace=nowarn x.patch",
    "git apply --check -- --3way.patch",
]

REFUSED = [
    ("touch x", "not on the allowlist: touch x"),
    ("git log -1 && rm -rf src", "not on the allowlist: rm -rf src"),
    ("git log | head -5", "not on the allowlist: head -5"),
    ("git -C other log", "not on the allowlist: git -C other log"),
    ("git checkout main", "not on the allowlist: git checkout main"),
    ("FOO=1 git log", "not on the allowlist: FOO=1 git log"),
    ("cd src && ls", "not on the allowlist: cd src"),
    ("git worktree add x", "not on the allowlist: git worktree add x"),
    ("git apply x.patch", "not on the allowlist: git apply x.patch"),
    ("python3 -c 'print(1)'", "not on the allowlist: python3 -c print(1)"),
    ("git diff --output=x.patch", "writes a file (--output): git diff --output=x.patch"),
    ("git log --output x HEAD", "writes a file (--output): git log --output x HEAD"),
    ("git apply --check --apply x.patch", "applies a patch (--apply): git apply --check --apply x.patch"),
    ('git show "$(rm -rf x)"', "runs a substitution: git show $(rm -rf x)"),
    ("git log `id`", "runs a substitution: git log `id`"),
    ("git diff <(cat a)", "runs a substitution: git diff <(cat a)"),
    ("git log $X", "expands a value: git log $X"),
    ("(git log)", "runs a subshell: (git log)"),
    ("git log <<EOF\nx\nEOF", "reads a heredoc or here-string: git log << EOF"),
    ("git log <<< x", "reads a heredoc or here-string: git log <<< x"),
    ("git diff > x.patch", "redirects into a file: git diff > x.patch"),
    ("git log >> log.txt", "redirects into a file: git log >> log.txt"),
    ("git log >&x.txt", "redirects into a file: git log >& x.txt"),
    ("git log 2>err.txt", "redirects into a file: git log > err.txt"),
    ("ls <> f", "redirects into a file: ls <> f"),
    ("git apply --check --ap x.patch", "applies a patch (--apply): git apply --check --ap x.patch"),
    ("git apply --check --appl=1 x.patch", "applies a patch (--apply): git apply --check --appl=1 x.patch"),
    ("git diff --outp=x", "writes a file (--output): git diff --outp=x"),
    ("git apply --check --build-fake-ancestor=idx x.patch",
     "writes a file (--build-fake-ancestor): git apply --check --build-fake-ancestor=idx x.patch"),
    ("git apply --check --build=idx x.patch", "writes a file (--build-fake-ancestor): git apply --check --build=idx x.patch"),
    ("git apply --check --no-check x.patch", "applies a patch (--no-check): git apply --check --no-check x.patch"),
    ("git apply --check --no-ch x.patch", "applies a patch (--no-check): git apply --check --no-ch x.patch"),
    ("git apply --check --3way x.patch", "git apply option off the read-only list: git apply --check --3way x.patch"),
    ("git apply --check --reject x.patch", "git apply option off the read-only list: git apply --check --reject x.patch"),
    ("git apply --check -Rv x.patch", "git apply option off the read-only list: git apply --check -Rv x.patch"),
    ("git diff *", "expands a value: git diff *"),
    ("git log {--output=x,HEAD}", "expands a value: git log {--output=x,HEAD}"),
    ("git apply --check {--apply,x.patch}", "expands a value: git apply --check {--apply,x.patch}"),
]


def payload(command, agent="superlite:researcher", tool="Bash"):
    p = {"session_id": "s1", "tool_name": tool, "tool_input": {"command": command}}
    if agent is not None:
        p["agent_type"] = agent
    return json.dumps(p)


def sl(args, text):
    return subprocess.run([BASH, str(SCRIPTS / "sl"), *args], input=text, capture_output=True, text=True)


@pytest.mark.parametrize("command", ALLOWED)
def test_allowed(command):
    assert fr.research_bash_refusal(command) is None


@pytest.mark.parametrize("command,reason", REFUSED)
def test_refused(command, reason):
    assert fr.research_bash_refusal(command) == reason


def test_lexer_error_refuses(monkeypatch):
    import guard_lex

    def boom(text):
        raise RuntimeError("x")

    monkeypatch.setattr(guard_lex, "split", boom)
    assert fr.research_bash_refusal("git log") == "could not read the command (RuntimeError)"


def test_hook_passes_an_allowed_command():
    assert fr.research_hook(payload("git log -1")) == (0, "")


def test_hook_blocks_with_the_reason_and_the_list():
    code, msg = fr.research_hook(payload("touch x"))
    assert code == 2
    assert msg.splitlines() == [HEAD + "not on the allowlist: touch x.", LIST, TAIL]


@pytest.mark.parametrize("text", [
    payload("rm -rf x", agent="superlite:implementer"),
    payload("rm -rf x", agent=None),
    payload("rm -rf x", agent="researcher"),
    payload("rm -rf x", tool="Read"),
    json.dumps({"agent_type": "superlite:researcher", "tool_name": "Bash", "tool_input": {"command": 5}}),
    json.dumps({"agent_type": "superlite:researcher", "tool_name": "Bash", "tool_input": "rm -rf x"}),
    json.dumps(["superlite:researcher"]),
    '{"agent_type": "superlite:researcher", ',
    "",
])
def test_hook_passes_every_other_payload(text):
    assert fr.research_hook(text) == (0, "")


def test_cli_reads_the_payload_from_stdin():
    r = sl(["fleet_roles", "research-bash"], payload("git diff > x.patch"))
    assert (r.returncode, r.stdout) == (2, "")
    assert r.stderr.splitlines()[0] == HEAD + "redirects into a file: git diff > x.patch."
    ok = sl(["fleet_roles", "research-bash"], payload("git status"))
    assert (ok.returncode, ok.stdout, ok.stderr) == (0, "", "")


def test_cli_without_the_subcommand_is_usage():
    r = sl(["fleet_roles"], "")
    assert r.returncode == 2
    assert "usage: fleet_roles.py research-bash (hook payload on stdin)" in r.stderr
