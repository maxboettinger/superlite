---
type: llm
focus: {source: file, path: docs/design.md}
criteria: The design names a way back if the SQLite version misbehaves after release - a rollback step, a release order, or how to restore or export the notes to JSON - as a decision, a Ruling or a question. Keeping a renamed notes.json from the migration counts only when the design says it is the way back.
---

The way back is named explicitly, not just a one-way migration.
