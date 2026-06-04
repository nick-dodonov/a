---
description: Search OpenViking for context relevant to the current task
---

Search OpenViking for memories and context relevant to the current task or question.

Steps:
1. Build a concise query from the current task description (1–2 sentences or key terms).
2. Call `mcp_openviking_search` with that query, `limit=6`.
3. For any high-relevance URI, call `mcp_openviking_read` to expand the full content.
4. Summarize retrieved context in 3–5 bullets and proceed.

If nothing relevant is found, say so briefly and continue without fabricating context.
