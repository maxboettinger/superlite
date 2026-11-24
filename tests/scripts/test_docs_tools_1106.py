"""docs/tools.md names what B311-B323 shipped (#1086, #1089, #1091-#1095, #1097, #1107, #1108, #1121); each quoted message is checked against the script printing it (#1106)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINES = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

NEW_ROWS = [  # (anchor row prefix, new row prefix)
    ("| `plan_tools` |", "| `plan_tools lint` OUTSIDE (#1086) |"),
    ("| `commit_task` |", "| `commit_task` reviewer hold (#1097) |"),
    ("| `run_tests` |", "| `run_tests` xcsift log lines and unittest (#1091, #1092) |"),
    ("| `fleet` |", "| `fleet` brief checks (#1089, #1094, #1107) |"),
    ("| `fleet_io` |", "| `fleet wait` signed out (#1093, #1108) |"),
]
OUT, HOLD, XC, BRIEF, WAIT = (new for _, new in NEW_ROWS)
NAMED = [  # (row or paragraph prefix, text it holds exactly once)
    (OUT, "`WARNING: OUTSIDE: line N names a path outside the project: P; plan text reaches worker briefs (Global constraints, the review packet) and the #1015 check refuses it there: copy the file into <root>/.superlite/briefs/ and name the copy, or drop the path (#1086)`"),
    (OUT, "lint's exit code is unchanged"),
    ("| `plan_tools` |", "its parenthesis names only the parts present, in the order slow tests, existing tests, review rounds (`plan_tools.EXTRA_PARTS`, #1121)"),
    ("| `predict` |", "a `Tests: slow` task adds `slow_min` to `extra_min`"),
    (HOLD, "`left uncommitted (in the review scope of busy Wn (label); commit_task Tn again once it is done): F`"),
    (HOLD, "`nothing to commit; held for busy Wn: F`"),
    (HOLD, "reads only fixer, package-reviewer and writer briefs"),
    (XC, "`run_tests: WARNING: xcsift listed N console log line(s) under errors[], not counted as failures: <first>`"),
    (XC, "`Ran N tests in Xs`"),
    (BRIEF, "`Standing note: a research worker may read these outside paths read-only; ...`"),
    (BRIEF, "and would overwrite a report the worker writes there; name another file, such as <rd>/<id>-full.md (#1094)`"),
    (WAIT, "(signed out: account <acct> shows the Claude Code sign-in screen; sign in there, then respawn)`"),
    ("Main steps (#674):", "matches no Jira key of this batch (K1, K2)`"),
    ("Main steps (#674):", "matches K1 and K2; write the key`"),
    ("Main steps (#674):", "is not one of this batch's issues (K1, K2)`"),
]
CODE = [  # (script, literal its source holds)
    ("plan_tools.py", "names a path outside the project: {tok}; plan text reaches worker briefs (Global constraints, the review packet) and the #1015 check refuses it there: copy the file into "),
    ("plan_tools.py", "/briefs/ and name the copy, or drop the path (#1086)"),
    ("plan_tools.py", 'EXTRA_PARTS = (("slow_min", "slow tests"), ("suite", "existing tests"), ("review", "review rounds"))'),
    ("predict.py", 'out["slow_min"] = slow_min'),
    ("commit_task.py", 'f"left uncommitted (in the review scope of busy {names}; commit_task {tid} again once it is done): {f}"'),
    ("commit_task.py", 'f"nothing to commit; held for busy {'),
    ("commit_task.py", 'BRIEF_ROLES = ("fixer", "package-reviewer", "writer")'),
    ("run_tests.py", "console log line(s) under errors[], not counted as failures: {"),
    ("run_tests.py", 'print(f"run_tests: WARNING: {note}"'),
    ("testcmd.py", r'r"^Ran (\d+) tests? in \d+(?:\.\d+)?s$"'),
    ("backlog_brief.py", 'REF_READ = "Standing note: a research worker may read these outside paths read-only; '),
    ("fleet.py", "and would overwrite a report the worker writes there; name another file, such as {rd}/{rid}-full.md (#1094)"),
    ("fleet_io.py", " (signed out: account {w.get('account')} shows the Claude Code sign-in screen; sign in there, then respawn)"),
    ("backlog_checks.py", "matches no Jira key of this batch ("),
    ("backlog_checks.py", "; write the key"),
    ("backlog_checks.py", "is not one of this batch's issues ("),
]


def test_new_rows_follow_their_anchor():
    for anchor, new in NEW_ROWS:
        rows = [i for i, ln in enumerate(LINES) if ln.startswith(new)]
        assert len(rows) == 1, new
        first = next(i for i, ln in enumerate(LINES) if ln.startswith(anchor))
        assert rows[0] > first, new


def test_anchor_rows_stay_one_each():
    for anchor in [a for a, _ in NEW_ROWS] + ["| `predict` |"]:
        assert sum(ln.startswith(anchor) for ln in LINES) == 1, anchor


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
    assert not bad, bad


def test_quoted_text_is_in_the_scripts():
    missing = [(s, t[:60]) for s, t in CODE if t not in (SCRIPTS / s).read_text(encoding="utf-8")]
    assert not missing, missing
