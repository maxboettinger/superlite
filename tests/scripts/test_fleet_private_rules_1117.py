"""A private state folder outside the project gets Read/Edit rules, not --add-dir, so no trust dialog shows (#1117)."""
from pathlib import Path
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
from test_fleet_roles_spawn import _start

pytestmark = pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")


def _list(argv):
    i = argv.index("--allowedTools") + 1
    j = i
    while j < len(argv) and not argv[j].startswith("--"):
        j += 1
    return argv[i:j]


def test_state_rules_examples():
    assert fleet.state_rules(["--agent", "a", "--disallowedTools", "AskUserQuestion"], Path("/h/sessions/s1.d/.superlite"), "implementer") == [
        "--agent", "a", "--allowedTools", "Read(//h/sessions/s1.d/.superlite/**)", "Edit(//h/sessions/s1.d/.superlite/**)", "--disallowedTools", "AskUserQuestion"]
    assert fleet.state_rules(["--permission-mode", "default", "--allowedTools", "Edit(//p/out.md)", "--disallowedTools", "Bash"], Path("/h/s"), "writer") == [
        "--permission-mode", "default", "--allowedTools", "Edit(//p/out.md)", "Read(//h/s/**)", "--disallowedTools", "Bash"]


def test_state_rules_is_idempotent():
    a = ["--agent", "a", "--allowedTools", "Bash(ls)", "--disallowedTools", "X"]
    sd = Path("/h/s")
    assert fleet.state_rules(fleet.state_rules(a, sd, "fixer"), sd, "fixer") == fleet.state_rules(a, sd, "fixer")


def test_private_state_folder_gets_rules_not_add_dir(world, tmp_path, monkeypatch):
    monkeypatch.setattr(fleet.state, "private", lambda sd: True)
    fleet.main(["on"]); other = tmp_path / "elsewhere"; other.mkdir()
    fleet.spawn(world.sd, world.plan, None, other, role="implementer")
    argv = _start(world)[2]
    base = f"/{world.sd.resolve().as_posix()}/**"
    assert "--add-dir" not in argv
    assert {f"Read({base})", f"Edit({base})"} <= set(_list(argv))


def test_private_research_and_writer_get_read_only(world, tmp_path, monkeypatch):
    monkeypatch.setattr(fleet.state, "private", lambda sd: True)
    fleet.main(["on"]); other = tmp_path / "elsewhere"; other.mkdir()
    base = f"/{world.sd.resolve().as_posix()}/**"
    fleet.spawn(world.sd, world.plan, None, other, role="research")
    out = other / "out.md"
    fleet.spawn(world.sd, world.plan, None, other, role="writer", output=str(out))
    for i in (0, 1):
        argv = _start(world, i)[2]
        assert "--add-dir" not in argv
        assert f"Read({base})" in _list(argv) and f"Edit({base})" not in argv


def test_worktree_state_folder_keeps_add_dir(world, tmp_path, monkeypatch):
    monkeypatch.setattr(fleet.state, "private", lambda sd: False)
    fleet.main(["on"]); other = tmp_path / "elsewhere"; other.mkdir()
    fleet.spawn(world.sd, world.plan, None, other, role="research")
    argv = _start(world)[2]
    assert argv[argv.index("--add-dir") + 1] == str(world.sd.resolve())
    assert f"Read(/{world.sd.resolve().as_posix()}/**)" not in argv
