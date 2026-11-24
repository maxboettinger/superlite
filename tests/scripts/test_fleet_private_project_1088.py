"""A fleet spawned from a session's private state folder starts its workers in the launch folder's project (#1088)."""
import types
from pathlib import Path

import pytest
from test_fleet import world, SCRIPTS  # noqa: F401
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import state  # noqa: E402


@pytest.fixture
def priv(tmp_path, monkeypatch):
    home = tmp_path / "home"; psd = home / "sessions" / "s1.d" / ".superlite"; psd.mkdir(parents=True)
    proj = tmp_path / "proj"; (proj / ".git").mkdir(parents=True); (proj / "src").mkdir(); (proj / "src" / "a.py").write_text("x")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    for v in ("CLAUDE_PROJECT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(proj / "src")
    return types.SimpleNamespace(home=home, psd=psd, proj=proj, tmp=tmp_path)


def test_private_folder_takes_the_launch_git_root(priv):
    assert state.private(priv.psd) is True
    assert state.project(priv.psd).resolve() == priv.proj.resolve()


def test_claude_project_dir_wins_over_the_cwd(priv, monkeypatch):
    other = priv.tmp / "other"; (other / ".git").mkdir(parents=True); (other / "sub").mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other / "sub"))
    assert state.project(priv.psd).resolve() == other.resolve()


def test_launch_folder_outside_git_is_the_project(priv, monkeypatch):
    plain = priv.tmp / "plain"; plain.mkdir(); monkeypatch.chdir(plain)
    assert state.project(priv.psd).resolve() == plain.resolve()


def test_home_inside_a_git_checkout_still_takes_the_launch_project(priv):
    (priv.home / ".git").mkdir()
    assert state.project(priv.psd).resolve() == priv.proj.resolve()


def test_project_folder_keeps_git_root_or_parent(priv):
    a = priv.tmp / "a"; (a / ".git").mkdir(parents=True); (a / "app" / ".superlite").mkdir(parents=True)
    assert state.private(a / "app" / ".superlite") is False
    assert state.project(a / "app" / ".superlite") == a
    b = priv.tmp / "b" / ".superlite"; b.mkdir(parents=True)
    assert state.project(b) == priv.tmp / "b"


def test_outside_paths_judges_a_private_folder_against_its_project(priv):
    assert fleet.outside_paths(f"Read {priv.proj}/src/a.py.\n", priv.psd.parent, priv.psd) == []
    other = priv.tmp / "other"; other.mkdir(); (other / "x.md").write_text("x")
    assert fleet.outside_paths(f"Read {other}/x.md.\n", priv.psd.parent, priv.psd) == [f"{other}/x.md"]


def test_spawn_from_private_folder_starts_in_the_project(world, tmp_path, monkeypatch):
    home = tmp_path / "home"; psd = home / "sessions" / "s1.d" / ".superlite"; psd.mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_HOME", str(home)); monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    (world.proj / ".git").mkdir(); (world.proj / "src").mkdir(); (world.proj / "src" / "a.py").write_text("x")
    assert fleet.main(["on", "--plan", str(psd)]) == 0
    brief = psd / "briefs" / "R1.md"; brief.parent.mkdir(); brief.write_text(f"Read {world.proj}/src/a.py and answer.\n")
    seen = {}

    def fake_spawn(sd, plan, tier, project, **k):
        seen["project"] = Path(project)
        return {"id": "W1"}
    monkeypatch.setattr(fleet, "spawn", fake_spawn)
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--plan", str(psd)]) == 0
    assert seen["project"].resolve() == world.proj.resolve()


def test_fleet_takes_every_project_from_state_project():
    src = (SCRIPTS / "fleet.py").read_text(encoding="utf-8")
    assert "state.git_root(sd) or sd.parent" not in src
    assert src.count("state.project(sd)") >= 10
    assert "(#1088)" in fleet.__doc__
