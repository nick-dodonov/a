---
description: "Use when finishing a task and you want to persist outcome to MCP memory"
---
This is an end-focused variant. For mid-session snapshots, use `memory-save.prompt.md`.

Create a memory draft from the completed work, then ask for confirmation to store it.

Task/topic: ${input:task}
Outcome summary: ${input:outcome}

Draft format:
- problem
- decision
- rationale
- constraints
- next-step

Tag suggestions:
- proj:a
- area:${input:area}
- type:${input:type}
- chain:${input:chain}

After showing the draft, ask: "Store this in memory?"
Only store after explicit confirmation.
