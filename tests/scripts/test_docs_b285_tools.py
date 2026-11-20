"""docs/tools.md names #1006, #1007, #906 and #1015 (B285, #1031)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
DOC = ROOT / "docs" / "tools.md"

ORCH = " A relative `--plan` (and `approve`'s or `status`'s `--review`) that names nothing at the cwd resolves at the enclosing checkout's top, a bare `.superlite` at the nearest folder up to that top that holds a run (else the cwd's); run from a subfolder, `set`, `bind` and `approve` refuse a relative plan found at neither place before they bind or approve: `orchestrator: plan not found: X (neither at the cwd nor at <top>); not set` (`not bound`, `not approved`), exit 2, and `approve --review R` without `--plan` prints `orchestrator: review plan not found: R (neither at the cwd nor at <top>); not approved` (#1006)."
STATUS = "; a lead's full run state is `sl status --plan <worktree>/.superlite`, its one-line progress the `lead Wn <worktree>: ...` line of `sl fleet status` (#906)"
FLEET = "; `spawn --role lead --plan P [--brief F] [--label L] [--wait]` starts a lead for the plan P in P's own worktree (its run is `<worktree>/.superlite`; without `--brief` it writes `<worktree>/.superlite/briefs/lead.md`, whose lead never pushes, merges or ships) and prints `Wn lead <worktree>: progress: sl fleet status; ...`; `status` prints one `lead Wn <worktree>: plan <plan> (N tasks); ...; workers busy K; question: open <path>` (or `question: none`) line per live lead, batch leads too (`status.lead_progress`); `NEEDS_DECISION` is a report status, and `wait` ends such a lead's line with ` question=<worktree>/.superlite/question.json` when that file exists (#906); `spawn --brief F` and `send Wn --brief F` (every role but lead) refuse with one `error:` line from `fleet_io.brief_refusal`, exit 2, before any gate, pane or prompt, a brief file outside the project, the run folder and the plugin skills folder (`error: brief F is outside the project, the run folder and the plugin skills folder; a worker cannot read it: move it into <sd>/briefs/ (#1015)`) and a brief that, with the plan's Global constraints (spawn) or a review spawn's `--note`, names such a path outside fenced code blocks (`error: brief F names paths outside the project, the run folder and the plugin skills folder: P, ...; a worker cannot read them: copy each file into <sd>/briefs/ and name the copy, or drop the path (#1015)`, at most five paths, then ` and N more`) (#1015, #1024)"
BASE = " A skipped test's file may name the files its session must collect in a module-level `SESSION_FILES` tuple or list of string globs relative to its own folder (read with `ast`, never imported; an absolute or `..` pattern is dropped, and a file that does not parse names none): the base run adds their matches in the base tree to the narrowed run and prints `run_tests: --base-skips: the base run also collects N files SESSION_FILES names, so a skip that depends on what its session collects matches the full run's`; test-summary-base.json keeps its keys (#1007)."


def _row(name):
    rows = [l for l in DOC.read_text(encoding="utf-8").splitlines() if l.startswith(f"| `{name}` | ")]
    assert len(rows) == 1, name
    return rows[0]


def test_orchestrator_row_names_1006():
    assert _row("orchestrator").endswith(ORCH + " |")


def test_status_row_names_lead_progress():
    assert _row("status").endswith(STATUS + " |")


def test_fleet_row_names_906_and_1015():
    assert FLEET + "; `send`, `keys` and `wait` are handled by `fleet_io` (see `docs/fleet.md`)" in _row("fleet")


def test_base_skips_names_session_files():
    lines = [l for l in DOC.read_text(encoding="utf-8").splitlines() if l.startswith("`sl run_tests --base-skips [--plan DIR]`")]
    assert len(lines) == 1 and lines[0].endswith("(#999)." + BASE)


def test_messages_match_code():
    orch = (SCRIPTS / "orchestrator.py").read_text(encoding="utf-8")
    for s in ("orchestrator: plan not found: {a.plan} (neither at the cwd nor at {top}); not {word}",
              "orchestrator: review plan not found: {review} (neither at the cwd nor at {top}); not approved"):
        assert s in orch, s
    rt = (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
    assert "SESSION_FILES" in rt
    assert "the base run also collects {len(extra)} files SESSION_FILES names, so a skip that depends on what its session collects matches the full run's" in rt
    io = (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
    assert "is outside the project, the run folder and the plugin skills folder; a worker cannot read it: move it into {sd.resolve()}/briefs/ (#1015)" in io
    assert 'f" question={question}"' in io
    fl = (SCRIPTS / "fleet.py").read_text(encoding="utf-8")
    assert "names paths outside the project, the run folder and the plugin skills folder: {named}; " in fl
    assert "a worker cannot read them: copy each file into {sd}/briefs/ and name the copy, or drop the path (#1015)" in fl
    assert ' and {len(paths) - 5} more' in fl
    st = (SCRIPTS / "status.py").read_text(encoding="utf-8")
    for s in ('f"workers busy ', 'f"question: open {q}"', '"question: none"', "tasks)"):
        assert s in st, s
    assert "progress: sl fleet status; run state: sl status --plan " in (SCRIPTS / "fleet_lead.py").read_text(encoding="utf-8")
