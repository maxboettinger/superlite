import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "P"
    (p / ".superlite").mkdir(parents=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    return p


@pytest.fixture
def scratch(tmp_path):
    s = tmp_path / "S"
    s.mkdir()
    return s


def bash(proj, cmd):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, cwd=proj)


def script(s, arg):
    return (
        f"cat > {s}/patch.py <<'EOF'\nimport sys\nfrom pathlib import Path\n"
        "plan = Path(sys.argv[1])\nplan.write_text(plan.read_text().replace('a','b'))\n"
        f"EOF\npython3 {s}/patch.py {arg}"
    )


def test_scratch_script_edits_plan_allowed(proj, scratch):
    assert bash(proj, script(scratch, "docs/superpowers/plans/x.md")).returncode == 0


def test_scratch_script_on_source_blocked(proj, scratch):
    assert bash(proj, script(scratch, "src/app.py")).returncode == 2


def test_heredoc_to_outside_path_allowed(proj, scratch):
    cmd = f"cat > {scratch}/p.py <<'EOF'\nopen('src/a.py','w').write('x')\nEOF"
    assert bash(proj, cmd).returncode == 0


def test_heredoc_into_project_code_blocked(proj):
    cmd = "cat > p.py <<'EOF'\nprint(1)\nEOF"
    assert bash(proj, cmd).returncode == 2


def _w(s, body, arg):
    return f"cat > {s}/x.py <<'EOF'\nimport sys\nfrom pathlib import Path\n{body}\nEOF\npython3 {s}/x.py {arg}"


@pytest.mark.parametrize("body", [
    "p = Path('.') / sys.argv[1]\np.write_text('x')",
    "p = Path('docs/plans') / '../../src/a.py'\np.write_text('x')",
    "p = Path(sys.argv[1]) / 'a.py'\np.write_text('x')",
    "p = 'docs/plans/' + sys.argv[1]\np.write_text('x')",
])
def test_composed_path_not_literal_blocked(proj, scratch, body):
    assert bash(proj, _w(scratch, body, "src/a.py")).returncode == 2


def test_path_argv_plan_still_allowed(proj, scratch):
    assert bash(proj, _w(scratch, "p = Path(sys.argv[1])\np.write_text('x')", "docs/plans/x.md")).returncode == 0
