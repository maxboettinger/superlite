import pytest

from test_block_coordinator_edits import bash, proj, run  # noqa: F401
from test_guard_false_blocks import human_proj


@pytest.fixture(params=["active", "human"])
def state(request, proj, tmp_path_factory):  # noqa: F811
    if request.param == "active":
        return proj
    return human_proj(tmp_path_factory.mktemp("h"))


def test_exclude_allowed_in_both_states(state):
    assert bash(state, "echo '.claude/worktrees/' >> .git/info/exclude").returncode == 0
    assert run(state, "Write", {"file_path": ".git/info/exclude"}).returncode == 0


def test_worktree_add_with_exclude_passes(proj):  # noqa: F811
    assert bash(proj, "git worktree add wt -b b && echo wt >> .git/info/exclude").returncode == 0


@pytest.mark.parametrize("cmd", [
    "echo x > .git/hooks/pre-commit",
    "echo x >> .git/config",
    "echo x > .git/info/../hooks/pre-commit",
    "echo x > .git/info/exclude.bak",
])
def test_other_git_paths_stay_blocked(state, cmd):
    assert bash(state, cmd).returncode == 2


def test_block_message_names_the_target(proj):  # noqa: F811
    r = bash(proj, "echo x > src/a.py")
    assert r.returncode == 2 and r.stderr.splitlines()[-1] == "Blocked target: src/a.py"
    r = bash(proj, "echo a > docs/plans/p.md; echo b > lib/b.py")
    assert r.returncode == 2 and r.stderr.splitlines()[-1] == "Blocked target: lib/b.py"
    r = bash(proj, "git stash pop")
    assert r.returncode == 2 and r.stderr.splitlines()[-1] == "Blocked command: git stash pop"


def test_protected_file_message_unchanged(proj):  # noqa: F811
    r = run(proj, "Write", {"file_path": ".superlite/orchestrator.json"})
    assert r.returncode == 2
    assert "never written directly" in r.stderr
    assert "Blocked target" not in r.stderr and "Blocked command" not in r.stderr


@pytest.mark.parametrize("cmd, last", [
    ("echo x > 'my dir/a.py'", "Blocked target: my dir/a.py"),
    ("echo x | tee src/a.py", "Blocked target: src/a.py"),
    ("cp a.txt src/b.py", "Blocked target: src/b.py"),
    ("rm src/a.py", "Blocked target: src/a.py"),
    ("sed -i s/a/b/ src/a.py", "Blocked target: src/a.py"),
    ("echo x > ./src/a.py", "Blocked target: src/a.py"),
    ("git stash pop", "Blocked command: git stash pop"),
    ("python3 -c \"open('src/q.py','w').write('x')\"", "Blocked target: src/q.py"),
    ("cat <<EOF > src/h.py\nx\nEOF", "Blocked target: src/h.py"),
])
def test_last_line_is_clean_and_project_relative(proj, cmd, last):  # noqa: F811
    r = bash(proj, cmd)
    assert r.returncode == 2 and r.stderr.splitlines()[-1] == last
    assert not any(c in r.stderr for c in "\x03\x05\x06")


def test_tool_path_with_space_and_absolute_path(proj):  # noqa: F811
    r = run(proj, "Write", {"file_path": "my dir/a.py"})
    assert r.stderr.splitlines()[-1] == "Blocked target: my dir/a.py"
    r = run(proj, "Write", {"file_path": str(proj / "src" / "a.py")})
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


def test_exclude_lookalikes_stay_blocked(state):
    for cmd in ("echo x > .git/info/exclude/x", "echo x > .git/info/./hooks/x", "cp a .git/hooks/x",
                "tee .git/config </dev/null"):
        assert bash(state, cmd).returncode == 2


def test_no_run_blocks_nothing_new(tmp_path):
    (tmp_path / ".superlite").mkdir()
    assert bash(tmp_path, "echo x > src/a.py").returncode == 0
    assert bash(tmp_path, "echo x >> .git/info/exclude").returncode == 0
