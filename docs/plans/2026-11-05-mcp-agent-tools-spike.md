# Spike: MCP tools for plugin agents (S1, #98)

**Question:** which `tools:` line gives a plugin agent the project's MCP tools without giving it the `Agent` tool?

**Setup:** Claude Code 2.1.318, run from `/Users/max/github/superlite`. `claude mcp list` showed: `claude.ai Claude Docs`, `plugin:context7:context7`, `plugin:github:github`, `plugin:playwright:playwright`, `plugin:atlassian:atlassian`, `xcode` (`xcrun mcpbridge`), all connected; `Sunsama` needed authentication. Temporary plugin `mcpprobe` (`.claude-plugin/plugin.json` `{"name": "mcpprobe"}`, `agents/probe-a.md` to `probe-d.md`, `model: haiku`, body "List the names of every tool you can call, one per line, then stop."), removed afterwards.

**Command** (x = a, b, c, d; exit 0 each, about 4 cents in total):

```
cd /Users/max/github/superlite && claude -p --plugin-dir <tmp>/mcpprobe --model haiku --max-turns 3 --output-format json "Use the Agent tool with subagent_type mcpprobe:probe-x. Reply with its answer verbatim."
```

## Findings

| Probe | Frontmatter line under test | Started | Tools the agent listed | Error |
|---|---|---|---|---|
| a | `tools: Read, Bash, mcp__*` | yes | `Read`, `Bash`, `SubagentHandback`; no MCP tool | none |
| b | `tools: Read, Bash, mcp__xcode__*` | yes | `Read`, `Bash`, `SubagentHandback` and all 54 `mcp__xcode__*` tools (`mcp__xcode__BuildProject`, `mcp__xcode__XcodeRead`, ...) | none |
| c | `tools: Read, Bash, mcp__nosuchserver__*` | yes | `Read`, `Bash`, `SubagentHandback`; no MCP tool | none (an unknown server is ignored silently) |
| d | no `tools:` line, `disallowedTools: Agent, Write` | yes | 194 names: no `Agent`, no `Write`; every MCP tool of every connected server (`mcp__xcode__` 54, `mcp__plugin_github_github__` 49, `mcp__plugin_atlassian_atlassian__` 26, `mcp__plugin_playwright_playwright__` 25, `mcp__claude_ai_Claude_Docs__` 8, `mcp__plugin_context7_context7__` 2), plus the harness tools (`Bash`, `Edit`, `Read`, `Skill`, `WebFetch`, `TaskCreate`, `EnterWorktree`, ...) | none |

## Reading

- A wildcard works per server (`mcp__xcode__*`), not as a bare `mcp__*` (probe a gave no MCP tool).
- A server name that does not exist is not an error (probe c), so a list of per-server globs is safe to ship but names servers the plugin cannot know: server names differ per user and project (`xcode`, `plugin_github_github`, `claude_ai_Claude_Docs`).
- Omitting `tools:` and denying `Agent` with `disallowedTools` reaches every connected server without naming one (probe d).
- Not tested: whether `Agent` is listed when `disallowedTools` is absent; a bare `mcp__*__*`; calling an MCP tool (the agents only listed names, self-reported by haiku).
- Side effect of probe d: the agent also gets harness tools such as `WebFetch`, `WebSearch`, `TaskCreate`, `EnterWorktree`, `SendMessage`; deny those too if the agent files must stay narrow.

## Recommendation

Drop the `tools:` line and write `disallowedTools: Agent` (extend it with any harness tool an agent must not have); a per-server `mcp__<server>__*` entry after the core tools (`tools: Read, Edit, Write, Bash, Grep, Glob, mcp__xcode__*`) is the fallback for a project that names its servers.
