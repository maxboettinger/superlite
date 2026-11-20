import json
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
from test_fleet import REAL, fleet, world  # noqa: F401,E402  (world is a fixture)

fake_only = pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")


def _start(world, i=0):
    return [c for c in world.fh.calls if c[0] == "start_agent"][i][2]


def _rule():
    return "Read(/" + fr.SKILLS.as_posix() + "/**)"


def test_skills_is_the_plugin_skills_folder():
    assert (fr.SKILLS / "writing-plans" / "SKILL.md").is_file()


def test_rule_joins_the_existing_allow_list():
    argv = ["--permission-mode", "default", "--allowedTools", "Edit(//r/x.md)", "--disallowedTools", "Bash"]
    assert fr.skills_read(argv, "/p/skills") == ["--permission-mode", "default", "--allowedTools", "Edit(//r/x.md)",
                                                 "Read(//p/skills/**)", "--disallowedTools", "Bash"]
    assert argv == ["--permission-mode", "default", "--allowedTools", "Edit(//r/x.md)", "--disallowedTools", "Bash"]


def test_rule_gets_its_own_list_before_the_deny_list():
    assert fr.skills_read(["--agent", "a", "--disallowedTools", "X"], "/p/skills/") == [
        "--agent", "a", "--allowedTools", "Read(//p/skills/**)", "--disallowedTools", "X"]


def test_rule_goes_last_without_either_list():
    assert fr.skills_read(["--agent", "a"], "/p/skills") == ["--agent", "a", "--allowedTools", "Read(//p/skills/**)"]


def test_rule_is_added_once():
    once = fr.skills_read(["--agent", "a", "--disallowedTools", "X"], "/p/skills")
    assert fr.skills_read(once, "/p/skills") == once


def test_skills_inside_the_project_add_nothing(tmp_path):
    (tmp_path / "skills").mkdir()
    argv = ["--agent", "a", "--disallowedTools", "X"]
    assert fr.skills_read(argv, tmp_path / "skills", project=tmp_path) == argv
    assert "--allowedTools" in fr.skills_read(argv, tmp_path / "skills", project=tmp_path / "proj")


def test_default_skills_is_read_at_call_time(monkeypatch, tmp_path):
    monkeypatch.setattr(fr, "SKILLS", tmp_path / "plug" / "skills")
    assert fr.skills_read(["--agent", "a"]) == ["--agent", "a", "--allowedTools", "Read(/" + (tmp_path / "plug" / "skills").as_posix() + "/**)"]


@fake_only
def test_spawn_writer_has_one_allow_list(world):
    fleet.main(["on"])
    out = world.proj / "out.md"
    fleet.spawn(world.sd, world.plan, None, world.proj, role="writer", output=str(out))
    argv = _start(world)
    i = argv.index("--allowedTools")
    assert argv.count("--allowedTools") == 1
    assert argv[i + 1:i + 3] == ["Edit(/" + out.as_posix() + ")", _rule()]
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["launch"]["argv"] == argv


@fake_only
def test_spawn_implementer_reads_plugin_skills(world):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = _start(world)
    i = argv.index("--allowedTools")
    assert argv[i + 1] == _rule() and i < argv.index("--disallowedTools")


@fake_only
def test_spawn_in_the_plugin_root_adds_no_rule(world, monkeypatch):
    (world.proj / "skills").mkdir()
    monkeypatch.setattr(fr, "SKILLS", (world.proj / "skills").resolve())
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, None, world.proj, role="research")
    assert _rule() not in _start(world)
