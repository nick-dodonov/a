---
description: "Use when you want to store a memory snapshot at any point in a session"
---
Create and store a concise memory snapshot for the current progress point.

Topic: ${input:topic}
What to save: ${input:summary}
Area: ${input:area}
Type (decision|fix|note): ${input:type}
Chain id (optional): ${input:chain}

Steps:
1. Build a compact draft:
- problem
- decision/update
- rationale
- constraints
- next-step
2. Suggest tags:
- proj:a
- area:${input:area}
- type:${input:type}
- chain:${input:chain}
3. Ask for confirmation before writing.
4. On confirmation, store via MCP memory tool/API.

Rules:
- Prefer one high-quality memory over multiple noisy entries.
- Do not store secrets or credentials.
- If similar memory already exists, propose updating/merging instead of duplicating.
