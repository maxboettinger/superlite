# Language

The tools are Python, but the project can be in any language. `run_tests` uses the project's own test command (`.superlite/test-cmd.json`, else detection from its marker files). The probe stage (`probe_run`) is Python only.

**Swift.** A `Package.swift` is detected without any `test-cmd.json`: `swift test --xunit-output {junit}`, and per-file runs through `--filter` on the test file basenames (placeholder `{names}`, e.g. `NotificationModelTests|PushPayloadTests`). `swift test` writes Swift Testing results to the `-swift-testing.xml` sidecar next to the JUnit file; `run_tests` counts every non-empty `<junit stem>*.xml` and sums them. A worktree without its own `.superlite/test-cmd.json` falls back to the main checkout's. The log and the failure tail are ANSI-free.
