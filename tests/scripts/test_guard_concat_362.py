"""A Python string `+` composes a write target, so a scratch write outside the project passes (#362)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from guard_tools import targets  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")

SIGHTING = (
    "mkdir -p {S} && cd {T} && python3 - <<'EOF'\n"
    "import json\n"
    "out='{S}/'\n"
    "for l in open('t.jsonl'):\n"
    "    r=json.loads(l); m=r.get('message',{{}}); c=m.get('content') if isinstance(m,dict) else None\n"
    "    if r.get('type')=='assistant' and isinstance(c,list):\n"
    "        for b in c:\n"
    "            if b.get('type')=='tool_use' and b['name']=='Agent':\n"
    "                d=b['input'].get('description','')\n"
    "                if 'Review' in d:\n"
    "                    open(out+'prev-brief-'+d.replace(' ','_')+'.md','w').write(b['input']['prompt'])\n"
    "            if b.get('type')=='tool_use' and b['name']=='SendMessage':\n"
    "                open(out+'prev-task-msg-P4B1.md','w').write(b['input']['message']); print('P4 msg')\n"
    "EOF\n"
    "cat \"{S}/prev-task-msg-P4B1.md\""
)


def py(code):
    return targets(["python3", "-c", code])


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "P"
    (p / ".superlite").mkdir(parents=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "src").mkdir()
    return p


def hook(proj, cmd):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, cwd=proj)


@pytest.mark.parametrize("code,expected", [
    ("out='/tmp/s/'\nopen(out+'a.md','w')", ["/tmp/s/a.md"]),
    ("out = '/tmp/s'\nopen(out + '/a.md', 'w')", ["/tmp/s/a.md"]),
    ("open('/tmp/s/' + 'x' + '.md', 'w')", ["/tmp/s/x.md"]),
    ("out='/tmp/s/'\nopen(out+'b-'+d.replace(' ','_')+'.md','w')", ["/tmp/s/?"]),
    ("out='docs/plans/'\nopen(out + 'a.md', 'w')", ["docs/plans/a.md"]),
    ("p = 'src/' + 'a.py'\nopen(p, 'w')", ["src/a.py"]),
    ("import os\nopen(os.path.join('/tmp/s', 'a' + '.md'), 'w')", ["/tmp/s/a.md"]),
])
def test_string_plus_composes(code, expected):
    assert py(code) == expected


def test_plus_binds_looser_than_slash():
    assert py("from pathlib import Path\nopen(str(Path('/tmp/s') / 'a') + '.md', 'w')") == ["/tmp/s/a.md"]
    assert py("from pathlib import Path\nopen('/tmp/x' + str(Path('a') / 'b'), 'w')") == ["/tmp/xa/b"]


@pytest.mark.parametrize("code", [
    "open(name + '.md', 'w')",
    "open('src/' + name, 'w')",
    "p='a'+x\nopen(p,'w')",
    "p='a'\np+='x'\nopen(p,'w')",
    "p = 'docs/plans/' + sys.argv[1]\nopen(p, 'w')",
])
def test_unknown_piece_stays_unknown(code):
    assert py(code) == ["?"]


def test_sighting_scratch_concat_passes(proj, tmp_path):
    s, t = tmp_path / "scratch", tmp_path / "transcripts"
    t.mkdir()
    r = hook(proj, SIGHTING.format(S=s, T=t))
    assert r.returncode == 0, r.stderr


def test_concat_into_project_code_blocks(proj):
    r = hook(proj, f"python3 - <<'EOF'\nout='{proj}/src/'\nopen(out+'a.py','w').write('x')\nEOF")
    assert r.returncode == 2 and r.stderr.strip().splitlines()[-1] == "Blocked target: src/a.py"


def test_relative_concat_into_plans_passes_and_into_src_blocks(proj):
    ok = "python3 - <<'EOF'\nout='docs/plans/'\nopen(out+'a.md','w').write('x')\nEOF"
    bad = "python3 - <<'EOF'\nout='src/'\nopen(out+'a.py','w').write('x')\nEOF"
    assert hook(proj, ok).returncode == 0
    r = hook(proj, bad)
    assert r.returncode == 2 and r.stderr.strip().splitlines()[-1] == "Blocked target: src/a.py"


def test_unknown_concat_still_blocks(proj):
    r = hook(proj, "python3 - <<'EOF'\nimport sys\nopen(sys.stdin.readline() + '.md','w')\nEOF")
    assert r.returncode == 2 and "Unresolved word: ? (from python3)" in r.stderr


def test_heredoc_written_outside_not_run_passes(proj, tmp_path):
    s = tmp_path / "scratch"
    s.mkdir()
    body = "import os\nopen(P + '/src/x.py', 'w').write('x')\nprint(open('.superlite/orchestrator.json').read())\n"
    r = hook(proj, f"cd {proj}; S={s}; cat > $S/pre.py <<'PYEOF'\n{body}PYEOF")
    assert r.returncode == 0, r.stderr


def test_heredoc_script_that_runs_is_still_judged(proj, tmp_path):
    s = tmp_path / "scratch"
    s.mkdir()
    r = hook(proj, f"S={s}; cat > $S/pre.py <<'PYEOF'\nopen('src/x.py', 'w').write('x')\nPYEOF\npython3 $S/pre.py")
    assert r.returncode == 2 and r.stderr.strip().splitlines()[-1] == "Blocked target: src/x.py"


def _lits(n):
    return ", ".join(f"'f{i}'" for i in range(n))


@pytest.mark.parametrize("use", [
    "open('/tmp/s/' + p, 'w')",
    "open(Path('/tmp/s') / p, 'w')",
    "open(os.path.join('/tmp/s', p), 'w')",
    "open(f'/tmp/s/{p}', 'w')",
])
def test_over_64_combinations_are_unknown_not_cut(use):
    got = py(f"for p in ({_lits(65)}):\n    {use}")
    assert got == ["/tmp/s/?"]


@pytest.mark.parametrize("use", [
    "open('/tmp/s/' + p, 'w')",
    "open(Path('/tmp/s') / p, 'w')",
])
def test_exactly_64_combinations_still_compose(use):
    got = py(f"for p in ({_lits(64)}):\n    {use}")
    assert len(got) == 64 and "?" not in got
