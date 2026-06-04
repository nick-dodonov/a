---
description: "Use when starting a task and you want relevant context from MCP memory"
---
This is a start-focused variant. For mid-session context top-ups, use `memory-load.prompt.md`.

Retrieve relevant context from MCP memory for this task.

Task/topic: ${input:task}

Steps:
1. Run semantic retrieval for the task/topic.
2. If useful, run tag-based retrieval for likely tags.
3. Return:
- top facts
- prior decisions
- known constraints
- open risks

Keep the summary compact and actionable.
