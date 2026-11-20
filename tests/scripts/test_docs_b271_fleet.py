"""B271 (#1008): docs/fleet.md "Remote machines" names #997's retake of a missing stop-hook snapshot on the worker's machine; each quoted text is checked against fleet_remote_collect.py."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
LINES = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8").splitlines()
SCRIPT = ROOT / "skills" / "subagent-driven-development" / "scripts" / "fleet_remote_collect.py"

NAMED = [  # text the "## Remote machines" section holds exactly once
    "is first retaken on the worker's machine",
    "(workspace `sl:collect Wn`)",
    "`sl remote_apply snapshot --ref R`",
    "every 2 s for up to 120 s (`RETAKE_S`)",
    "`collected.retaken`",
    "`remote worker Wn's stop hook took no snapshot (remote_apply snapshot failed or ran past 30 s); collect retook it on L: <sha>`",
    "`; retaking it there failed: <reason>; sl fleet collect Wn retries`",
    "(#997)",
]
CODE = [  # literal fleet_remote_collect.py holds
    "RETAKE_S = 120",
    "POLL_S = 2",
    'hc.create_workspace(f"sl:collect {wid}"',
    "remote_apply snapshot --ref {q(ref)}",
    'out["collected"]["retaken"] = True',
    "'s stop hook took no snapshot (remote_apply snapshot failed or ran past 30 s); collect retook it on {label}: {snap}",
    "; retaking it there failed: {why}; sl fleet collect {wid} retries",
]


def section(title):
    start = LINES.index(title)
    end = next((i for i in range(start + 1, len(LINES)) if LINES[i].startswith("## ")), len(LINES))
    return "\n".join(LINES[start:end])


@pytest.mark.parametrize("text", NAMED)
def test_section_names_it_once(text):
    assert section("## Remote machines").count(text) == 1


@pytest.mark.parametrize("literal", CODE)
def test_quoted_texts_match_the_code(literal):
    assert literal in SCRIPT.read_text(encoding="utf-8")
