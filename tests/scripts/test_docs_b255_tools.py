"""B255 (#969, #970, #972): docs/tools.md names the status worktree: line and the lean stop, the gate's bounds, refusal and review-first admission, the account, usage, brief and waits-on lines, and the run_tests row states the --wait sizing rule."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
WAIT = ("its limit without `--timeout` is the run's predicted time left + 60 s, at least 540 s (`DEFAULT_WAIT`) and at most one harness call less 60 s "
        "(`BASH_MAX_TIMEOUT_MS` / 1000, else 600 s; the `run_tests --wait` line below the table has the details)")
OLD = "its limit defaults to 540 s (`DEFAULT_WAIT`, under a 600 s Bash cap)"
LINES = [
    "`fleet status` without `--plan` adds one `worktree: fleet is on in <W>, ...` or `worktree: fleet is off in <W>, ...` line after `fleet: on` or `fleet: off` when the worktree's own "
    "`.superlite` is not the folder it read and its fleet is on where that folder's is off or the reverse (#904); `fleet stop` sends `/exit` and waits up to 10 s only for a lead, "
    "and a lean worker's pane close ends it with no wait (#930); [fleet.md](fleet.md) quotes both lines.",
    "`fleet spawn --over-limit [--max-workers N] [--min-swap-free-mb M]`: the bounds keep the override refusing at critical pressure, under M MB of free swap and at N live workers of the run "
    "(`machine limit overridden (--over-limit within ...): ...` when admitted); either flag without `--over-limit` is an error and plain `--over-limit` skips every check. A gate refusal names "
    "what drove it and ends `gave up after K checks in N s: <what>; room comes when <ways>; rerun later, or pass --over-limit`, and a waiting package or final reviewer spawn is admitted "
    "before any other (`a review spawn waits first: <what>`); [fleet.md](fleet.md) lists every part (#902).",
    "`fleet spawn` prints `accounts skipped: <name> (<why>), ...` on stderr once it picked an account, and `usage: claude-profile usage gave no report; using last readings: <name> <age> old, ...` "
    "when the usage call gave no report; a fresh one-turn worker that does not take its first brief gets it once more, then `BLOCKED: Wn <label> not sent (brief not taken after one resend)`; "
    "`fleet status` ends a busy local worker's line with ` waits on <command> <N min>` (#909).",
]


def _row(name):
    return next(line for line in TOOLS.splitlines() if line.startswith(f"| `{name}` |"))


def test_run_tests_row_states_the_wait_rule():
    row = _row("run_tests")
    assert row.count(WAIT) == 1
    assert OLD not in TOOLS and "under a 600 s Bash cap" not in TOOLS
    assert "the `defaults to 540 s` of the run_tests row" not in TOOLS


def test_tools_holds_the_lines_as_one_block():
    lines = TOOLS.splitlines()
    assert any(lines[i:i + len(LINES)] == LINES for i in range(len(lines) - len(LINES) + 1))
    assert all(lines.count(line) == 1 for line in LINES)


def test_quoted_texts_match_the_code():
    rt = (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
    assert "DEFAULT_WAIT = 540.0" in rt and "BASH_MAX_TIMEOUT_MS" in rt
    assert "want = min(expected) - (now - started) + 60.0" in rt
    assert "half of it under 120 s" in rt
