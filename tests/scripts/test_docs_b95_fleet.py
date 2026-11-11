"""B95 (#450, B87-B91 follow-ups): docs/fleet.md names what shipped in 1.5.82 to 1.5.101."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")


def section(title):
    head = f"## {title}\n"
    assert head in FLEET, title
    return FLEET.split(head, 1)[1].split("\n## ", 1)[0]


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_commands_section():
    has(section("Commands"), "--for-review", "--package", "review: Tn", "--strict-mcp-config", "dropped",
        "another account", "ASKED", "concerns=N", "--brief", "--full", "Files changed:")


def test_batch_leads_section():
    has(section("Batch leads (backlog mode)"), "--add", "overlap:", "--note FILE", "note:", "parked",
        "tell B --text T", "--approve-ship --source prompt", '"by"', "followups=N", "undone=M",
        "--autocompact", "Files other open batches own", "incident resolve --kind")


def test_troubleshooting_trust_dialog():
    has(section("Troubleshooting"), "Yes, I trust this folder", "lead")
