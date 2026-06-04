---
description: Draft and store a curated memory entry in OpenViking
---

Draft a structured memory entry for the current task outcome and store it in OpenViking.

Steps:
1. Draft a memory entry with these fields:
   - **problem**: what was the task or issue
   - **decision**: what was done or decided
   - **why**: reasoning or constraints
   - **next step** (optional): follow-up action if any

2. Present the draft to the user for confirmation before storing.

3. After confirmation, call `mcp_openviking_store` with:
   ```
   messages=[{"role": "assistant", "content": "<formatted entry>"}]
   ```

Quality rules:
- One focused memory per significant decision — avoid near-duplicates.
- Do not store: secrets, tokens, passwords, private keys, or raw file contents.
- Keep entries concise (aim for <400 chars).
- If the `Stop` hook will capture this session automatically, only store
  entries with information that clearly deserves curation beyond the transcript.
