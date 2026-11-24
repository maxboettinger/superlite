"""#1116: sl state never lands inside the plugin's skills folder; an explicit value there is refused (exit 2)."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_session_state import SCRIPTS, state  # noqa: F401

REAL_SCRIPTS = SCRIPTS
A = "a1"


@pytest.fixture
def plug(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    (plugin / ".git").mkdir(parents=True)
    skills = plugin / "skills"
    scripts = skills / "subagent-driven-development" / "scripts"
    scripts.mkdir(parents=True)
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    monkeypatch.setattr(state, "PLUGIN_SKILLS", skills)
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", A)
    monkeypatch.chdir(scripts)
    monkeypatch.setenv("PWD", str(scripts))
    return tmp_path, plugin, scripts, proj


def test_resolve_from_plugin_goes_to_session_project(plug, monkeypatch):
    _, _, scripts, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.resolve() == proj / ".superlite"
    assert not (scripts / ".superlite").exists()


def test_claude_project_dir_wins(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(tmp / "other"))
    assert state.resolve() == proj / ".superlite"


def test_resolve_from_plugin_without_project_uses_private_folder(plug):
    assert state.resolve() == state.private_dir(A)


def test_resolve_from_plugin_without_project_or_session_refuses(plug, monkeypatch, capsys):
    monkeypatch.delenv("SUPERLITE_SESSION_ID")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    with pytest.raises(state.Refused) as e:
        state.resolve()
    assert e.value.code == 2
    assert "lies inside the superlite plugin" in capsys.readouterr().err


def test_owned_project_folder_goes_private(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp / "elsewhere"))
    state.bind(proj / ".superlite", sid="b2")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.resolve() == state.private_dir(A)


def test_bare_plan_from_plugin_skips_the_walk(plug, monkeypatch):
    _, plugin, _, proj = plug
    (plugin / ".superlite").mkdir()
    (plugin / ".superlite" / "fleet.json").write_text("{}\n")
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.plan_dir(".superlite") == proj / ".superlite"


def test_explicit_plan_inside_plugin_refused(plug):
    _, _, scripts, _ = plug
    with pytest.raises(state.Refused):
        state.plan_dir(str(scripts / ".superlite"))
    with pytest.raises(state.Refused):
        state.plan_dir(str(scripts))


def test_state_dir_env_inside_plugin_refused(plug, monkeypatch):
    _, _, scripts, _ = plug
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(scripts / ".superlite"))
    with pytest.raises(state.Refused):
        state.resolve()


def stray(scripts, gate=False):
    sd = scripts / ".superlite"
    sd.mkdir(exist_ok=True)
    b = state.home() / "sessions" / A
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text(f"{sd}\n\n{scripts}\n")
    if gate:
        (sd / "orchestrator.json").write_text('{"mode": "ai"}\n')
        (sd / "session").write_text(A + "\n")
    return sd


def test_bound_ignores_a_binding_into_the_plugin(plug, monkeypatch):
    _, _, scripts, proj = plug
    stray(scripts)
    assert state.bound() is None
    monkeypatch.chdir(proj)
    monkeypatch.setenv("PWD", str(proj))
    assert state.resolve() == state.Path(".superlite")


def test_bind_refuses_a_plugin_folder(plug):
    _, _, scripts, _ = plug
    with pytest.raises(state.Refused):
        state.bind(scripts / ".superlite", sid=A)
    assert not (scripts / ".superlite").exists()
    assert not (state.home() / "sessions" / A).exists()


def test_bind_moves_a_stray_gate_out_of_the_plugin(plug):
    _, _, scripts, proj = plug
    sd = stray(scripts, gate=True)
    state.bind(proj / ".superlite", sid=A)
    assert (proj / ".superlite" / "orchestrator.json").exists()
    assert not (sd / "orchestrator.json").exists()
    first = (state.home() / "sessions" / A).read_text().splitlines()[0]
    assert first == str(proj / ".superlite")


def test_for_plan_unstarted_plan_stays_out_of_the_plugin(plug, monkeypatch):
    _, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    plan = proj / "docs" / "plans" / "p.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("x\n")
    assert state.for_plan(str(plan)) == proj / ".superlite"


def test_where_names_the_plugin_redirect(plug, monkeypatch, capsys):
    _, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.main(["where"]) == 0
    assert capsys.readouterr().out == f"{proj}/.superlite (cwd inside the plugin; session project)\n"


def test_orchestrator_set_from_the_real_scripts_folder(tmp_path):
    """Runs a copy of the scripts folder laid out as an installed plugin: the real folder sits in a worktree whose own
    run would answer step 2, and a test must never write that run's gate."""
    import shutil
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    scripts = tmp_path / "plugin" / "skills" / "subagent-driven-development" / "scripts"
    shutil.copytree(REAL_SCRIPTS, scripts, ignore=shutil.ignore_patterns(".superlite", "__pycache__"))
    env = {k: v for k, v in os.environ.items()
           if k not in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR") and not k.startswith("SUPERLITE_FLEET_")}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_SESSION_ID=A,
               SUPERLITE_PROJECT_DIR=str(proj), PWD=str(scripts))
    r = subprocess.run([sys.executable, str(scripts / "orchestrator.py"), "set", "ai"],
                       cwd=scripts, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (proj / ".superlite" / "orchestrator.json").exists()
    assert not (scripts / ".superlite").exists()
