# Copilot Memory Hooks MVP

This folder implements a workspace-local MVP that gives VS Code Copilot memory behavior similar to Claude/OpenCode integrations, adapted to Copilot hooks.

## Why scripts are used

MCP tools are callable by the agent, but hooks run as deterministic shell commands. The hook runtime does not execute MCP tool calls directly. Scripts are the bridge from hook lifecycle events to the memory service HTTP API.

This is the same pattern used by Claude/OpenCode integrations in `mcp-memory-service`: hook/plugin code performs HTTP calls to the service rather than invoking MCP tool names.

## Hook flow

- `UserPromptSubmit` -> `user-prompt-submit.js`: captures per-session override mode from prompt markers (`#skip` / `#remember`).
- `SessionStart` -> `session-start.js`: retrieves relevant memories and injects concise context into the session.
- `PostToolUse` -> `post-tool-use.js`: stores high-signal tool outcomes as compact note memories.
- `Stop` -> `stop.js`: stores a lightweight session summary using transcript excerpts.

## Prompt markers

- `#skip`: disables auto-capture for the current prompt lifecycle.
- `#remember`: forces capture (bypasses normal signal thresholds).
- If both markers are present, `#skip` wins by default (`userOverrides.skipWins=true`).

The mode is written by `UserPromptSubmit` and read by both `PostToolUse` and `Stop`.

All scripts are fail-open: if memory service is unavailable, hooks return `{"continue": true}` and never block Copilot.

## Configuration

Default config file: `.github/hooks/memory-hooks.config.json`

Environment overrides:

- `MCP_MEMORY_ENDPOINT` or `MEMORY_HOOKS_ENDPOINT`
- `MCP_MEMORY_API_KEY` or `MEMORY_HOOKS_API_KEY`
- `MEMORY_HOOKS_CONFIG` (explicit config path)

## Local test examples

```bash
printf '{"cwd":"/Users/nik/p/t/a","sessionId":"demo"}' | node scripts/memory-hooks/session-start.js

printf '{"cwd":"/Users/nik/p/t/a","sessionId":"demo","prompt":"quick check #skip"}' | node scripts/memory-hooks/user-prompt-submit.js

printf '{"cwd":"/Users/nik/p/t/a","tool_name":"create_file","tool_input":{"filePath":"README.md"},"tool_response":"ok"}' | node scripts/memory-hooks/post-tool-use.js

printf '{"cwd":"/Users/nik/p/t/a","sessionId":"demo","transcript_path":"/tmp/missing.json"}' | node scripts/memory-hooks/stop.js
```
