# Session-bound state: parallel sessions in worktrees never share a gate

Origin: PIX-837 (pix-app). Two Claude Code sessions launched from one checkout, each building in its own
git worktree, shared one `.superlite`: the hooks resolve it from `CLAUDE_PROJECT_DIR` or the hook input's
`cwd` (the launch directory; the shell's `cd` does not persist between tool calls), while `sl` resolves it
next to the plan. One session's `sl orchestrator set human` shut the other session's build, replies were
recorded into the wrong state, and nothing ended a run, so the guard kept blocking after it.

## Design

**Binding.** A session is bound to one state directory. The binding is a file
`$SUPERLITE_HOME/sessions/<session id>` (default `~/.superlite/sessions/`) holding the absolute path of
the `.superlite` directory, plus `.superlite/session` holding the owning session id. Claude Code gives
Bash `CLAUDE_CODE_SESSION_ID` and every hook `session_id`; they are the same id, so `sl` and the hooks
find the same binding without any launch discipline.

- Written by `sl orchestrator set` and `approve` and by `plan_tools lint --stable` (the run's start
  points), when `CLAUDE_CODE_SESSION_ID` is set. `sl orchestrator bind [--plan P]` binds explicitly.
- Removed by `sl orchestrator end`. Bindings older than 14 days are pruned whenever one is written.
- `SUPERLITE_STATE_DIR` (absolute path of a `.superlite`) overrides everything, for hosts without
  session ids.

**Resolution, the same order everywhere** (hooks in bash builtins, scripts in `state.py`):

1. `SUPERLITE_STATE_DIR`;
2. the session's binding, when its directory exists;
3. legacy: `<CLAUDE_PROJECT_DIR or cwd>/.superlite`, skipped when its `session` file names another
   session (another session's run never gates this one).

Scripts that take a plan resolve it from the plan's **git toplevel** (walk up to `.git`, file or
directory), so `docs/superpowers/plans/x.md` in a worktree maps to `<worktree>/.superlite`; the old
"next to the plan" rule stays as the fallback outside git. `approve --review P` uses P's toplevel, so the
approval lands in the state of the review plan's worktree.

**Recorder.** `record-human-reply` resolves the state as above, so replies land in the session's own
pending plan; it still records only while that state is human and unapproved.

**End of a run.** `sl orchestrator end [--plan P]` moves `stable.json`, `prime.md`, `prime-haiku.md`,
`pool.json`, `orchestrator.json` and `human-replies.jsonl` into `.superlite/runs/<timestamp>/`, deletes
`.superlite/session` and the session's binding, and prints one line. The guard stops at once (no run
marker, no gate). `finish` prints the reminder; the finishing skill runs it.

**Guard targets.** Interpreter writers (`python`, `node`, `ruby`, `php` with `open(..., 'w')`,
`write_text`, `writeFileSync`, ...) are judged by target: the quoted path literals in the command are
classified like any other write; all allowed (at least one) means allow; any project code means block;
no literal at all keeps today's block while a gate or run is active. Allowed paths gain
`docs/*/plans/*` (e.g. `docs/superpowers/plans/`) and `docs/*/plans/*.review.md` under the human gate.
The `rm .superlite` denial names `sl orchestrator end`.

**Small tool fixes.** `incident hotspots --files` takes several paths and comma lists. `build_prime
--sections N` on a spec without numbered headings picks the N-th section at the top section level, and an
unknown token lists the available sections. (`incident add --kind verified` already works on main.)

Out of scope (follow-up): a Swift profile (run_tests command, per-lane DerivedData, probe adapter).

## Plan

Built inline (one chain through `state.py`, small diffs), test-first with pytest under `tests/scripts/`.

1. `scripts/state.py`: `git_root`, `resolve(plan=None)`, `bind`, `unbind`, `owner`, prune; tests.
2. `orchestrator.py`: `sl_dir` via `state`; bind on set/approve/bind; `end`; `approve --review` uses the
   review path's toplevel; tests.
3. `plan_tools.stable_root` via git toplevel; `lint --stable` binds; test for a
   `docs/superpowers/plans` plan in a worktree.
4. Hooks (`block-coordinator-edits`, `record-human-reply`, `capture-agent-*`, `rewrite-test-runs`): the
   shared resolution order; tests with two sessions on one launch directory.
5. Guard: interpreter target check, `docs/*/plans` paths, end hint; tests from the PIX-837 cases.
6. `incident hotspots --files`, `build_prime` ordinal sections; tests.
7. Docs: `docs/gates.md`, `docs/hooks.md`, `docs/tools.md`, finishing skill; full suite; version bump
   1.1.1 through `scripts/bump-version.sh`.
