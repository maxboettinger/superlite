"""Docs name the hooks `sl autocommit apply` runs (B181); the #711 and #714 texts sit in their rows (B187)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs" / "tools.md"
FINISH_MD = ROOT / "skills" / "finishing-a-development-branch" / "SKILL.md"
COMMIT_MD = ROOT / "commands" / "commit.md"

HOOKS = (
    "; before HEAD moves, `apply` runs the project's commit hooks for every commit it writes, as a plain `git commit` would (`git hook run`, so `core.hooksPath` and config hooks count; git before 2.36 runs the hook file): `pre-commit` with `GIT_INDEX_FILE` naming a temporary index that holds that commit's tree (HEAD stays at the run's start, so a later commit's index diff also shows the earlier tasks' changes), then `prepare-commit-msg` and `commit-msg` on the message, whose edits are kept; a failing hook prints `apply: the <hook> hook failed (exit N) for <title>`, and a `pre-commit` that changes the staged files or a message left empty stops it too; each stop leaves HEAD, the index and the checkpoints unchanged, so a rerun after the fix applies the same checkpoints; `post-commit` runs once after HEAD moved and its exit status is ignored; there is no `--no-verify`"
)
LANGUAGE = ROOT / "docs" / "language.md"
PROBE_ROW = (
    "a `run=` entry runs in a scratch `HOME` and working folder, without `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK` or other credential variables, and `probe_run` exits 2 on a generated adapter whose `run=` predates that sandbox (`probe_run: adapter's run= predates the sandbox; rebuild with plan_tools adapter`) (#711);"
)
LINT_PROBE = (
    "Lint fails a `run=` probe entry with `PROBE: run=<cmd> has a dry-run flag` or `PROBE: run=<cmd> runs <tool>` (a tool that reaches outside the machine, such as `gh`, `git`, `ssh` or `curl`) and warns `WARNING: PROBE: run=<cmd> names \"<word>\"` for a word such as `deploy`, `publish` or `push`, since probes run every `run=` entry for real with fuzzed arguments (#711)."
)
FAST_ROW = (
    "a full run (no `--fast`, no `-m`, no `**Tests:** cmd=`), and a `--fast` run whose paths are all dropped (it runs the whole command, still labelled fast: summary mode, ledger, no unit stamp) unless `-m`, pass-through arguments or an honoured marker narrow it (#714), passes the full-run gate (the `machine.json` admission below, else the lock; `\"lock\": false` skips both): it first takes the machine-wide full-suite lock `~/.superlite/locks/full-suite-<toolchain>.lock`"
)
FAST_LANG = (
    "ignores the `--fast` paths and runs whole, still labelled fast, and unless `-m`, pass-through arguments or an honoured marker narrow it, passes the full-run gate like a full run (`~/.superlite/machine.json` admission, else the toolchain's full-suite lock; `\"lock\": false` skips it); `run_tests` prints"
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


def _row(name):
    rows = [l for l in TOOLS.read_text().splitlines() if l.startswith(f"| `{name}` |")]
    assert len(rows) == 1, name
    return rows[0]


def test_rows_name_the_sandbox_and_the_gate():
    assert PROBE_ROW in _row("probe_run")
    assert LINT_PROBE in _row("plan_tools")
    assert FAST_ROW in _row("run_tests")
    for name in ("probe_run", "plan_tools", "run_tests"):
        r = _row(name)
        assert r.count(" | ") == 1 and r.rstrip().endswith("|"), name


def test_language_names_the_gate():
    text = LANGUAGE.read_text()
    assert FAST_LANG in text
    assert "still labelled fast; `run_tests` prints" not in text


def test_end_lines_moved_into_the_rows():
    lines = TOOLS.read_text().splitlines()
    assert not any(l.startswith(("A `run=` probe entry runs", "A `run_tests --fast` run whose paths")) for l in lines)
    assert lines[-1].startswith("Backlog rules are split by reader")
    assert TOOLS.read_text().count("predates that sandbox") == 1


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
