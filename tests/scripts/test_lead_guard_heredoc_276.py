"""#276: in a fleet session (lead or worker) the backlog guard blocks `sl backlog decide|answer|start|plan` run as a
command, not the same words in a heredoc body or a quoted argument that only writes them."""
import json, os, subprocess
import pytest
from test_block_coordinator_edits import BASH, HOOK

ALLOW = [
    "cat > docs/x.md <<'EOF'\nRun `sl backlog start B1` from main.\nEOF",
    "cat > t.py <<EOF\nsl backlog decide --file f\nEOF",
    "cat > t.py <<-EOF\n\tsl backlog decide --file f\n\tEOF\nls",
    'git commit -m "docs: sl backlog start runs in main"',
    "git commit -m \"$(cat <<'EOF'\nsl backlog plan --reset\nEOF\n)\"",
    'grep -n "backlog start" commands/backlog.md',
    "printf '%s\\n' 'sl backlog answer B1' > f",
    'sl feedback add --kind bug "the hook blocks sl backlog start in a heredoc"',
    "echo x # sl backlog start",
    "gh issue create --title t --body 'sl backlog decide'",
    "cat <<\\EOF > f\n$(sl backlog start)\nEOF",
    "cat > t.py <<'EOF'\nrun(['sl', 'backlog', 'start'])\nEOF",
    "echo $((1<<2)) > f <<'EOF'\nsl backlog start\nEOF",
    'grep -rn "sl backlog start" .', 'rg "backlog decide" .',
    'git add . && git commit -m "docs: sl backlog start runs in main"', "ls . # sl backlog start",
    '"$SL" feedback add --kind bug "sl backlog start is blocked in a heredoc"', '$SL feedback add "sl backlog decide"',
]
BLOCK = [
    "bash <<'EOF'\nsl backlog start B1\nEOF",
    "sh -s <<EOF\nenv -u SUPERLITE_FLEET_WORKER sl backlog decide\nEOF",
    "echo 'sl backlog start' | bash", 'eval "sl backlog plan"', 'x="sl backlog start"; $x',
    "cat <<EOF\n$(sl backlog start)\nEOF", 'echo "$(sl backlog decide --print)"', "echo `sl backlog answer B1`",
    "ls; sl backlog start B1", "python3 -c \"import os; os.system('sl backlog start')\"",
    "cat > f.sh <<'EOF'\nsl backlog start\nEOF\nbash f.sh", 'echo "backlog start" | xargs sl',
    "(sl backlog start)", "{ sl backlog start; }", "if true; then sl backlog start; fi",
    "env -S 'sl backlog start'", "ssh host 'sl backlog start'",
    "git commit -m \"$(cat <<'EOF'\nx\nEOF\n)\" && sl backlog start",
    "sl backlog start>out", "/abs/sl backlog plan --reset",
    "cat <<'A' <<'B2'\nsl backlog start\nA\nfoo\nB2\nsl backlog plan", "sl backlog \\\nstart",
    # a << in arithmetic is a shift, not a heredoc: the next line is a real command
    "echo $((1<<2))\nsl backlog start", "x=$((1 << 3))\nsl backlog start", "((n = 1 << 2))\nsl backlog start",
    'echo "$((1<<2))"\nsl backlog start', "echo $(( $(sl backlog start) + 1 ))", "echo $((sl backlog start); true)",
    "source /dev/stdin <<'E'\nsl backlog start\nE", ". <(echo 'sl backlog start')",
    "ls; . /dev/stdin <<'E'\nsl backlog start\nE", "exec bash <<'E'\nsl backlog start\nE",
    # F-T1-2: escaped-space assignment value, a variable as the shell word
    "x=sl\\ backlog\\ start; $x", "$SHELL -c 'sl backlog start'", '"$SHELL" -lc \'sl backlog start\'',
    # F-T1-3: $( ) inside an unquoted ${ }
    "echo ${x:-$(sl backlog start)}",
    # F-T1-4: $[ ] arithmetic, << is a shift
    "echo $[1<<2]\nsl backlog start", 'echo "$[1<<2]"\nsl backlog start',
    # F-T1-5: awk, make; source/. after a reserved word
    "awk 'BEGIN{system(\"sl backlog start\")}'", "if true; then . /dev/stdin <<'E'\nsl backlog start\nE\nfi",
    "{ source /dev/stdin; } <<'E'\nsl backlog start\nE",
    # F-T1-6: a backslash before n or t is a literal backslash, not a newline
    'sl backlog pla\\n', 'sl backlog a\\nswer B1', 'sl backlog star\\t',
]


@pytest.fixture
def sd(tmp_path):
    d = tmp_path / "proj" / ".superlite"; d.mkdir(parents=True); return d


def call(sd, cmd, tool="Bash", role="lead", **extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(sd.parent), "SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": role,
              "SUPERLITE_STATE_DIR": str(sd)})
    raw = json.dumps({"session_id": "s276", "tool_name": tool, "tool_input": {"command": cmd, **extra}, "cwd": str(sd.parent)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e, cwd=sd.parent)


@pytest.mark.parametrize("cmd", ALLOW)
def test_written_text_passes(sd, cmd):
    for role in ("lead", "implementer"):
        r = call(sd, cmd, role=role)
        assert r.returncode == 0, (role, cmd, r.stderr)


@pytest.mark.parametrize("cmd", BLOCK)
def test_runs_stay_blocked(sd, cmd):
    for role in ("lead", "implementer"):
        r = call(sd, cmd, role=role)
        assert r.returncode == 2 and "runs only in the main session" in r.stderr, (role, cmd, r.stderr)


def test_long_line_keeps_the_raw_block(sd):
    assert call(sd, 'printf %s "' + "x" * 5000 + ' sl backlog start"').returncode == 2


def child_cpu():
    t = os.times()
    return t.children_user + t.children_system


@pytest.mark.skipif(os.name == "nt", reason="os.times() reports no child CPU time on Windows")
def test_large_heredoc_is_quick(sd):
    # #353: CPU time of the hook's process tree, not wall clock, which parallel suites stretch.
    # time.process_time() would count only this test process, not the hook.
    cmd = "cat > docs/big.md <<'EOF'\n" + "Run `sl backlog start B1` from the main session.\n" * 3000 + "EOF"
    t = child_cpu()
    r = call(sd, cmd)
    cpu = child_cpu() - t
    assert r.returncode == 0 and cpu < 5, (cpu, r.stderr)


def test_description_alone_passes(sd):
    assert call(sd, "ls", description="then sl backlog start").returncode == 0


def test_powershell_keeps_the_raw_match(sd):
    assert call(sd, "Write-Output 'sl backlog start'", tool="PowerShell").returncode == 2
