"""fleet spawn: a research worker on this machine may name outside paths; a remote one keeps the #1015 refusal (#1158)."""
import pytest
from test_fleet import world, SCRIPTS  # noqa: F401
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import fleet_placement  # noqa: E402

LINE = "placement: research worker stays local: its brief names paths outside the project that only this machine has (#1158)"


def _brief(world, tmp_path, text=None):
    other = tmp_path / "other"; other.mkdir(exist_ok=True); (other / "spec.md").write_text("s")
    b = world.sd / "briefs" / "R1.md"; b.parent.mkdir(exist_ok=True)
    b.write_text(text if text is not None else f"Read {other}/spec.md.\n")
    return b, other


def _stub(monkeypatch, spawned):
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: spawned.append(k) or {"id": "W1"})
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)


def test_spawn_local_research_naming_outside_path_starts(world, tmp_path, monkeypatch):
    fleet.main(["on"])
    b, _ = _brief(world, tmp_path)
    spawned = []
    _stub(monkeypatch, spawned)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 0
    assert len(spawned) == 1 and not spawned[0].get("machine")


def test_spawn_pins_research_local(world, tmp_path, monkeypatch, capsys):
    fleet.main(["on"])
    b, _ = _brief(world, tmp_path)
    spawned = []
    _stub(monkeypatch, spawned)
    monkeypatch.setattr(fleet_placement, "enabled", lambda sd: True)
    monkeypatch.setattr(fleet, "_placed", lambda *a, **k: pytest.fail("placement asked"))
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 0
    assert LINE in capsys.readouterr().err
    monkeypatch.setattr(fleet_placement, "enabled", lambda sd: False)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 0
    assert LINE not in capsys.readouterr().err


def test_spawn_research_brief_without_outside_path_is_placed(world, tmp_path, monkeypatch):
    fleet.main(["on"])
    b, _ = _brief(world, tmp_path, "Answer the question.\n")
    _stub(monkeypatch, [])
    asked = []
    monkeypatch.setattr(fleet, "_placed", lambda *a, **k: asked.append(1))
    assert fleet.main(["spawn", "--role", "research", "--brief", str(b), "--plan", str(world.sd)]) == 0
    assert asked


def test_spawn_research_on_remote_machine_still_refused(world, tmp_path, monkeypatch, capsys):
    fleet.main(["on"])
    b, other = _brief(world, tmp_path)
    spawned = []
    _stub(monkeypatch, spawned)
    monkeypatch.setattr(fleet_placement, "machine_refusal", lambda *a, **k: None)
    assert fleet.main(["spawn", "--role", "research", "--machine", "mxn", "--brief", str(b), "--plan", str(world.sd)]) == 2
    assert f"{other}/spec.md; a worker cannot read them" in capsys.readouterr().err
    assert not spawned


def test_spawn_implementer_still_refused(world, tmp_path, monkeypatch, capsys):
    fleet.main(["on"])
    b, other = _brief(world, tmp_path)
    spawned = []
    _stub(monkeypatch, spawned)
    assert fleet.main(["spawn", "--role", "implementer", "--brief", str(b), "--plan", str(world.sd)]) == 2
    assert f"{other}/spec.md; a worker cannot read them" in capsys.readouterr().err
    assert not spawned


def test_docs_name_1158():
    root = SCRIPTS.parents[2]
    for rel in ("docs/fleet.md", "docs/tools.md", "skills/subagent-driven-development/fleet.md"):
        assert "#1158" in (root / rel).read_text(encoding="utf-8"), rel
    assert "#1158" in fleet.__doc__
