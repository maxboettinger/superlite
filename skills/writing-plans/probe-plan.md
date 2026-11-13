# The probe plan

Read this before you write the Review Focus and Running-app checks sections.

## Review Focus: the probe plan

Classify each package by app type, then pick its generic categories from the table. Add app-specific risks the domain implies (a spreadsheet: circular references through ranges, huge-range timing, CSV formula injection; a site generator: path traversal in slugs, template recursion).

| App type | Generic categories |
|---|---|
| library / parser / evaluator | deep, numeric, encoding, state |
| CLI | protocol (commands and args), encoding, state, file |
| HTTP service | protocol, encoding, numeric, state |
| web UI | protocol via its API, encoding (rendering, XSS) |
| file I/O / generator | file, encoding, deep |
| data pipeline | numeric, encoding, state, deep |
| concurrency | state (races, partial writes), protocol |
| auth | protocol, state; **security review required** (Opus) |

Rules:
- List, per package: app type, categories, specific risks.
- Copy into each task the cases that touch its files, as named tests with exact inputs and outcomes. The implementer writes them during TDD, so the failures never reach review (lever 1).
- Never list the spec's own examples: tests already cover them.
- An MCP-only check (Xcode `RenderPreview`) can be a task step when the project needs that MCP server: an implementer, fixer or package-reviewer of such a project starts with the servers its test-cmd.json `"mcp"` list names, else `xcode` for a Swift or Xcode project on macOS, while other fleet workers start with no MCP server; otherwise it is the coordinator's step after the package review.
- **Running-app checks.** A check that needs the running artifact (a simulator, the built macOS app, a widget, an app extension, a browser page) is never a plan task or a task step: an implementer skips it or cannot reach it. List each in a `## Running-app checks` section, one `- C<n>: <target>; reach: <state>; see: <what must show>` line per check. The coordinator runs them once, after every task is committed and before the final review packet, with a checker (`superlite:checker`, `../subagent-driven-development/fleet.md`), whose agent file holds the standing rules (own simulator, own build folder, screenshots in `.superlite/render/`).
- **Reach.** `reach:` names how the changed state is reached in the running app: a launch argument, fixture, URL or UI path from the project's `launch` entry in `.superlite/test-cmd.json` (setup records per platform whether a worker may launch the app and with which data; the prime repeats it), or a preview or snapshot render for a view no running state reaches. A state none of these reaches (an error or empty state, a screen that needs server pairing, a platform the entry marks `"worker": false`) gets a task that makes it reachable, such as a demo launch argument or a fixture loader, and `reach:` names that task (`reach: -fixture empty-inbox (T4)`). With no `launch` entry, read the app's launch arguments and fixtures from the code. Never leave the way in for the checker to find: it reports such a check NOT REACHABLE. Lint warns (`REACH:`) when a plan whose tasks own UI files has a check whose `reach:` names none of these and no task, or names a platform the entry marks `"worker": false` without a preview or task.
- A **`**Probe entry:**` line per package** feeds the generated probe adapter, for example `call=minisheet.Workbook.get · run=python -m minisheet · serve=minisheet.server.create_server`. Use `call=` for libraries, `run=` for CLIs, `serve=` for servers. `call=` must name a Produces of this plan with exactly one required parameter, because each probe passes one text argument (a `str`): a method's `self` does not count, every other parameter needs a default, and a method's class must build with no arguments. Anything else fails lint with `PROBE: call=<target> takes N required parameters; probes pass one text argument` (`Workbook.set(ref, raw)` takes two) or `PROBE: call=<target> is not a Produces of this plan`. A package without such a function leaves `call=` out: `run=` or `serve=` when it has a CLI or server, else `**Probe entry:** none (<why>)`, and its Review Focus cases become named tests in the owning task. No agent writes adapters. A domain exception a probe may raise is named `raises=Name[,Name]` on the entry: it counts as a rejection, not a crash. `call=` and `serve=` import Python; lint fails `PROBE: call=<target> imports Python, but T2 owns no Python file (TypeScript)` (also for `serve=`, or `but the plan's stack is <languages>` when no Owns entry names a source file and the Tech stack line does) when the code it would import is not Python; other languages use `run=` with an already built command, because each probe call has the run timeout (5 s, or from the measured start-up: max(5, 3 x the second warm call + 1) s, at most 60): a Swift package with an executable target gets `run=.build/debug/<Exec>` (built by `swift build`). Never `run=swift run`, `swift test` or `xcodebuild` (they compile on every call). A Swift library or Xcode app target without an executable gets no `Probe entry`; its Review Focus cases become named XCTest or Swift Testing tests in the owning task.
