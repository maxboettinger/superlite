"""fleet spawn refuses a machine the project excludes; fleet placement names the exclusions (#1096)."""
import json, sys
from test_fleet import world  # noqa: F401 (fixture)
from test_fleet_placement_spawn import pl, disp  # noqa: F401 (fixtures)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_placement as fp  # noqa: E402


def cfg(proj, data):
    p = proj / ".superlite" / "placement.json"; p.write_text(data if isinstance(data, str) else json.dumps(data))
    return p


def test_explicit_excluded_machine_refused(pl, capsys):
    p = cfg(pl.proj, {"exclude": ["box"]})
    assert fleet.main(["spawn", "--machine", "box", "--role", "research", "--brief", str(pl.brief)]) == 2
    assert f"error: machine box is excluded from this project's fleet by {p}; drop --machine or pass --machine local (#1096)" in capsys.readouterr().err
    assert pl.remote == [] and pl.local == []


def test_explicit_excluded_machine_refused_for_dispatch(disp, capsys):
    cfg(disp.proj, {"exclude": ["BOX"]})
    disp.lines = [("T3", "fresh tier=sonnet agent=superlite:implementer")]
    assert fleet.main(["spawn", "--for-dispatch", "--machine", "box", "--plan", str(disp.plan2)]) == 2
    assert disp.remote == [] and disp.local == [] and disp.fsends == []


def test_explicit_other_machine_still_spawns(pl):
    cfg(pl.proj, {"exclude": ["mxn"]})
    assert fleet.main(["spawn", "--machine", "box", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert [x[2] for x in pl.remote] == ["box"]


def test_machine_local_ignores_a_broken_config(pl):
    cfg(pl.proj, "{")
    assert fleet.main(["spawn", "--machine", "local", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.remote == [] and len(pl.local) == 1


def test_broken_config_refuses_an_explicit_remote(pl, capsys):
    p = cfg(pl.proj, "{")
    assert fleet.main(["spawn", "--machine", "box", "--role", "research", "--brief", str(pl.brief)]) == 2
    assert f"error: {p}: not valid JSON; fix it before a remote spawn (#1096)" in capsys.readouterr().err


def placement_out(world, tmp_path, monkeypatch, capsys, data):
    home = tmp_path / "home"; home.mkdir(); monkeypatch.setenv("SUPERLITE_HOME", str(home))
    (home / "machine.json").write_text(json.dumps({"remote_room": ["x"], "remote_tree": ["y"]}))
    monkeypatch.setattr(fp, "room", lambda sd, **k: {"local": {"state": "ready", "room": 12}, "box": {"state": "ready", "room": 10},
                                                     "far": {"state": "ready", "room": 4}})
    fleet.main(["on"]); capsys.readouterr()
    p = cfg(world.proj, data)
    assert fleet.main(["placement"]) == 0
    return p, capsys.readouterr().out


def test_placement_command_names_exclusions(world, tmp_path, monkeypatch, capsys):
    p, out = placement_out(world, tmp_path, monkeypatch, capsys, {"exclude": ["mxn", "box"]})
    assert f"excluded: box, mxn ({p})" in out.splitlines()
    assert "box: ready room 10 (excluded)" in out and "far: ready room 4\n" in out and "local: ready room 12\n" in out


def test_placement_command_names_a_broken_config(world, tmp_path, monkeypatch, capsys):
    p, out = placement_out(world, tmp_path, monkeypatch, capsys, "[]")
    assert f"excluded: {p}: not a JSON object; every worker of this project stays local" in out.splitlines()


def test_fleet_doc_and_docs_name_the_config():
    assert "(#1096)" in fleet.__doc__
    text = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert ".superlite/placement.json" in text and "(#1096)" in text
