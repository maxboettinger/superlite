"""B245 (#950, #952, #955, #956): docs/tools.md and docs/fleet.md name the --wait default, <summary>.meta, the default pytest command, the testcmd cwd key, the launchd spawn warning, SUPERLITE_GUI_CHECK=0, wave0 stubbed_ids and the plan in-progress lines."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
LINES = [
    '`run_tests --wait` without `--timeout` sizes its wait from `<summary>.meta`, which `--background` writes beside the summary as one JSON line (`started`, `mode`, `limit`, `predicted` in seconds and `predicted_from`: `run_min in <file>` of the plan forecast or `median of N ledger runs`): the shorter of `predicted` and `limit` less the time already run, + 60 s, at least 540 s (`DEFAULT_WAIT`) and at most one harness call less 60 s (`BASH_MAX_TIMEOUT_MS` / 1000, else 600 s; half of it under 120 s); with no meta, prediction or limit it waits that whole cap, and its timeout line adds `about N s left of a predicted M s run` (or `N s past its predicted M s`) and, when the cap cut the wait, `one call waits at most C s; BASH_MAX_TIMEOUT_MS raises it` (#952).',
    '`sl testcmd` in a Python project with no configured test command fills `command` with the default pytest command run_tests runs (the pytest prefix, then the `--fast` paths or else the full-run args: none when `testpaths` is configured, `tests` when that folder exists, else `--ignore=bench`; then `-q -rP -p no:cacheprovider -o junit_family=xunit1 --junitxml={junit}`) and adds `"default_command": true`; a configured command has no `default_command` key, and with no pytest runner `command` stays null and a `testcmd:` stderr line says why (#952).',
    '`sl testcmd` prints test-cmd.json `"cwd"` as its `cwd` key, as written (`""` when unset): the folder inside the project, relative to its root (`.` the root itself), that run_tests runs `setup` and the test command in; unset, run_tests uses the `.maxapp` package folder, else the root (#950).',
    '`fleet spawn` on this Mac prints `fleet: warning: launchd session <kind>, not Aqua: a worker spawned now cannot launch or drive a Mac app window or run a macOS xcodebuild test; fallback: ...; SUPERLITE_GUI_CHECK=0 skips this check` on stderr when the test config launches or tests a Mac app (a `launch` entry for a GUI platform whose `worker` is not false, or a macOS or Catalyst `xcodebuild test` in `test` or `test_file`) and the session is not Aqua; the spawn goes on. `SUPERLITE_GUI_CHECK=0` skips that warning and the run_tests GUI preflight (#798, #955).',
    '`wave0.stubbed_ids`, the tasks Wave 0 stubs that `plan_tools prune` (through `shape.removable_edges`) and the lint `TYPES:` check count as stubbed, honours the stubs the written `briefs/wave0.json` lists: with that record a stub pick counts only when one of its files is in `stubs`; with no usable record every stub pick counts; `**Wave0:** none` gives none (#831, #955).',
    '`backlog plan` leaves out an issue another session builds (a Jira status in the In Progress category, or a worktree or a local or `origin` branch naming it) with `in progress: #N (<status, worktree or branch>): not planned, another session builds it; sl backlog plan --issues N --add plans it anyway` and the `status` reason `not planned (in progress: <label>)`; a pinned one is planned anyway with `in progress?: #N (<status, worktree or branch>): planned anyway (pinned); sl backlog skip N drops it`; a plan with nothing left says `nothing to plan: every issue is already shipped`, or `nothing to plan: every issue is already shipped or in progress` when an issue another session builds was left out (#813, #956). `SUPERLITE_IN_PROGRESS_LIVE=0` skips the Jira, worktree and branch reads (default on) and prints no `in progress:` lines; a failed read prints `in progress: Jira status not read (<error>); worktrees and branches still checked` or `in progress: worktrees and branches not read (<error>)` and plans on (#947).',
]
BULLET = '- `fleet: warning: launchd session <kind>, not Aqua: ...` (stderr, a spawn on this Mac; the spawn goes on): the test config launches or tests a Mac app and this session is not the desktop login session, so the new worker cannot launch or drive a Mac app window or run a macOS `xcodebuild test`; the line names the fallback (`swift test`, an iOS Simulator destination, or the logged-in desktop session). `SUPERLITE_GUI_CHECK=0` skips the check, and the run_tests GUI preflight with it (#798).'


def _holds_block(lines, block):
    n = len(block)
    return any(lines[i:i + n] == block for i in range(len(lines) - n + 1))


def test_tools_holds_the_lines():
    lines = TOOLS.splitlines()
    assert _holds_block(lines, LINES)
    assert not _holds_block(lines, LINES[:2] + LINES[3:])


def test_fleet_troubleshooting_names_the_warning():
    section = FLEET.split("\n## Troubleshooting\n", 1)[1].split("\n## ", 1)[0]
    assert BULLET in section.splitlines()


def test_quoted_texts_match_the_code():
    gui = (SCRIPTS / "gui_session.py").read_text(encoding="utf-8")
    assert "launchd session {kind}, not Aqua: a worker spawned now cannot launch or drive a Mac app window or run a macOS xcodebuild test; " in gui
    assert 'os.environ.get("SUPERLITE_GUI_CHECK") == "0"' in gui
    assert "fleet: warning: {warn}" in (SCRIPTS / "fleet.py").read_text(encoding="utf-8")
    rt = (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
    assert "about {left:.0f} s left of a predicted {predicted:.0f} s run" in rt
    assert "one call waits at most {cap:g} s; BASH_MAX_TIMEOUT_MS raises it" in rt
    intake = (SCRIPTS / "backlog_intake.py").read_text(encoding="utf-8")
    assert "not planned, another session builds it; sl backlog plan --issues {p} --add plans it anyway" in intake
    assert "planned anyway (pinned); sl backlog skip {p} drops it" in intake
    assert "def stubbed_ids(" in (SCRIPTS / "wave0.py").read_text(encoding="utf-8")
