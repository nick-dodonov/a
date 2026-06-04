# MCP Memory Workflow

Use this workspace workflow when MCP memory tools are available.

## Hooks First
- Workspace hooks under `.github/hooks/*.json` are the primary automation path for memory lifecycle.
- Hooks run deterministically on lifecycle events (for example UserPromptSubmit, SessionStart, PostToolUse, Stop).
- Agent instructions define policy and quality expectations; they do not replace hook execution.

## Goal
Keep short-term chat context small while preserving key decisions in mcp-memory-service.

## Start-of-task behavior
- Before deep implementation, run memory retrieval once:
  - Prefer `mcp_memoryservice_retrieve_memory` with a concise query built from the current task.
  - If the task has stable labels, also run `mcp_memoryservice_search_by_tag`.
- Summarize retrieved context in 3-6 bullets and continue.
- If SessionStart hook already injected sufficient context, avoid duplicate retrieval unless the task scope changed.

## End-of-task behavior
- Propose a compact memory draft with:
  - problem
  - decision
  - why
  - constraints
  - next step
- Ask for confirmation before writing memory.
- After confirmation, store memory through available memory tool/API path and include consistent tags.
- If hooks already auto-captured the relevant outcome, avoid duplicate near-identical entries; prefer one curated memory.

## Marker Overrides
- Respect prompt markers consumed by hooks:
  - `#skip`: skip auto-capture for the current prompt lifecycle.
  - `#remember`: force capture for the current prompt lifecycle.
- If both markers are present, treat as `#skip` (safety-first default).

## Tag conventions
- `proj:a`
- `area:<component>`
- `type:decision|fix|note`
- `chain:<short-id>` for related entries

## Quality rules
- Do not store secrets, tokens, passwords, or private keys.
- Prefer one high-quality memory over many noisy entries.
- Keep memory entries concise and specific.
- Prefer deterministic hook capture for routine events and manual curated entries for high-value decisions.
