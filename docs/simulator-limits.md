# Simulator limits

Limits of Apple's simulator tooling that superlite runs have met. None of them is superlite code, and superlite cannot fix them. Each entry says where it was seen, what was tried and what to do instead, so the next agent does not repeat the attempts.

Add an entry when a run loses time to a limit like these: the versions, the commands tried, and what worked. Mark an option nobody has tried yet as untried.

## iOS: package tests get no full Reminders access

Seen: once, 2026-11-11, superlite 1.5.109, Xcode 27.2, iOS 27.2 simulator ([#569](https://github.com/maxboettinger/superlite/issues/569)).

A Swift package's tests ran on the iOS Simulator with `xcodebuild test -scheme <Package>-Package -destination 'platform=iOS Simulator,...'`. The tests gated on full Reminders access (live EventKit store tests) stayed skipped: the package's test runner never got full access. Tried, none worked:

- `xcrun simctl privacy <udid> grant reminders com.apple.xctest`
- the same grant for `com.apple.dt.xctest.tool`
- a path entry for the test runner in the simulator's TCC database
- a reboot of the simulator

What to do: do not retry the grant. Untried options: run these tests on a device or on macOS, or move them into a test target hosted by an app whose bundle id `simctl privacy` can grant. A batch that ships without them names them in a `Left undone:` line of its notes.

## watchOS: friction in the screenshot step

Seen: once, 2026-11-11, superlite 1.5.109, in a lead's pre-plan screenshot step of a watch app ([#571](https://github.com/maxboettinger/superlite/issues/571)). The entry that recorded them says every watch run of that project met them:

- **Build.** `maxapp build` needs a `.maxapp` file at the project root; without one it cannot build the watch target. Build with plain `xcodebuild` and `-destination 'platform=watchOS Simulator,id=<udid>'`. Where `xcodebuild` on `PATH` is the build-slot shim, the direct call still waits for a build slot.
- **Typing.** `rocketsim interact type` types nothing into the watchOS system text input sheet. What worked: the Xcode MCP's `DeviceInteractionSynthesize` with `sender keyboard kbd <text>`.
- **Sessions.** An Xcode MCP DeviceInteraction session is lost after each app relaunch. Start a new session after every relaunch, before the next tap or text.
- **Simulators.** `xcrun simctl clone` refuses a watch simulator. Create a per-worktree watch simulator with `xcrun simctl create <name> <watch device type> <watchOS runtime>` instead.
- **Xcode MCP.** The Xcode MCP server disconnected mid-session. Untried: reconnect the server, then start a new DeviceInteraction session.

## SwiftUI previews: no command-line renderer

Seen: superlite 1.5.123, in fleet package reviews ([#600](https://github.com/maxboettinger/superlite/issues/600)).

Xcode renders `#Preview` blocks only inside Xcode: the Xcode MCP `RenderPreview` tool needs a running Xcode, and a fleet worker starts with no MCP server except an implementer, fixer or package-reviewer of a project that needs one (the servers its test-cmd.json `"mcp"` list names, else `xcode` for a Swift or Xcode project on macOS). Two reviewers rendered PNGs with throwaway hosted tests instead and left them in the tree.

What to do: a checker renders a view no running state reaches with a throwaway `ImageRenderer` snapshot test, recorded with `sl render_edit start <file>` and undone with `sl render_edit restore` (`agents/checker.md`).

## macOS: no simulator for a render check

Seen: superlite 1.5.109 ([#600](https://github.com/maxboettinger/superlite/issues/600)). With no macOS render check, every macOS UI batch ended with a live check left for the user; 36 piled up after about 60 batches.

What to do: a checker launches the built `.app` and captures it with `screencapture -x` (`agents/checker.md`). Untried: whether a fleet pane's terminal has the Screen Recording permission `screencapture` needs; a refused or blank capture is NOT REACHABLE.
