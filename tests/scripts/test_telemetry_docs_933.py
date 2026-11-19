"""docs/telemetry.md matches telemetry.KINDS and COMMON; hooks.md and tools.md carry their lines (#933)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import telemetry  # noqa: E402

DOC = (ROOT / "docs" / "telemetry.md").read_text(encoding="utf-8")


def _rows():
    rows = {}
    for line in DOC.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2 and re.fullmatch(r"`[a-z_]+`", cells[0]):
            rows[cells[0].strip("`")] = re.findall(r"`([a-z_]+)`", cells[1])
    return rows


def test_docs_table_matches_kinds():
    rows = _rows()
    assert set(rows) == set(telemetry.KINDS)
    for kind, fields in telemetry.KINDS.items():
        assert tuple(rows[kind]) == fields, kind
    common = "Common fields, in order: " + ", ".join(f"`{f}`" for f in telemetry.COMMON)
    assert common in DOC


def test_docs_name_off_switches_and_rotation():
    for word in ("SUPERLITE_TELEMETRY=0", "telemetry-off", "events.jsonl", "20 MB", "events.jsonl.5",
                 "review_kind", "writer_role", "backfill", "4096"):
        assert word in DOC, word


def test_hooks_md_lists_session_end():
    assert "- `session-end`" in (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")


def test_tools_md_has_telemetry_row():
    assert "| `telemetry` |" in (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
