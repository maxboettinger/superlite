from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def test_tools_names_restore_writer_note_and_read_first():
    for s in ("fleet restore", "writer", "Output:", "--note", "Read first", "read_first", ".pid"):
        assert s in TOOLS, s


def test_fleet_md_names_restore_writer_note_and_read_first():
    for s in ("fleet restore", "writer", "Output:", "--note", "Read first", "read_first", ".pid"):
        assert s in FLEET, s
