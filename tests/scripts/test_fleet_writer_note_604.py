"""fleet spawn: the writer role needs a brief with an Output: line; --note adds coordinator notes to a review brief (#604)."""
import sys
from pathlib import Path
import pytest
from test_fleet import world, FakeHerdr, SCRIPTS  # noqa: F401
import fleet  # noqa: E402


def test_writer_output_examples(tmp_path):
    root, sd = tmp_path / "r", tmp_path / "r" / ".superlite"
    sd.mkdir(parents=True)
    b = tmp_path / "b.md"
    b.write_text("Write the plan.\nOutput: `docs/plans/x.md`\n")
    assert fleet.writer_output(str(b), root, sd) == root / "docs/plans/x.md"
    b.write_text("Write the plan.\n")
    with pytest.raises(ValueError) as e:
        fleet.writer_output(str(b), root, sd)
    assert str(e.value) == f"writer brief {b.resolve()} names no Output: <file> line"
    b.write_text("Output: /etc/x\n")
    with pytest.raises(ValueError) as e:
        fleet.writer_output(str(b), root, sd)
    assert str(e.value) == f"writer output /etc/x is outside {root} and {sd}"


def test_writer_output_inside_state_dir_is_allowed(tmp_path):
    root, sd = tmp_path / "r", tmp_path / "r" / ".superlite"
    sd.mkdir(parents=True)
    b = tmp_path / "b.md"
    b.write_text(f"Output: {sd}/out/a.md\n")
    assert fleet.writer_output(str(b), root, sd) == sd / "out/a.md"


def test_writer_spawn_needs_brief(world, capsys):
    fleet.main(["on"])
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "writer", "--plan", str(world.sd)]) == 2
    assert "error: --role writer needs --brief naming its Output: file" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_writer_spawn_passes_output(world, monkeypatch):
    fleet.main(["on"])
    brief = world.proj / "brief.md"
    brief.write_text("Do it.\nOutput: out.md\n")
    got = {}
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: (got.update(k), {"id": "W1"})[1])
    import fleet_io
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)
    assert fleet.main(["spawn", "--role", "writer", "--brief", str(brief), "--plan", str(world.sd)]) == 0
    assert got["output"] == str(world.proj.resolve() / "out.md")


def test_writer_spawn_bad_output_is_exit_2(world, capsys):
    fleet.main(["on"])
    brief = world.proj / "brief.md"
    brief.write_text("Output: /etc/x\n")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--role", "writer", "--brief", str(brief), "--plan", str(world.sd)]) == 2
    assert "error: writer output /etc/x is outside" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def _review_stubs(world, monkeypatch):
    import fleet_io
    monkeypatch.setattr(fleet_io, "ledger_commits", lambda p: {"T1": "abc"})
    monkeypatch.setattr(fleet_io, "review_brief", lambda *a, **k: "BRIEF\n")
    monkeypatch.setattr(fleet_io, "send_brief", lambda *a, **k: None)
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: {"id": "W1"})
    monkeypatch.setattr(fleet, "stop", lambda *a, **k: [])
    fleet.fs.save(world.sd, {**fleet.fs.load(world.sd), "workers": {"W1": {"state": "ready"}}})


def test_note_appends_coordinator_notes(world, monkeypatch):
    fleet.main(["on"])
    _review_stubs(world, monkeypatch)
    assert fleet.for_review(world.sd, world.plan, world.proj, ["T1"], note="check X\n") == 0
    text = (world.sd / "briefs" / "review-T1.md").read_text()
    assert text == "BRIEF\n\n## Coordinator notes\n\nThese notes add to the review above; review every task and file it lists all the same.\n\ncheck X\n"


def test_empty_note_adds_nothing(world, monkeypatch):
    fleet.main(["on"])
    _review_stubs(world, monkeypatch)
    fleet.for_review(world.sd, world.plan, world.proj, ["T1"], note="  \n")
    assert (world.sd / "briefs" / "review-T1.md").read_text() == "BRIEF\n"


def test_note_needs_review_form(world, capsys):
    fleet.main(["on"])
    note = world.proj / "n.md"; note.write_text("x")
    n = len(world.fh.calls)
    assert fleet.main(["spawn", "--note", str(note), "--plan", str(world.sd)]) == 2
    assert "error: --note is for --for-review or --package" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_note_missing_file_is_exit_2(world, capsys):
    fleet.main(["on"])
    n = len(world.fh.calls)
    miss = world.proj / "nope.md"
    assert fleet.main(["spawn", "--for-review", "T1", "--note", str(miss), "--plan", str(world.sd)]) == 2
    assert f"error: note not found: {miss.resolve()}" in capsys.readouterr().err
    assert len(world.fh.calls) == n


def test_writer_output_rejects_symlink_escape(tmp_path):
    root, sd = tmp_path / "r", tmp_path / "r" / ".superlite"
    sd.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    b = tmp_path / "b.md"
    b.write_text("Output: link/a.md\n")
    with pytest.raises(ValueError):
        fleet.writer_output(str(b), root, sd)
