---
name: openviking
description: Manage context through OpenViking Context Database — search, store, add resources, navigate code.
---

# OpenViking Skill

Use OpenViking to manage project context.

## When to use

- **Before starting a task**: find relevant context via `find` or `search`
- **After completing a task**: save key decisions via `remember`
- **When working with new documentation**: add a resource via `add_resource`
- **When navigating code**: use `code_search` → `code_outline` → `code_expand`

## Tiered Context Loading

Always use the tiered approach:

1. **L0 (`.abstract`)**: check relevance — `find` or `search` returns abstracts
2. **L1 (`.overview`)**: if relevant, read the overview to understand structure
3. **L2 (full content)**: read full content only when necessary

## Patterns

### Search context before a task
```
find "query about the task"
```

### Store results
```
remember "key decision or insight"
```

### Add a resource
```
add_resource https://example.com/docs
```

### Navigate code
```
code_search "ClassName" --uri viking://resources/...
code_outline --uri viking://resources/.../file.py
code_expand "ClassName.method_name" --uri viking://resources/.../file.py
```