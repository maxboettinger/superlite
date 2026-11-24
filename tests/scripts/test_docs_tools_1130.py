"""docs/tools.md names what B320-B329 shipped (#1113-#1120, #1132-#1134); each quoted message is checked against the script printing it (#1130)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINES = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

NEW_ROWS = [  # (anchor row prefix, new row prefix)
    ("| `run_tests` |", "| `run_tests` --fast filter and uv env (#1119, #1120, #1133) |"),
    ("| `pt_review` |", "| `pt_review packet` cuts and fences (#1118) |"),
    ("| `state` |", "| `state` plugin folder (#1116) |"),
    ("| `backlog_run` |", "| `backlog_run` note and cap 0 (#1113, #1114) |"),
    ("| `backlog_ship` |", "| `backlog_ship` lock checks (#1134) |"),
]
UV, CUTS, STATE, NOTE, LOCK = (new for _, new in NEW_ROWS)
ANCHORS = ["run_tests", "pt_review", "state", "build_prime", "backlog", "backlog_run", "backlog_ship", "ship_lock", "fleet"]
BRIEF = "| `fleet` brief checks (#1089, #1094, #1107) |"
NAMED = [  # (row prefix, text it holds exactly once)
    (UV, "is in no test target, so it maps to no test filter; skipped, never widened to the whole suite (#1119)"),
    (UV, "uv run --frozen --project <root>"),
    (UV, "(#1133)"),
    ("| `run_tests` |", ".pnp.cjs"),
    (CUTS, "[… N chars cut …]"),
    (CUTS, "at least 3"),
    (STATE, "SUPERLITE_PROJECT_DIR"),
    (STATE, "state.Refused"),
    ("| `build_prime` |", "state.plan_dir"),
    ("| `backlog_run` |", "sl backlog note /dev/null"),
    (NOTE, "BLOCKED: sl backlog note runs only in the main session"),
    (NOTE, "no free slot for B (cap 0); rerun once the cap: line shows room"),
    (NOTE, "waiting for room: cap 0; start retried every 300 s until --timeout"),
    (LOCK, "refused: uncommitted changes in the worktree ("),
    (LOCK, "lock held: fix it, then run sl backlog ship B lock again"),
    ("| `ship_lock` |", "LIVE_GRACE_MS"),
    (BRIEF, "placement: research worker stays local: ... (#1111)"),
    (BRIEF, "(#1132)"),
]
CODE = [  # (script, literal its source holds)
    ("run_tests.py", "is in no test target, so it maps to no test filter; skipped, never widened to the whole suite (#1119)"),
    ("_pyrun.py", "the tests may import that folder's package, not {root}'s (#1133)"),
    ("pt_review.py", "chars cut \\u2026]"),
    ("state.py", "SUPERLITE_PROJECT_DIR"),
    ("state.py", "lies inside the superlite plugin ("),
    ("backlog.py", "BLOCKED: sl backlog note runs only in the main session"),
    ("backlog_run.py", "start retried every {a.retry} s until --timeout"),
    ("backlog_run.py", "); rerun once the cap: line shows room"),
    ("backlog_ship.py", "refused: uncommitted changes in the worktree ("),
    ("backlog_ship.py", "lock held: fix it, then run sl backlog ship {bid} lock again"),
    ("ship_lock.py", "LIVE_GRACE_MS = 120000"),
    ("fleet_placement.py", "placement: research worker stays local: "),
]


def test_new_rows_follow_their_anchor():
    for anchor, new in NEW_ROWS:
        rows = [i for i, ln in enumerate(LINES) if ln.startswith(new)]
        assert len(rows) == 1, new
        first = next(i for i, ln in enumerate(LINES) if ln.startswith(anchor))
        assert rows[0] > first, new


def test_anchor_rows_stay_one_each():
    for a in ANCHORS:
        assert sum(ln.startswith(f"| `{a}` |") for ln in LINES) == 1, a


def test_new_rows_stay_one_table_line():
    for _, new in NEW_ROWS:
        line = next(ln for ln in LINES if ln.startswith(new))
        assert line.endswith(" |") and line.count(" | ") == 1, new


def test_rows_name_the_shipped_text():
    bad = []
    for prefix, text in NAMED:
        line = next((ln for ln in LINES if ln.startswith(prefix)), "")
        if line.count(text) != 1:
            bad.append((prefix, text[:60]))
    build = next(ln for ln in LINES if ln.startswith("| `build_prime` |"))
    assert "when when" not in build
    brief = next(ln for ln in LINES if ln.startswith(BRIEF))
    assert "spawn does not check it" not in brief
    assert "--note /dev/null" not in next(ln for ln in LINES if ln.startswith("| `backlog_run` |")).replace("sl backlog note /dev/null", "")
    assert not bad, bad


def test_quoted_text_is_in_the_scripts():
    bad = [(s, t[:60]) for s, t in CODE if t not in (SCRIPTS / s).read_text(encoding="utf-8")]
    assert not bad, bad
