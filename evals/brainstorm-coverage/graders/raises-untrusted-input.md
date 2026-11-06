---
type: llm
focus: {source: file, path: docs/design.md}
criteria: The design treats the imported mail files as untrusted input - for example bound SQL parameters instead of string formatting, skipping symlinks or odd file names, or a cap on what is read - as a decision, a Ruling or a question.
---

The security side of the mail import is named explicitly.
