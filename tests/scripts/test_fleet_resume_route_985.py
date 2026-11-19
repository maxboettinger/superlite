"""sl fleet resume runs fleet_resume through fleet.py, as restore runs fleet_restore; SDD fleet.md spells it so and names the session fleet file (#985, #786)."""
import sys
import types
import pytest
from test_fleet import world, FakeHerdr, SCRIPTS  # noqa: F401
import fleet  # noqa: E402
import fleet_resume  # noqa: E402

FOLDER = ("One fleet per session: it follows the session into the run. Its file lives in `~/.superlite/fleets/<sid>/fleet.json`, "
          "and each run it serves holds `.superlite/fleet.json` as a link to that file, which lint's binding or the first fleet command "
          "naming another run adds (stderr `fleet: this session's fleet in F now also serves R (N workers)`, after "
          "`fleet: this session's fleet moved from R to F (N workers)` when a run still kept the fleet as its own file) (#786), "
          "and before a plan, $PLAN is the worktree's .superlite folder.")


def test_resume_is_delegated(world, monkeypatch):
    calls = []
    mod = types.ModuleType("fleet_resume")
    mod.main = lambda argv: (calls.append(argv), 5)[1]
    monkeypatch.setitem(sys.modules, "fleet_resume", mod)
    assert fleet.main(["resume", "W1", "--text", "run the check", "--plan", str(world.sd)]) == 5
    assert calls == [["W1", "--text", "run the check", "--plan", str(world.sd)]]


def test_help_lists_resume(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "200")
    with pytest.raises(SystemExit):
        fleet.main(["--help"])
    out = capsys.readouterr().out
    assert "{on,off,status,spawn,placement,stop,name,report,collect,send,keys,wait,run,restore,resume}" in out
    assert "continue a stopped one-turn worker's session" in out


def test_hints_spell_fleet_resume():
    assert fleet_resume.CMD == "sl fleet resume"
    assert "fleet.py resume WID --text T [--plan P]" in fleet.__doc__


def test_sdd_fleet_md_spells_fleet_resume_and_names_the_session_file():
    text = (SCRIPTS.parent / "fleet.md").read_text(encoding="utf-8")
    assert "fleet_resume" not in text
    assert text.count('`"$SL" fleet resume Wn --text') == 2
    assert text.splitlines()[2].endswith(" Details: `docs/fleet.md`. " + FOLDER)
