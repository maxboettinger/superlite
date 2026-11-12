# tests/scripts/test_docs_552_reap.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_offers_reap_flag():
    t = _read("commands/setup.md")
    assert '"CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP": "1"' in t
    assert "Setting it from a shell command has no effect." in t


def test_fleet_md_names_the_stop():
    t = _read("skills/subagent-driven-development/fleet.md")
    assert "A lead runs it in the foreground" in t
    assert "in the foreground (under the 600000 ms Bash limit)" in t
    assert "may run it in the foreground" not in t


def test_backlog_command_restarts_in_foreground():
    t = _read("commands/backlog.md")
    assert "backlog wait --timeout 540" in t
    assert "reports every lead that ended while none ran" in t
