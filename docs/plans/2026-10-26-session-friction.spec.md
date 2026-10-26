# Session friction: false alarms the coordinator has to reason around

Origin: the PixKit notifications build on 2026-10-26 (sessions ccf887ee planning, 83e0675b build). Four tasks
built and reviewed in 8 minutes with zero rework, but the surrounding checkers misfired on a Swift package in a
git worktree running in checkpoint mode. Every misfire cost the Opus coordinator two to five turns at
130k context, and two of them surfaced as findings of the final review.

## 1. Test runner on Swift Testing and worktrees

- `swift test --xunit-output X` writes XCTest results to `X` and Swift Testing results to `X-swift-testing.xml`.
  `run_tests` read only `X`: the full suite reported `passed 1`; the real count was 548.
- `.superlite/test-cmd.json` lived in the main checkout's `.superlite`; the worktree had none, so the fast
  runner said "no test command found" until the coordinator copied it by hand.
- `test-output.log` was full of ANSI colour escapes from the Swift compiler.
- Wanted: every non-empty `<junit stem>*.xml` the runner writes next to the requested path is parsed and the
  counts summed; a `Package.swift` project is detected without any config (`swift test --xunit-output {junit}`,
  per-file runs through `--filter` on the test file basenames, placeholder `{names}`); a worktree without
  `test-cmd.json` reads the main checkout's (`git rev-parse --git-common-dir`, its parent's `.superlite`);
  the log and the tail are ANSI-free.

## 2. Contract check for non-Python producers

- `pt_review contract` introspects Python modules only. For a Swift producer every Produces line logged
  `no module found (file missing)` as a high-confidence incident: 4 false incidents, final-review finding #1.
- Wanted: when a producer owns no Python source, each Produces name is checked by declaration: the first
  component of the qualified name must be declared in one of the producer's owned source files (a per-extension
  regex; Swift, TypeScript/JavaScript, Go, Rust, and a generic fallback for Kotlin, Java, C#, Ruby, PHP).
  Declared: `verified` with the file and line, parameters unchecked, note `checked by declaration`. Not declared:
  one mismatch naming the symbol and the files searched. Python producers behave as before.

## 3. Review packet in checkpoint mode

- `commit_task` stores shadow commits under `refs/superlite/<run>/<Tn>`; the working tree stays dirty and new
  files stay untracked. The packet's diff stat is `git diff --stat <base>` against the working tree, which
  omits untracked files: it showed 11 of 19 files, and the coordinator ran `git add -N` by hand.
- Wanted: when `.superlite/checkpoints.json` lists entries, the diff stat and the source excerpts compare
  `<base>` with the newest entry's sha; without checkpoints the working tree is used as today.

## 4. Session hand-over from planning to build

- The planning session, launched in the main checkout, wrote the plan into a worktree and ran `lint --stable`
  there, which bound the worktree's `.superlite` to it. The build session, launched in that worktree as the
  planning session's own closing report told Max to do, was refused (`belongs to session ...`); `bind --force`
  without `--plan` then bound a private folder under `~/.superlite/sessions/`, and only `bind --plan --force`
  worked. Three turns on every plan-then-build hand-over.
- Wanted: a session launched in the folder's own project (launch directory = the `.superlite`'s parent) takes
  the folder over without `--force` when its owner was launched elsewhere; a binding records the owner's launch
  directory (line 3) so that can be decided; an owner launched in the same directory still wins (two sessions
  from one checkout never share a gate, as today). `bind` without `--plan` always targets the launch
  directory's `.superlite`, never the private folder; `--force` remains for a session launched elsewhere.

## 5. Coordinator guard false positives

- `cp ../../../.superlite/test-cmd.json .superlite/` was blocked: a directory target (trailing slash) is
  judged as the path `.superlite`, which matches no allowed pattern.
- `P=docs/superpowers/plans/x.md; python3 - "$P" <<'EOF' ... open(p,'w') ... EOF` (p = sys.argv[1]) was
  blocked as an unknown target, although the only file written is the plan.
- Two blocks in two sessions, no true positive. Wanted: `cp`, `mv` and `tee` with a directory target
  (trailing slash, `.`, or an existing directory) are judged by `<dir>/<basename of the source>`;
  `sys.argv[N]` as a writer target resolves to the interpreter's N-th positional argument after the script
  (`-`, a file, or `-c CODE`), through one `VAR=literal` assignment in the same command; anything
  unresolvable stays unknown and blocks. The existing allow and block cases keep their verdicts.

## 6. Dispatch keeps offering a skipped Wave 0

- The coordinator ruled `skip T0` (Swift whole-module compile, stubs break the build), yet every
  `commit_task --dispatch` printed `T0 wave0 ...` first.
- Wanted: a ledger line starting `- Ruling: skip T0` silences the T0 line.

## 7. Docs and version

- The subagent-driven-development skill, `orchestrator.md`, `docs/hooks.md` and `docs/language.md` describe
  the new behaviour (skip ruling, Swift without config, sidecar reports, declaration contract, checkpoint diff,
  own-project hand-over, guard rules). Version 1.2.1 through `scripts/bump-version.sh`, audit clean.

## Out of scope

The metrics counting harness sidecar agents, the predictor calibration, the final reviewer's value, and the
max-core Stop hook (a separate change in that repository).
