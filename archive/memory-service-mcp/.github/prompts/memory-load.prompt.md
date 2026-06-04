---
description: "Use when you need to load additional context from MCP memory at any point in a session"
---
Load relevant context from MCP memory for the current topic without resetting conversation flow.

Topic/query: ${input:topic}
Optional focus tags (comma-separated): ${input:tags}

Steps:
1. Run semantic retrieval for the topic/query.
2. If tags are provided or obvious, run tag-based retrieval.
3. Return only useful additions:
- newly relevant facts
- prior decisions that affect next steps
- constraints/risks that are easy to miss
- what changed vs already-known context

Rules:
- Keep output compact and actionable.
- Do not duplicate context already visible in this session.
- If nothing useful is found, say so explicitly.
