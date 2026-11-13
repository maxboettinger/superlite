"""Docs name the hooks `sl autocommit apply` runs (B181)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs" / "tools.md"
FINISH_MD = ROOT / "skills" / "finishing-a-development-branch" / "SKILL.md"
COMMIT_MD = ROOT / "commands" / "commit.md"

HOOKS = (
    "; before HEAD moves, `apply` runs the project's commit hooks for every commit it writes, as a plain `git commit` would (`git hook run`, so `core.hooksPath` and config hooks count; git before 2.36 runs the hook file): `pre-commit` with `GIT_INDEX_FILE` naming a temporary index that holds that commit's tree (HEAD stays at the run's start, so a later commit's index diff also shows the earlier tasks' changes), then `prepare-commit-msg` and `commit-msg` on the message, whose edits are kept; a failing hook prints `apply: the <hook> hook failed (exit N) for <title>`, and a `pre-commit` that changes the staged files or a message left empty stops it too; each stop leaves HEAD, the index and the checkpoints unchanged, so a rerun after the fix applies the same checkpoints; `post-commit` runs once after HEAD moved and its exit status is ignored; there is no `--no-verify`"
)
PROBE_LINE = (
    "A `run=` probe entry runs in a scratch `HOME` and working folder, without `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK` or other credential variables; `probe_run` exits 2 on a generated adapter whose `run=` predates that sandbox (`probe_run: adapter's run= predates the sandbox; rebuild with plan_tools adapter`), and plan lint fails `PROBE: run=<cmd> has a dry-run flag` and `PROBE: run=<cmd> runs <tool>` and warns `WARNING: PROBE: run=<cmd> names \"<word>\"` (#711)."
)
FAST_LINE = (
    "A `run_tests --fast` run whose paths are all dropped runs the whole command, still labelled fast (summary mode, ledger, no unit stamp), and unless `-m`, pass-through arguments or an honoured marker narrow it, it passes the full-run gate like a full run: `machine.json` admission, else the toolchain's full-suite lock; `\"lock\": false` skips it (#714)."
)
FINISH = (
    "which runs the project's commit hooks (`pre-commit`, `prepare-commit-msg`, `commit-msg`) for each commit before HEAD moves, refuses when commits since the run touched checkpointed files, a checkpointed file changed again or a hook failed (HEAD and the checkpoints stay as they were: fix the cause, run it again), and leaves unrelated changes uncommitted; give that Bash call a 600000 ms timeout when the project's `pre-commit` runs its tests;"
)
COMMIT = (
    "it runs the project's commit hooks for each commit before HEAD moves (give the Bash call a 600000 ms timeout when the project's `pre-commit` runs its tests); if it refuses (HEAD moved, a checkpointed file was edited again or a hook failed: HEAD and the checkpoints stay unchanged), print why and stop;"
)


def test_autocommit_row_names_the_hooks():
    rows = [l for l in TOOLS.read_text().splitlines() if l.startswith("| `autocommit` |")]
    assert len(rows) == 1
    row = rows[0]
    assert HOOKS in row
    assert row.count(" | ") == 1
    assert row.rstrip().endswith("|")


def test_end_lines():
    lines = TOOLS.read_text().splitlines()
    assert PROBE_LINE in lines
    assert FAST_LINE in lines


def test_finish_and_commit_texts():
    finish = FINISH_MD.read_text()
    assert FINISH in finish
    assert "which refuses only when" not in finish
    assert COMMIT in COMMIT_MD.read_text()


def test_quoted_strings_exist():
    plan_tools = ROOT / "skills" / "subagent-driven-development" / "scripts" / "plan_tools.py"
    probe = ROOT / "skills" / "subagent-driven-development" / "probes" / "probe_run.py"
    assert "has a dry-run flag" in plan_tools.read_text()
    assert "adapter's run= predates the sandbox; rebuild with plan_tools adapter" in probe.read_text()
