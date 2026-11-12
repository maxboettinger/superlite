# tests/scripts/test_docs_607_fleet.py
from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")


def test_batch_leads_name_ship_and_end_items():
    for s in ("cleanup-cmd.json", "plan --reset", "OPEN", "Decisions:", "Attribution:", "no-change", "Unverified:", "Kind: design", "Refs #N", "ship B notes", "reopened"):
        assert s in DOC, s


def test_trees_and_disk_gate():
    for s in ("20 GB", "50 GB", "SUPERLITE_DISK_FLOOR_GB", "--module-cache-hours", "-derivedDataPath", "SUPERLITE_DERIVED_DATA_PATH", "orphan"):
        assert s in DOC, s


def test_fleet_commands_roles_and_state():
    for s in ("fresh pane", "--wait", "already collected", "(reported:", "dead", "checker", "Fleet state read:", "state_dir", "fleet: off (moved to", "low memory"):
        assert s in DOC, s
    assert "retried once on the same pane after 3 s" not in DOC
