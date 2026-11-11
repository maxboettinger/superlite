# tests/scripts/test_fleet_names_wiring_467.py
import hashlib, json
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="names are read from the in-process fake")


def _starts(world):
    return [c[1] for c in world.fh.calls if c[0] == "start_agent"]


@pytest.fixture
def reg(tmp_path, monkeypatch):
    monkeypatch.setattr(fleet.fs, "_registry", lambda: tmp_path / "reg")


def test_fleet_on_labels_the_workspace_with_the_run_name(world, reg):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    assert json.loads((world.sd / "fleet.json").read_text())["label"] == "sl:proj-main"
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert next(c for c in world.fh.calls if c[0] == "create_workspace")[1] == "sl:proj-main"


def test_spawn_names_the_worker_by_repo_worktree_and_id(world, reg):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _starts(world) == ["sl-proj-main-w1"]
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["name"] == "sl-proj-main-w1"


def test_spawn_adds_the_run_hash_when_the_name_is_taken(world, reg):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    world.fh.agent_rows = [{"name": "sl-proj-main-w1", "agent_status": "idle", "pane_id": "w1:p1"}]
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    h = hashlib.sha1(str(world.proj.resolve()).encode()).hexdigest()[:4]
    assert _starts(world) == [f"sl-proj-main-{h}-w1"]


def test_no_agent_list_keeps_the_readable_name(world, reg, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    def boom():
        raise world.fh.HerdrError("server_unavailable", "no server")
    monkeypatch.setattr(world.fh, "agents", boom)
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _starts(world) == ["sl-proj-main-w1"]


def test_lead_is_named_by_its_worktree(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    repo = tmp_path / "superlite"; gd = repo / ".git" / "worktrees" / "superlite-b81-fleet-wait"; gd.mkdir(parents=True)
    wt = repo / ".claude" / "worktrees" / "superlite-b81-fleet-wait"; wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert r["name"] == "sl-superlite-b81-fleet-wait-lead" == _starts(world)[0]


def test_fleet_name_prints_the_full_name(world, capsys):
    fleet.main(["name", "T3"])
    assert capsys.readouterr().out == "sl:proj-main-T3\n"
    fleet.main(["name", "final-reviewer", "--plan", str(world.sd)])
    assert capsys.readouterr().out == "sl:proj-main-final-reviewer\n"
    fleet.main(["name"])
    assert capsys.readouterr().out == "sl:proj-main\n"
