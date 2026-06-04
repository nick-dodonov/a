# OpenViking Memory Workflow

OpenViking is the long-term memory and context backend for this workspace.
Connection: `http://localhost:1933` (auth configured in `~/.openviking/ovcli.conf`).

## Hooks

Workspace hooks under `.github/hooks/ov-*.json` run automatically on lifecycle events:

| Event | Script | What it does |
|-------|--------|-------------|
| `SessionStart` | `session-start.py` | Injects profile + recent memories as `<openviking-context>` |
| `UserPromptSubmit` | `auto-recall.py` | Searches memories and injects relevant context before each prompt |
| `PostToolUse` | `post-tool-use.py` | Captures significant tool events to the OV session |
| `Stop` | `auto-capture.py` | Pushes new transcript turns to OV session and commits; OV runs async memory extraction |

Hooks fire automatically. The model does not need to call recall or store tools for routine turns — only when explicitly needed or when hooks are insufficient.

## Memory tools (on-demand)

Use the `mcp_openviking_*` tools when you need to go beyond what hooks inject:

- `mcp_openviking_search` — semantic search across memories, resources, skills
- `mcp_openviking_read` — read a specific `viking://` URI (expand an abstract to full content)
- `mcp_openviking_store` — push messages to OV session (manual commit)
- `mcp_openviking_find` — vector similarity search without session context
- `mcp_openviking_list` — list a `viking://` directory

## URI scheme

All content in OpenViking is addressed as `viking://`. The structure is
`viking://{scope}/{space}/{path}` where `{space}` is the user or agent name
(typically `default`). Hook scripts resolve space names dynamically via the API.

| URI | Contents |
|-----|----------|
| `viking://user/default/memories/profile.md` | User identity and preferences |
| `viking://user/default/memories/preferences/` | Topic-based preferences |
| `viking://user/default/memories/entities/` | People, projects, entities |
| `viking://user/default/memories/events/` | Decisions and milestones |
| `viking://agent/default/memories/cases/` | Problem–solution pairs |
| `viking://agent/default/memories/patterns/` | Reusable patterns |
| `viking://agent/default/skills/` | Skill definitions |
| `viking://resources/{project}/` | Project knowledge base |

> MCP tools (`mcp_openviking_search`, `mcp_openviking_read`) accept both the
> fully-qualified form above and shorthand like `viking://user/memories`. The
> REST API used by hook scripts requires the fully-qualified form.

When `<openviking-context>` references URIs, call `mcp_openviking_read` to expand them.

## Start-of-task behavior

If the `SessionStart` hook already injected sufficient context, skip redundant search.
Otherwise, if the task scope is new or shifted, run:

```
mcp_openviking_search(query="<concise task description>", limit=6)
```

Summarize retrieved context in 2–4 bullets and proceed.

## End-of-task behavior (important decisions)

The `Stop` hook captures the session automatically. For high-value decisions that
deserve a curated memory entry, use the `/ov-commit` prompt (`.github/prompts/ov-commit.prompt.md`)
to draft and store a structured memory.

Do **not** store: secrets, tokens, passwords, private keys, or raw file contents.
Prefer one curated memory over many noisy near-duplicate entries.
