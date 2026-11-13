from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_backlog_md_run():
    t = _read("skills/subagent-driven-development/backlog.md")
    for s in ("backlog run", "--window", "fleet restore", "re-arm"):
        assert s in t, s


def test_command_run():
    t = _read("commands/backlog.md")
    assert "backlog run" in t and "--window" in t


def test_fleet_md_zero_timeout():
    t = _read("docs/fleet.md")
    assert "--timeout 0" in t
    assert "worker ids repeat across worktrees" in t


def test_tools_md_append_only():
    lines = _read("docs/tools.md").rstrip("\n").split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith("`experiment set --arms A,B`")]
    assert idx
    after = "\n".join(lines[idx[-1] + 1:])
    assert idx[-1] < len(lines) - 1
    for s in ("backlog run", "--window", "fleet wait --timeout 0"):
        assert s in after, s


_OLD_HANDOVER = '`"$SL" backlog status`, then `"$SL" backlog wait`'
_NEW_HANDOVER = '`"$SL" backlog status`, then `"$SL" backlog run`'
_OLD_BG_WAIT = '`"$SL" backlog wait` as a background command'


def test_handover_names_run():
    for rel in ("commands/backlog.md", "skills/subagent-driven-development/backlog.md"):
        t = _read(rel)
        assert _NEW_HANDOVER in t, rel
        assert _OLD_HANDOVER not in t, rel
        assert _OLD_BG_WAIT not in t, rel
        assert "Run `\"$SL\" backlog wait` as a background" not in t, rel


def test_run_exit_codes_documented():
    t = _read("skills/subagent-driven-development/backlog.md")
    assert "Exit codes 0 (run end, needs_decision, parked and TIMEOUT), 2 (start refusal), 3 (Herdr missing)" in t
    assert "2 (refusal or a batch needs main)" not in t
