"""B67 (#401): docs/tools.md names what shipped in 1.5.63 to 1.5.69."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

RT = "; `--wait` keeps stdout one JSON document and ends with a stderr summary line `tests (<mode>): P passed, F failed[, S skipped][; error: E]` (the line cuts E at 150 characters, the saved summary `error` at 400); its limit defaults to 540 s (`DEFAULT_WAIT`, under a 600 s Bash cap), and a timeout prints `tests: no result yet after T s [(pid N still running)]; run again: <cmd>`; runner output goes to temp files, so a leftover child holding stdout no longer blocks the summary; a test-cmd.json `{only_testing}` placeholder is refused before the run when git lists no `*.swift`, `*.xcodeproj/*` or `*.xcworkspace/*` file (exit 2, `test-cmd.json uses {only_testing}, the Xcode (Swift) placeholder, ...` naming the detected language's `{files}` form; no incident; `--background` refuses in the parent); incident closing (#380): no rule closes an entry logged at or after the run's start, a green `--task Tn` run closes Tn's `-` entries and re-logs other tasks' open entries there (a stretch holding a no-result stays open), a green `--full` run without `--task` closes every `run_tests` test-failure location, and a `--fast` run without `--task` closes nothing"
CT = "An owned file that a checkpoint of this plan holds and git status no longer lists (a new file deleted, or a file back to its HEAD content) is staged again when it differs from the newest checkpoint; a restored one prints `restored F (back to its HEAD content)` on stderr. `--plan P` changes into P's checkout (`state.git_root(P)`, as `autocommit` and `trees` do) when it differs from the cwd, after making `--plan`, `--ledger`, `--log`, `--pool` and the run-folder defaults absolute against the caller's cwd; `--also` and `--claim` stay repo-relative (an absolute one is made relative to P's checkout), and a P outside any checkout keeps the cwd."
FLEET = "; `report Wn [Wm ...]` prints the reports `fleet wait` saved, read-only (a report label such as `T3` or `FR1` works too; several ids print a `== <id> <path>` line before each; a busy, blocked or unknown id, or one with no collected report, prints an `error:` line on stderr and exits 1 while the others still print); every `fleet` subcommand refuses an explicit `--plan` that is no plan file or folder, or whose state folder cannot be created (exit 2, `error: --plan P: ...`, before anything runs)"
ACCOUNTS = "| `accounts` | Account choice for fleet workers from `claude-profile usage --json` and `list --json`; `sl accounts [--tier MODEL]` prints one headroom line per account, `claude1 ok 5h=12% weekly=40%` or `claude2 skip 5-hour 95%` (the reason spawn skips it; `--tier` adds that model's scoped weekly cap), and exits 3 without usage data |"
PT = "; a `run_tests` test failure is outdated when its test file, a `conftest.py` above it, or a changed-since-base `.py` module it imports changed (mtime) after the run: it leaves section 1 and the open count (the packet can still take the fast path) and shows in section 4 as `- OUTDATED: <test> (<file> changed after this run; the full suite decides)` or `- OUTDATED incident: <file>:<line> <context> (<file> changed after it)` (at most 30 lines; agent-logged failures are never outdated); when a changed test file would be cut from section 8, the full diffs of every changed test file go to the tests shard `<packet stem>-tests.md` (cap `AUTO_MAX_TOKENS`, or `--max-tokens`), named in the packet head by a `Tests shard: K changed test file(s) are not in section 8 (truncated: test diffs over the size limit; read <abs> in full)` line and on stdout by a second `wrote` line, and a packet without a shard deletes an old one; the contract check searches a task's source files, then its owned test files"
PLAN_TOOLS = "Lint warns `WARNING: IMPORT: Tn consumes <item> from Tm, but <Type> is declared in <targets>, which target <tg> may not import (<Package.swift>) dependencies: <deps>` (a warning, never an issue) when a seam's Produces type is declared only in SwiftPM targets that the consumer's target does not list in its `Package.swift` dependencies; the same warning reads Python `import-linter` contracts (`setup.cfg`, `.importlinter`, `pyproject.toml`) and workspace `package.json` packages in TypeScript, and a Python or TypeScript producer is checked against its home module. Python `acyclic_siblings` contracts are checked against the code's current imports (a planned import must not close a cycle between siblings); a custom contract type, or a `pyproject.toml` config on a Python without `tomllib` (3.10), is not checked and prints `NOTE: IMPORT: ...`. A TypeScript package's `tsconfig.json` `references` and its `compilerOptions.paths` aliases (through relative `extends`) count as dependencies. The header line `**Edges:** hard (<why>)` keeps every Consumes edge in the task graph. A `PROBE: <kind>=<target> imports Python, but ...` issue says a `call=` or `serve=` probe names Python in a plan whose owners have no Python file (use `run=` or `**Probe entry:** none (<why>)`), and `WARNING: PLATFORM: Tn has code behind #if ...` says a build for the host platform skips that code. `lint --stable` rebuilds a stale generated probe adapter and prints `ADAPTER: rebuilt <path> (the plan's Probe entries changed)`, or `ADAPTER: removed <path> (the plan has no Probe entry lines)`; plain `lint` prints `RUN: <sl> plan_tools adapter --plan P (the probe adapter is stale: ...)` and leaves the file."


def row(name):
    rows = [ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |")]
    assert len(rows) == 1, name
    return rows[0]


def test_rows_keep_table_shape():
    for name in ("run_tests", "commit_task", "fleet", "accounts", "pt_review", "plan_tools"):
        r = row(name)
        assert r.count(" | ") == 1 and r.endswith(" |"), name


def test_run_tests_row():
    assert row("run_tests").endswith("naming the tree" + RT + " |")


def test_commit_task_row():
    assert row("commit_task").endswith("always commits. " + CT + " |")


def test_fleet_row():
    assert row("fleet").endswith("(see `docs/fleet.md`)" + FLEET + " |")


def test_accounts_row():
    assert row("accounts") == ACCOUNTS


def test_pt_review_row():
    assert row("pt_review").endswith("the cap grows by these sections" + PT + " |")


def test_plan_tools_row():
    assert row("plan_tools").endswith("(`<stem>.build-report.md`/`.json`). " + PLAN_TOOLS + " |")


def test_quoted_strings_exist_in_code():
    rt = (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
    assert "DEFAULT_WAIT = 540.0" in rt and "no result yet after" in rt and "test-cmd.json uses {only_testing}, the Xcode (Swift) placeholder" in rt
    assert "back to its HEAD content)" in (SCRIPTS / "commit_task.py").read_text(encoding="utf-8")
    pt = (SCRIPTS / "pt_review.py").read_text(encoding="utf-8")
    assert "Tests shard: " in pt and "- OUTDATED: " in pt and "- OUTDATED incident: " in pt
    assert "WARNING: IMPORT: " in (SCRIPTS / "plan_tools.py").read_text(encoding="utf-8")
    assert "skip %s" in (SCRIPTS / "accounts.py").read_text(encoding="utf-8")
