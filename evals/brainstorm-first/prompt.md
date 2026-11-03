---
schema_version: "1.1"
name: brainstorm-first
description: A vague build request starts with brainstorming, not code.
runs: 2
model: sonnet
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion]
---

Let's make a react todo list
