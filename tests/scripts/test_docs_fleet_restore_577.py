# tests/scripts/test_docs_fleet_restore_577.py
from pathlib import Path

FLEET = (Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/fleet.md").read_text(encoding="utf-8")


def para(start):
    return next(p for p in FLEET.split("\n\n") if p.lstrip("- ").startswith(start))


def test_fleet_md_names_restore():
    p = para("Herdr restart:")
    for s in ('"$SL" fleet restore --plan $PLAN', "--resume", "re-arm:", "test run ended:", "before any `fleet wait`"):
        assert s in p


def test_fleet_md_names_writer():
    b = next(l for l in FLEET.splitlines() if l.startswith("- Writer:"))
    for s in ("--role writer", "--brief", "Output:", "every other write is refused"):
        assert s in b


def test_fleet_md_names_note():
    b = next(l for l in FLEET.splitlines() if l.startswith("- Package reviewer:"))
    assert "--note FILE" in b and "## Coordinator notes" in b


def test_fleet_md_names_read_first():
    sec = FLEET.split("## Implementers", 1)[1].split("## Other roles", 1)[0]
    assert "**Read first:**" in sec and "read_first" in sec and "test-cmd.json" in sec
