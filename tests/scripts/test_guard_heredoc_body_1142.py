"""#1142: in a fleet session the backlog guard reads a quoted heredoc that a lone Python runs as its program as Python:
`sl backlog decide|answer|start|plan` in its string literals or comments is data, unless the code can run text or
another command of the call is a runner."""
import json, os, subprocess, sys
from pathlib import Path
import pytest
from test_block_coordinator_edits import BASH, HOOK

JUDGE = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts" / "guard_judge.py"

SIGHTING = ("cd /tmp/w; python3 - <<'EOF'\np='docs/fleet.md'\nt=open(p).read()\n"
            "b=\"`run end: still goes into every later lead brief; sl backlog start --note /dev/null clears it`.\"\n"
            "assert t.count(b)==1\nt=t.replace(b,\"`sl backlog note /dev/null clears it`.\")\nopen(p,'w').write(t)\nEOF\n"
            "/abs/sl run_tests --fast tests/scripts/test_docs_fleet_1130.py --task T2 --background")

ALLOW = [
    SIGHTING,
    "python3 - <<'EOF'\nopen('docs/x.md', 'w').write('Run sl backlog start B1 from main.')\nEOF",
    "python3 <<'EOF'\nprint('sl backlog plan --reset')\nEOF",
    'python3 -u - <<"EOF"\nt = """sl backlog decide --file f"""\nEOF',
    "python3 - <<\\EOF\n# sl backlog answer B1\nx = 1\nEOF",
    "python - <<'EOF'\nopen('a.md','w').write(f'sl backlog start {1}')\nEOF\ngit add a.md && git commit -m x",
    "python3.12 - <<'PY'\ns = 'sl backlog start'\nPY",
    "python3 - <<'EOF' > out.md\nprint('sl backlog start')\nEOF",
    "python3 - <<'EOF' > /dev/null\nprint('sl backlog plan')\nEOF",
]
BLOCK = [
    "python3 - <<'EOF'\nimport os\nos.system('sl backlog start')\nEOF",
    "python3 - <<'EOF'\nimport subprocess\nsubprocess.run('sl backlog start', shell=True)\nEOF",
    "python3 - <<'EOF'\nexec('import os; os.system(\"sl backlog plan\")')\nEOF",
    "python3 - <<'EOF'\nfrom os import system\nsystem('sl backlog decide')\nEOF",
    "python3 - <<EOF\nprint('sl backlog start')\nEOF",
    "python3 - <<'EOF'\nopen('f.sh','w').write('sl backlog start')\nEOF\nbash f.sh",
    "python3 - <<'EOF'\nopen('f.sh','w').write('sl backlog start')\nEOF\n./f.sh",
    "python3 - <<'EOF' | sh\nprint('sl backlog start')\nEOF",
    "python3 - <<'EOF'\nprint('sl backlog start')\nEOF\nmake test",
    "python3 x.py <<'EOF'\nsl backlog start\nEOF",
    "python3 -c 'import sys; print(sys.stdin.read())' <<'EOF'\nsl backlog start\nEOF",
    "python3 -m code <<'EOF'\nsl backlog start\nEOF",
    "$(python3 - <<'EOF'\nprint('sl backlog start')\nEOF\n)",
    "python3 - <<'EOF'\nx = '''sl backlog start\nEOF",
    "python3 - <<'EOF'\nsl backlog start\nEOF",
    "node - <<'EOF'\nconsole.log('sl backlog start')\nEOF",
    "bash <<'EOF'\necho 'sl backlog start' > d.md\nEOF",
    "python3 - <<'EOF' > f.sh\nprint('sl backlog start')\nEOF\n./f.sh",
    "python3 - <<'EOF'\nopen('f'+'.sh','w').write('sl backlog start')\nEOF\n./f.sh",
    "python3 - <<'EOF'\nopen('f'+'.sh','w').write('sl backlog start')\nEOF\nX=./f.sh; $X",
    "python3 - <<'EOF' > $T\nprint('sl backlog start')\nEOF",
    "python3 - <<'EOF'\nprint('sl backlog start')\nEOF\nbin/x",
]


@pytest.fixture
def sd(tmp_path):
    d = tmp_path / "proj" / ".superlite"; d.mkdir(parents=True); return d


def call(sd, cmd, role="lead", **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(sd.parent), "SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": role,
              "SUPERLITE_STATE_DIR": str(sd)}, **env)
    raw = json.dumps({"session_id": "s1142", "tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(sd.parent)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e, cwd=sd.parent)


@pytest.mark.parametrize("cmd", ALLOW)
def test_python_heredoc_strings_pass(sd, cmd):
    for role in ("lead", "implementer"):
        r = call(sd, cmd, role=role)
        assert r.returncode == 0, (role, cmd, r.stderr)


@pytest.mark.parametrize("cmd", BLOCK)
def test_runs_stay_blocked(sd, cmd):
    for role in ("lead", "implementer"):
        r = call(sd, cmd, role=role)
        assert r.returncode == 2 and "runs only in the main session" in r.stderr, (role, cmd, r.stderr)


def test_block_line_unchanged(sd):
    r = call(sd, "python3 - <<'EOF'\nimport os\nos.system('sl backlog start')\nEOF")
    assert "Matched: the heredoc <<EOF, which python3 in the same command runs." in r.stderr, r.stderr


def test_judge_without_ack_keeps_block(sd, tmp_path):
    fake = tmp_path / "fakepy"
    fake.write_text("#!/bin/sh\ncat >/dev/null\nexit 0\n"); fake.chmod(0o755)
    r = call(sd, SIGHTING, SUPERLITE_PYTHON=str(fake))
    assert r.returncode == 2 and "runs only in the main session" in r.stderr, r.stderr


def judge(code):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e["SUPERLITE_GUARD_NONCE"] = "n1142"
    return subprocess.run([sys.executable, "-I", "-X", "utf8", str(JUDGE), "--py-data"], input=code,
                          capture_output=True, text=True, env=e)


@pytest.mark.parametrize("code,ok", [
    ("t = 'sl backlog start'\n", True),
    ("# sl backlog plan\n", True),
    ("open('a.md', 'w').write(f'sl Backlog Decide {1}')\n", True),
    ("import os\nos.system('sl backlog start')\n", False),
    ("sl backlog start\n", False),
    ("x = '''sl backlog start\n", False),
    ("getattr(__import__('os'), 'system')('sl backlog answer')\n", False),
])
def test_py_data_judge(code, ok):
    r = judge(code)
    assert (r.returncode == 0 and "guard: ok n1142" in r.stdout) == ok, (code, r.returncode, r.stdout, r.stderr)
    assert r.returncode in (0, 1), r.stderr


def test_py_data_in_process():
    sys.path.insert(0, str(JUDGE.parent))
    import guard_judge
    assert guard_judge.py_data("t = 'sl backlog start'\n") is True
    assert guard_judge.py_data("import os\nos.system('sl backlog start')\n") is False
    assert guard_judge.py_data("sl backlog start\n") is False
