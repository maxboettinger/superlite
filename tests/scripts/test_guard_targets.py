import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401


@pytest.fixture
def T(tmp_path_factory):
    return str(tmp_path_factory.mktemp("outside"))


def test_quoted_target_judged(proj, T):
    assert bash(proj, f'cd {T} && echo x > "{proj}/.superlite/orchestrator.json"').returncode == 2
    assert bash(proj, f'cd {T} && rm "{proj}/src/a.py"').returncode == 2
    assert bash(proj, f'rm "{T}/x"').returncode == 0
    assert bash(proj, f"echo x > '{proj}/src/a.py'").returncode == 2
    assert bash(proj, 'rm "$HOME/x y"').returncode == 2


def test_cd_only_when_it_moves(proj, T):
    assert bash(proj, "cd /nonexistent-dir; rm src/a.py").returncode == 2
    assert bash(proj, f"cd {T} | true; rm src/a.py").returncode == 2
    assert bash(proj, f"cd {T}; rm src/a.py").returncode == 0
    assert bash(proj, f"cd {T} && rm src/a.py").returncode == 0


def test_dots_resolved(proj, T):
    (proj / "src").mkdir()
    assert bash(proj, "cd src && rm ../b.py").returncode == 2
    assert bash(proj, f"rm ../{proj.name}/src/a.py").returncode == 2
    assert bash(proj, f"cd {T} && rm ../x").returncode == 0


def test_protected_dots_when_idle(proj):
    (proj / ".superlite" / "pool.json").unlink()
    assert bash(proj, "echo x > .superlite/./orchestrator.json").returncode == 2


def test_project_variable_expanded(proj):
    assert bash(proj, "echo x > $CLAUDE_PROJECT_DIR/.superlite/orchestrator.json").returncode == 2
    assert bash(proj, "echo x > ${CLAUDE_PROJECT_DIR}/src/a.py").returncode == 2


def test_join_absolute_part(proj, T):
    code = f"import os; open(os.path.join('{T}','{proj}/src/a.py'),'w')"
    assert bash(proj, f'python3 -c "{code}"').returncode == 2
    code = f"from pathlib import Path; (Path('{T}') / '{proj}/src/a.py').write_text('x')"
    assert bash(proj, f'python3 -c "{code}"').returncode == 2
    code = f"import os; open(os.path.join('{T}','a.py'),'w')"
    assert bash(proj, f'python3 -c "{code}"').returncode == 0
