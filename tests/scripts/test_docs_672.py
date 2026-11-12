"""Docs name the disk floor and the simulator cleanup (#672)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text()
TOOLS = (ROOT / "docs" / "tools.md").read_text().splitlines()

SENTENCES = [
    "A `machine:` line also shows while free disk is below the warn level (50 GB, `SUPERLITE_DISK_WARN_GB`), naming that level or the floor; a `B simulators owed: ...` line names simulators a ship cleanup could not delete (status re-reads them and drops the gone ones).",
    "Below the free-disk floor (20 GB on the main checkout's volume, `SUPERLITE_DISK_FLOOR_GB`; `--over-limit` does not skip it) a batch is not started: one `BLOCKED: waiting for disk: B not started: <free> GB free on <path>, below the <floor> GB floor; ...` line, exit 2, and the batch keeps its state, so a later `start` starts it once space is free (#672).",
    "- Simulators: append the UDID of each simulator you or a worker creates to `<worktree>/.superlite/simulators.txt` (one per line; a name works when only one device has it). The ship cleanup (merge, `ship B done`, `plan --reset`, `reset`) shuts down and deletes each listed one before the project cleanup command (`B simulators: removed N: ...`); one it could not delete is kept as the batch's `simulators_owed` and named by `wait` and `status` (#672).",
    "Simulators a lead lists in `.superlite/simulators.txt` are removed by superlite itself (Lead: Simulators).",
]


def test_backlog_md_sentences():
    for s in SENTENCES:
        assert s in BACKLOG, s[:50]


def test_simulators_bullet_follows_adjacent_fixes():
    lines = BACKLOG.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("- Adjacent fixes:"))
    assert lines[i + 1].startswith("- Simulators:")


def test_tools_row_after_backlog_brief():
    i = next(k for k, l in enumerate(TOOLS) if l.startswith("| `backlog_brief` |"))
    row = TOOLS[i + 1]
    assert row.startswith("| `backlog_run` disk floor, simulators (#672) | ")
    for word in ("BLOCKED: waiting for disk:", "simulators.txt", "simulators_owed", "SUPERLITE_SIMCTL"):
        assert word in row
