# OpenViking Context Database

This project uses OpenViking — a context database for AI agents.

## Available tools

The following tools are available via the `openviking` MCP server:

| Tool | Purpose |
|-----|-----------|
| `search` | Semantic search across memories, resources, and skills |
| `find` | Fast semantic search |
| `read` | Read one or more `viking://` URIs |
| `list` | List contents of a `viking://` directory |
| `store` / `remember` | Save to long-term memory |
| `add_resource` | Add a local file or URL as a resource |
| `grep` | Regex search across `viking://` file contents |
| `glob` | Find files by glob pattern |
| `code_outline` | Symbol structure of a file |
| `code_search` | Search symbol names |
| `code_expand` | Full source of a symbol |
| `health` | Check service health |
| `forget` | Delete a URI (irreversible) |

## viking:// structure

```
viking://
├── resources/          # Resources: documentation, repositories, web pages
├── user/               # User: preferences, habits
│   └── memories/
└── agent/              # Agent: skills, instructions, task memory
    ├── skills/
    ├── memories/
    └── instructions/
```

## Tiered Context (L0/L1/L2)

OpenViking stores context in three tiers:
- **L0 (`.abstract`)**: one-line description (~100 tokens) — quick relevance check
- **L1 (`.overview`)**: overview (~2k tokens) — understand structure and key points
- **L2**: full content — read only when necessary

**Rule**: always start with `.abstract` or `.overview`, move to L2 only when more detail is needed.

## Usage scenarios

1. **Before starting a task**: run `find` or `search` with a relevant query to find existing context
2. **After completing a task**: save key decisions and insights via `remember`
3. **Adding sources**: use `add_resource` for documentation, repositories, web pages
4. **Code search**: use `code_search` / `code_expand` for code navigation through OpenViking
5. **Connection check**: `health` before starting work with OpenViking

## Important

- `forget` is an irreversible operation, requires confirmation
- When adding resources via `add_resource` with a URL, processing happens asynchronously
- For local files, a two-step upload is required (first `add_resource` with path, then HTTP POST)