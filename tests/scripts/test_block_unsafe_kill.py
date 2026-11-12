import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-unsafe-kill"
# Git Bash on Windows (WSL's bash.exe in System32 would not see Windows paths), bash elsewhere.
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture(autouse=True)
def fake_ps(tmp_path, monkeypatch):
    """A `ps` first on PATH that names a harmless command, so no test reaches the real process table."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    ps = bindir / "ps"
    ps.write_text("#!/bin/sh\necho /usr/bin/true\n", encoding="utf-8")
    ps.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))


def run(payload, tool="Bash", raw=None):
    if raw is None:
        raw = json.dumps({"tool_name": tool, "tool_input": {"command": payload}})
    return subprocess.run(
        [BASH, str(HOOK)], input=raw, capture_output=True, text=True
    )


def test_blocks_taskkill_im():
    for cmd in ("taskkill /F /IM python.exe", "taskkill //F //IM python.exe", "TASKKILL /im node.exe"):
        r = run(cmd)
        assert r.returncode == 2, cmd
        assert "PID" in r.stderr


def test_blocks_pkill_killall_stop_process_name():
    for cmd, tool in (
        ("pkill -f server", "Bash"),
        ("killall node", "Bash"),
        ("Stop-Process -Name python -Force", "PowerShell"),
        ("stop-process -name python", "PowerShell"),
        ("kill -9 -1", "Bash"),
    ):
        assert run(cmd, tool).returncode == 2, cmd


def test_allows_kill_by_pid():
    for cmd, tool in (
        ("kill 1234", "Bash"),
        ("kill -9 1234", "Bash"),
        ("taskkill /PID 1234", "Bash"),
        ("taskkill //F //PID 1234", "Bash"),
        ("Stop-Process -Id 12", "PowerShell"),
    ):
        r = run(cmd, tool)
        assert r.returncode == 0, cmd
        assert r.stdout == "" and r.stderr == ""


def test_allows_unrelated_commands():
    for cmd in ("ls -la", "python -m pytest", "echo skill"):
        assert run(cmd).returncode == 0, cmd
    # other tools are ignored
    assert run("pkill x", tool="Read").returncode == 0


def test_malformed_input_fails_open():
    for raw in ("", "not json", "[]", json.dumps({"tool_name": "Bash"}),
                json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}})):
        r = run(None, raw=raw)
        assert r.returncode == 0, raw
        assert r.stdout == "" and r.stderr == ""


def test_hooks_json_has_both_entries():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert "SessionStart" in data["hooks"]
    pre = data["hooks"]["PreToolUse"]
    assert pre[0]["matcher"] == "Bash|PowerShell"
    assert pre[0]["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/block-unsafe-kill"'


def test_blocks_multiline_and_escaped_newlines():
    for cmd in ("echo x\npkill -f y", "echo x\r\npkill -f y", "echo x\n\tkillall node"):
        assert run(cmd).returncode == 2, repr(cmd)
    # a literal backslash-n typed by the model is treated the same way
    assert run("echo x\npkill -f y").returncode == 2


def test_blocks_get_process_pipe_taskkill_filter_kill_all():
    for cmd, tool in (
        ("Get-Process python | Stop-Process -Force", "PowerShell"),
        ("get-process -Name node|stop-process", "PowerShell"),
        ("taskkill /F /FI \"IMAGENAME eq python.exe\"", "Bash"),
        ("taskkill //FI \"STATUS eq running\"", "Bash"),
        ("kill -KILL -1", "Bash"),
        ("kill -s KILL -1", "Bash"),
    ):
        assert run(cmd, tool).returncode == 2, cmd


def test_allows_pid_forms_of_new_rules():
    for cmd, tool in (
        ("Get-Process -Id 12 | Stop-Process -Id 12", "PowerShell"),
        ("kill -KILL 1234", "Bash"),
        ("kill -s KILL 1234", "Bash"),
        ("kill -9 12345", "Bash"),
        ("echo x\nkill 1234", "Bash"),
    ):
        assert run(cmd, tool).returncode == 0, cmd


# --- #666: only a command word is read; quotes, heredocs and other commands' arguments are data

TEXT_ONLY = (
    'echo "--- kill job 1 wrapper"',
    'sl feedback add "pkill -f server and killall node were refused as text"',
    "echo 'killall node'",
    'printf "%s\\n" "taskkill /F /IM python.exe"',
    'grep -rn "pkill\\|killall" hooks/',
    "grep -E '(pkill|killall)' notes.txt",
    "python3 -c \"import re; print(re.findall(r'\\b(kill|pkill|killall)\\b', 'x'))\"",
    "python3 -c 'import json; print(json.dumps({\"cmd\": \"killall node\"}))'",
    "python3 - <<'EOF'\nimport re\nPAT = re.compile(r'\\b(kill|pkill|killall)\\b')\nprint('pkill -f server')\nEOF\necho done",
    "cat > notes.json <<EOF\n{\"cmd\": \"killall node\", \"all\": \"kill -9 -1\"}\nEOF",
    "cat <<-EOF > x.txt\n\tpkill -f x\n\tEOF\nls",
    'git commit -m "Block pkill and killall only at command position"',
    "jq -n '{\"cmd\": \"pkill -f x\"}'",
    "# pkill -f x\nls",
    "ls  # killall node",
    "echo pkill; echo killall",
    "echo $'pkill -f x'",
    'echo "$(echo pkill -f x)"',
    "man pkill",
    "which killall taskkill",
    'echo "unterminated pkill -f x',
)


def test_text_mentioning_kill_words_passes_666():
    for cmd in TEXT_ONLY:
        r = run(cmd)
        assert r.returncode == 0, cmd
        assert r.stdout == "" and r.stderr == "", cmd


AT_COMMAND_POSITION = (
    "x; pkill -f server", "x && killall node", "false || pkill -f x", "ls | killall node",
    "echo node | xargs killall", "echo $(pkill -f x)", "echo `killall node`", 'echo "$(pkill -f x)"',
    "cat <(pkill -f x)", "env FOO=1 pkill -f x", "env -u HOME killall node", "sudo pkill -f x",
    "sudo -u root killall node", "nohup pkill -f x &", "time pkill -f x", "xargs -n 1 pkill -f < names.txt",
    "FOO=1 BAR=2 pkill -f x", "/usr/bin/pkill -f x", "if true; then pkill -f x; fi",
    "while true; do killall node; done", "(pkill -f x)", "{ killall node; }", "! pkill -f x",
    "timeout 5 pkill -f x", "nice -n 5 killall node", "exec pkill -f x", "command pkill -f x",
    "bash -c 'pkill -f x'", 'sh -c "killall node"', "bash -lc 'echo a; pkill -f x'", "eval 'pkill -f x'",
    "bash <<'EOF'\npkill -f x\nEOF", "cat <<'EOF' | sh\nkillall node\nEOF", "bash <<< 'pkill -f x'",
    "env -S 'pkill -f x'", "find . -name '*.pid' -exec pkill -F {} \\;", "taskkill.exe /F /IM node.exe",
    "cmd /c taskkill /F /IM node.exe", 'powershell -Command "Stop-Process -Name node"',
    "echo ok \\\n&& pkill -f x", "cat <<'EOF'\npkill -f x\nEOF\nkillall node",
    "cat <<-EOF > x.txt\n\tdata\n\tEOF\npkill -f x", "echo 'a' \"b\" c; pkill -f x", 'pkill "unterminated',
    "kill -- -1", "kill -TERM -1", "kill -s TERM -1",
)


def test_kill_words_at_command_position_block_666():
    for cmd in AT_COMMAND_POSITION:
        r = run(cmd)
        assert r.returncode == 2, cmd
        assert "PID" in r.stderr, cmd


def test_powershell_command_position_666():
    for cmd in ("Write-Output a; Stop-Process -Name python", "Get-Process | Where-Object CPU -gt 100 | Stop-Process",
                "Get-Process node | kill", "spps -Name node", '1..3 | ForEach-Object { Stop-Process -Name "n$_" }',
                "if ($true) { Stop-Process -Name node -Force }", "Stop-Process -n node"):
        assert run(cmd, "PowerShell").returncode == 2, cmd
    for cmd in ("Get-Process node | ForEach-Object { Stop-Process -Id $_.Id }", "Stop-Process -Id 12 -Force",
                'Write-Output "Stop-Process -Name python"', "Write-Host 'Get-Process x | Stop-Process'",
                "Select-String -Pattern 'taskkill /IM' -Path notes.txt", "# Stop-Process -Name x\nGet-ChildItem"):
        r = run(cmd, "PowerShell")
        assert r.returncode == 0, cmd
        assert r.stdout == "" and r.stderr == "", cmd


def test_powershell_backtick_escape_666():
    assert run('Write-Output "a `" Stop-Process -Name x"', "PowerShell").returncode == 0
    assert run('Write-Output "a `" ; Stop-Process -Name x', "PowerShell").returncode == 0
    assert run('Write-Output "a"; Stop-Process -Name x', "PowerShell").returncode == 2


def test_long_inputs_stay_fast_666():
    body = "\n".join(f"pkill -f server{i}  # kill {i}" for i in range(3000))
    code = "\n".join(f'print("pkill -f server{i}")' for i in range(3000))
    for cmd in (f"cat > notes.txt <<'EOF'\n{body}\nEOF\necho done", f"python3 -c '{code}'"):
        start = time.monotonic()
        r = run(cmd)
        assert r.returncode == 0
        assert time.monotonic() - start < 10


def test_docs_name_the_command_word_rule_666():
    text = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("- `block-unsafe-kill` reads"))
    for word in ("command position", "heredoc", "sh -c", "eval", "kill -- -1", "Get-Process", "#666"):
        assert word in line, word


def test_unquoted_heredoc_runs_its_substitutions_666():
    blocks = ("cat <<EOF\n$(pkill -f x)\nEOF", "cat <<EOF\n`killall node`\nEOF", "cat <<-EOF\n\t$(pkill -f x)\n\tEOF")
    for cmd in blocks:
        assert run(cmd).returncode == 2, cmd
    passes = (
        "cat <<'EOF'\n$(pkill -f x)\nEOF",
        'cat <<"EOF"\n$(pkill -f x)\nEOF',
        "cat <<\\EOF\n$(pkill -f x)\nEOF",
        "cat <<EOF\npkill -f x and $HOME\nEOF",
        "cat <<EOF\n\\$(pkill -f x)\nEOF",
        "cat <<EOF\n$(echo hi) $((1+2))\nEOF",
    )
    for cmd in passes:
        r = run(cmd)
        assert r.returncode == 0 and r.stderr == "", cmd
