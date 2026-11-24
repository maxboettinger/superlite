"""spawn's --note check applies fleet_io.brief_outside, the one text rule of the brief checks (#1107)."""
import re
import pytest
from test_fleet import world, SCRIPTS  # noqa: F401
import fleet  # noqa: E402


def _other(tmp_path):
    other = tmp_path / "other"; other.mkdir(); (other / "x.md").write_text("s")
    return other


def _spawn(world, note):
    return fleet.main(["spawn", "--for-review", "T1", "--note", str(note), "--plan", str(world.plan)])


def test_note_copying_standing_note_passes(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    note = world.proj / "note.md"
    note.write_text(f"Fenced:\n```\ncat {other}/x.md\n```\nF1 bug quote: `see {other}/x.md here`\n")
    _spawn(world, note)
    assert "names paths outside" not in capsys.readouterr().err


def test_note_naming_missing_path_passes(world, capsys):
    fleet.main(["on"])
    note = world.proj / "note.md"; note.write_text("Deploy lives in /nonexistent-host/srv/app today.\n")
    _spawn(world, note)
    assert "names paths outside" not in capsys.readouterr().err


def test_note_naming_existing_outside_path_still_refused(world, capsys, tmp_path):
    fleet.main(["on"])
    other = _other(tmp_path)
    note = world.proj / "note.md"; note.write_text(f"Compare with {other}/x.md.\n")
    assert _spawn(world, note) == 2
    err = capsys.readouterr().err
    assert f"error: note {note.resolve()} names paths outside" in err and f"{other}/x.md" in err


def test_note_check_calls_brief_outside():
    src = (SCRIPTS / "fleet.py").read_text()
    assert "brief_outside(" in src and not re.search(r"outside_paths\(note", src)
